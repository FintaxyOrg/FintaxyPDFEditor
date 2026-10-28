"""Uneltele PDF făcute direct în aplicație (PyMuPDF, pdf2docx, pyHanko), fără Stirling: merg pe orice calculator
cu aplicația portabilă. Uneltele rare (OCR, conversii exotice) rămân la Stirling, dacă e instalat.

Fiecare unealtă primește PDF-ul deschis (path) și câmpurile formularului din editor (fields) și întoarce ce a
scris: {kind: pdf | file | folder | report, out, files?, lines?}. Rezultatele stau lângă PDF, cu un sufix în nume.
"""
import io
import os
import re
import subprocess
from pathlib import Path

import fitz

import fx_sign

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def free_name(folder: Path, stem: str, ext: str) -> Path:
    p = folder / f"{stem}{ext}"
    k = 2
    while p.exists():
        p = folder / f"{stem}-{k}{ext}"
        k += 1
    return p


def next_to(pdf: Path, suffix: str, ext: str = ".pdf") -> Path:
    return free_name(pdf.parent, f"{pdf.stem}_{suffix}", ext)


def pages_of(spec: str, n: int) -> list:
    """„1-3, 5, 8-” -> [0, 1, 2, 4, 7, ..., n-1] (numerotare de la 0, fără dubluri, în ordinea scrisă)."""
    spec = (spec or "").strip().lower()
    if spec in ("", "all", "toate"):
        return list(range(n))
    out = []
    for part in re.split(r"[,;\s]+", spec):
        if not part:
            continue
        m = re.fullmatch(r"(\d*)-(\d*)", part)
        if m:
            a = int(m[1]) if m[1] else 1
            b = int(m[2]) if m[2] else n
        elif part.isdigit():
            a = b = int(part)
        else:
            raise ValueError(f"Nu înțeleg „{part}”: scrie paginile ca 1-3, 5, 8-")
        if a < 1 or b > n or a > b:
            raise ValueError(f"Paginile {part} nu există (PDF-ul are {n}).")
        out += [i for i in range(a - 1, b) if i not in out]
    return out


def open_pdf(path: str, password: str = "") -> fitz.Document:
    doc = fitz.open(stream=Path(path).read_bytes(), filetype="pdf")
    if doc.needs_pass and not doc.authenticate(password or ""):
        raise ValueError("PDF-ul are parolă: scrie-o în câmpul Parola.")
    return doc


def save(doc: fitz.Document, target: Path, **kw) -> Path:
    tmp = target.with_name(f".{target.stem}.tmp{target.suffix}")
    doc.save(str(tmp), garbage=kw.pop("garbage", 3), deflate=True, **kw)
    os.replace(tmp, target)
    return target


def warn_signed(doc):
    if fx_sign.is_signed(doc):
        raise ValueError("PDF-ul are semnătură digitală; unealta asta ar strica-o. Folosește o copie nesemnată.")


# ---------- unelte ----------

def merge(path, f):
    """PDF-ul deschis + celelalte, în ordinea aleasă."""
    files = [p for p in f.get("files") or [] if p]
    if not files:
        raise ValueError("Adaugă PDF-urile de lipit după cel deschis.")
    src = Path(path)
    out = fitz.open(stream=src.read_bytes(), filetype="pdf")
    for p in files:
        with open_pdf(p) as d:
            out.insert_pdf(d)
    return {"kind": "pdf", "out": str(save(out, next_to(src, "unit")))}


def split(path, f):
    """Câte un PDF pentru fiecare bucată: „1-3, 4-6” sau fiecare pagină."""
    src = Path(path)
    doc = open_pdf(path)
    n = len(doc)
    if f.get("mode") == "each":
        groups = [[i] for i in range(n)]
    else:
        groups = []
        for part in re.split(r"[,;]+", f.get("ranges") or ""):
            if part.strip():
                groups.append(pages_of(part, n))
        if not groups:
            raise ValueError("Scrie bucățile, ex. 1-3, 4-6, 7-")
    folder = free_name(src.parent, f"{src.stem}_impartit", "")
    folder.mkdir()
    files = []
    for k, g in enumerate(groups, 1):
        part = fitz.open()
        for i in g:
            part.insert_pdf(doc, from_page=i, to_page=i)
        label = f"p{g[0] + 1}" if len(g) == 1 else f"p{g[0] + 1}-{g[-1] + 1}"
        files.append(save(part, folder / f"{src.stem}_{k:02d}_{label}.pdf").name)
    return {"kind": "folder", "out": str(folder), "files": files}


def extract(path, f):
    src = Path(path)
    doc = open_pdf(path)
    keep = pages_of(f.get("pages"), len(doc))
    doc.select(keep)
    return {"kind": "pdf", "out": str(save(doc, next_to(src, "extras")))}


def remove_pages(path, f):
    src = Path(path)
    doc = open_pdf(path)
    warn_signed(doc)
    drop = set(pages_of(f.get("pages"), len(doc)))
    keep = [i for i in range(len(doc)) if i not in drop]
    if not keep:
        raise ValueError("Nu pot șterge toate paginile.")
    doc.select(keep)
    return {"kind": "pdf", "out": str(save(doc, next_to(src, "fara-pagini")))}


def remove_blanks(path, f):
    """Paginile fără text și aproape albe (scanări goale incluse)."""
    src = Path(path)
    doc = open_pdf(path)
    warn_signed(doc)
    keep = [page.number for page in doc if page.get_text().strip() or not _almost_white(page)]
    gone = len(doc) - len(keep)
    if not gone:
        return {"kind": "report", "lines": ["Nu am găsit pagini goale."]}
    if not keep:
        raise ValueError("Toate paginile par goale; nu șterg nimic.")
    doc.select(keep)
    return {"kind": "pdf", "out": str(save(doc, next_to(src, "fara-goale"))), "lines": [f"Am scos {gone} pagini goale."]}


def _almost_white(page) -> bool:
    pix = page.get_pixmap(matrix=fitz.Matrix(0.3, 0.3), colorspace=fitz.csGRAY)
    dark = sum(1 for b in pix.samples if b < 200)
    return dark < len(pix.samples) * 0.002


def rotate(path, f):
    src = Path(path)
    doc = open_pdf(path)
    warn_signed(doc)
    angle = int(f.get("angle") or 90)
    for i in pages_of(f.get("pages"), len(doc)):
        doc[i].set_rotation((doc[i].rotation + angle) % 360)
    return {"kind": "pdf", "out": str(save(doc, next_to(src, "rotit")))}


def compress(path, f):
    """Imaginile reduse la rezoluția aleasă (JPEG), fonturile și obiectele nefolosite scoase."""
    src = Path(path)
    doc = open_pdf(path)
    warn_signed(doc)
    level = f.get("level") or "mediu"
    dpi, quality = {"usor": (200, 85), "mediu": (150, 75), "puternic": (100, 60)}.get(level, (150, 75))
    before = src.stat().st_size
    try:
        doc.rewrite_images(dpi_threshold=dpi + 20, dpi_target=dpi, quality=quality, lossy=True, lossless=True, bitonal=True, color=True, gray=True)
    except TypeError:  # versiuni mai vechi de PyMuPDF
        doc.rewrite_images(dpi_threshold=dpi + 20, dpi_target=dpi, quality=quality)
    try:
        doc.subset_fonts()
    except Exception:
        pass
    target = save(doc, next_to(src, "comprimat"), garbage=4, clean=True, use_objstms=1)
    after = target.stat().st_size
    if after >= before:
        target.unlink()
        return {"kind": "report", "lines": [f"PDF-ul e deja mic ({before // 1024} KB): comprimarea nu l-a micșorat."]}
    return {"kind": "pdf", "out": str(target),
            "lines": [f"{before // 1024} KB → {after // 1024} KB ({100 - after * 100 // before}% mai mic)."]}


def to_word(path, f):
    from pdf2docx import Converter
    src = Path(path)
    target = next_to(src, "word", ".docx")
    pw = f.get("password") or None
    cv = Converter(str(src), password=pw) if pw else Converter(str(src))
    try:
        cv.convert(str(target), multi_processing=False)
    finally:
        cv.close()
    return {"kind": "file", "out": str(target)}


def to_excel(path, f):
    """Tabelele găsite pe pagini, câte o foaie pentru fiecare; fără tabele, textul paginii pe rânduri."""
    from openpyxl import Workbook
    src = Path(path)
    doc = open_pdf(path)
    wb = Workbook()
    wb.remove(wb.active)
    found = 0
    for page in doc:
        try:
            tables = page.find_tables().tables
        except Exception:
            tables = []
        for k, t in enumerate(tables, 1):
            ws = wb.create_sheet(f"Pag{page.number + 1}" + (f"-{k}" if len(tables) > 1 else ""))
            for row in t.extract():
                ws.append([_cell(v) for v in row])
            found += 1
    if not found:
        ws = wb.create_sheet("Text")
        for page in doc:
            for line in page.get_text().splitlines():
                ws.append([_cell(x) for x in re.split(r"\s{2,}|\t", line.strip())])
    target = next_to(src, "excel", ".xlsx")
    wb.save(str(target))
    note = f"Am găsit {found} tabele." if found else "N-am găsit tabele: am pus textul pe rânduri."
    return {"kind": "file", "out": str(target), "lines": [note]}


def _cell(v):
    """Numerele românești (1.234,56) devin numere în Excel; restul rămân text."""
    if v is None:
        return None
    s = str(v).replace("\n", " ").strip()
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})*(,\d+)?|-?\d+(,\d+)?", s):
        try:
            return float(s.replace(".", "").replace(",", "."))
        except ValueError:
            pass
    return s


def to_text(path, f):
    src = Path(path)
    doc = open_pdf(path)
    target = next_to(src, "text", ".txt")
    target.write_text("\n\n".join(p.get_text() for p in doc), encoding="utf-8")
    return {"kind": "file", "out": str(target)}


def to_images(path, f):
    src = Path(path)
    doc = open_pdf(path)
    fmt = "jpg" if f.get("format") == "jpg" else "png"
    dpi = int(f.get("dpi") or 150)
    folder = free_name(src.parent, f"{src.stem}_imagini", "")
    folder.mkdir()
    files = []
    for i in pages_of(f.get("pages"), len(doc)):
        pix = doc[i].get_pixmap(dpi=dpi, alpha=False)
        name = f"{src.stem}_p{i + 1:03d}.{fmt}"
        if fmt == "jpg":
            (folder / name).write_bytes(pix.tobytes("jpg", jpg_quality=88))
        else:
            pix.save(str(folder / name))
        files.append(name)
    return {"kind": "folder", "out": str(folder), "files": files}


def from_images(path, f):
    """Imaginile alese, câte una pe pagină (A4, sau mărimea imaginii)."""
    imgs = [p for p in f.get("files") or [] if p]
    if not imgs:
        raise ValueError("Alege imaginile.")
    out = fitz.open()
    a4 = f.get("page") != "image"
    for p in imgs:
        with fitz.open(p) as img:
            rect = img[0].rect
            pdf = fitz.open("pdf", img.convert_to_pdf())
        if a4:
            page = out.new_page(width=595.28, height=841.89) if rect.height >= rect.width else out.new_page(width=841.89, height=595.28)
            page.show_pdf_page(page.rect + (24, 24, -24, -24), pdf, 0, keep_proportion=True)
        else:
            out.insert_pdf(pdf)
    first = Path(imgs[0])
    return {"kind": "pdf", "out": str(save(out, free_name(first.parent, f"{first.stem}_pdf" if len(imgs) == 1 else "imagini", ".pdf")))}


OFFICE_PS = r"""
$ErrorActionPreference = 'Stop'
$src = $env:FX_SRC; $dst = $env:FX_DST
$ext = [IO.Path]::GetExtension($src).ToLower()
if ('.doc', '.docx', '.rtf', '.odt', '.txt', '.docm', '.dot', '.dotx' -contains $ext) {
  $app = New-Object -ComObject Word.Application; $app.Visible = $false; $app.DisplayAlerts = 0
  try { $d = $app.Documents.Open($src, $false, $true); $d.ExportAsFixedFormat($dst, 17); $d.Close(0) } finally { $app.Quit() }
} elseif ('.xls', '.xlsx', '.xlsm', '.csv', '.ods' -contains $ext) {
  $app = New-Object -ComObject Excel.Application; $app.Visible = $false; $app.DisplayAlerts = $false
  try { $w = $app.Workbooks.Open($src, 0, $true); $w.ExportAsFixedFormat(0, $dst); $w.Close($false) } finally { $app.Quit() }
} elseif ('.ppt', '.pptx', '.odp' -contains $ext) {
  $app = New-Object -ComObject PowerPoint.Application
  try { $p = $app.Presentations.Open($src, $true, $false, $false); $p.SaveAs($dst, 32); $p.Close() } finally { $app.Quit() }
} else { throw "Tip de fișier necunoscut: $ext" }
"""


def office_to_pdf(path, f):
    """Word / Excel / PowerPoint -> PDF cu Microsoft Office (dacă e instalat), altfel cu Stirling + LibreOffice."""
    files = [p for p in f.get("files") or [] if p]
    if not files:
        raise ValueError("Alege fișierele Word, Excel sau PowerPoint.")
    outs, errors = [], []
    for p in files:
        src = Path(p)
        dst = free_name(src.parent, src.stem, ".pdf")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", OFFICE_PS], capture_output=True,
                           timeout=300, creationflags=NO_WINDOW, env={**os.environ, "FX_SRC": str(src), "FX_DST": str(dst)})
        if r.returncode == 0 and dst.exists():
            outs.append(str(dst))
            continue
        err = r.stderr.decode("utf-8", "replace")
        if "80040154" in err or "Class not registered" in err:
            raise RuntimeError("Pentru Word/Excel → PDF trebuie Microsoft Office instalat (sau Stirling PDF cu LibreOffice: "
                               "„Word, Excel, orice fișier → PDF (Stirling)” din Unelte).")
        errors.append(f"{src.name}: {err.strip().splitlines()[-1] if err.strip() else 'eroare'}")
    if not outs:
        raise RuntimeError("; ".join(errors))
    res = {"kind": "pdf" if len(outs) == 1 else "folder", "out": outs[0] if len(outs) == 1 else str(Path(outs[0]).parent),
           "files": [Path(o).name for o in outs]}
    if errors:
        res["lines"] = errors
    return res


def protect(path, f):
    src = Path(path)
    pw = f.get("password") or ""
    if len(pw) < 4:
        raise ValueError("Parola trebuie să aibă cel puțin 4 caractere.")
    doc = open_pdf(path)
    warn_signed(doc)
    perm = fitz.PDF_PERM_ACCESSIBILITY | fitz.PDF_PERM_PRINT | fitz.PDF_PERM_PRINT_HQ
    if f.get("allowCopy"):
        perm |= fitz.PDF_PERM_COPY
    target = next_to(src, "parola")
    tmp = target.with_name(f".{target.stem}.tmp.pdf")
    doc.save(str(tmp), garbage=3, deflate=True, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw=pw,
             owner_pw=f.get("ownerPassword") or pw + "-owner", permissions=perm)
    os.replace(tmp, target)
    return {"kind": "file", "out": str(target), "lines": ["PDF-ul se deschide doar cu parola. Păstreaz-o: nu se poate recupera."]}


def unprotect(path, f):
    src = Path(path)
    doc = open_pdf(path, f.get("password") or "")
    target = next_to(src, "fara-parola")
    tmp = target.with_name(f".{target.stem}.tmp.pdf")
    doc.save(str(tmp), garbage=3, deflate=True, encryption=fitz.PDF_ENCRYPT_NONE)
    os.replace(tmp, target)
    return {"kind": "pdf", "out": str(target)}


def watermark(path, f):
    """Text în diagonală peste fiecare pagină, semi-transparent."""
    text = (f.get("text") or "").strip()
    if not text:
        raise ValueError("Scrie textul watermark-ului.")
    src = Path(path)
    doc = open_pdf(path)
    warn_signed(doc)
    opacity = max(0.05, min(1.0, float(f.get("opacity") or 25) / 100))
    color = fx_sign.hex_rgb(f.get("color") or "#888888")
    font = fx_sign.font_file("arial", True, False)
    fobj = fitz.Font(fontfile=font)
    for i in pages_of(f.get("pages"), len(doc)):
        page = doc[i]
        r = page.rect
        # fără mărime aleasă: textul acoperă cam trei sferturi din diagonala paginii
        size = float(f.get("size") or min(120, 0.72 * abs(r.br - r.tl) / max(1, fobj.text_length(text, fontsize=1))))
        width = fobj.text_length(text, fontsize=size)
        # pe diagonală, de jos-stânga în sus-dreapta, centrat; morph rotește în jurul punctului de start
        r = page.rect if not page.rotation else fitz.Rect(0, 0, *(page.rect * page.rotation_matrix).br)
        c = fitz.Point(r.width / 2, r.height / 2)
        start = c + (-width / 2 * 0.7071 + size * 0.25, width / 2 * 0.7071 + size * 0.25)
        p0 = start * page.derotation_matrix
        page.insert_text(p0, text, fontsize=size, fontname="fxwm", fontfile=font, color=color, fill_opacity=opacity,
                         morph=(p0, fitz.Matrix(45 - page.rotation)), overlay=True)
    doc.subset_fonts()
    return {"kind": "pdf", "out": str(save(doc, next_to(src, "watermark")))}


def page_numbers(path, f):
    src = Path(path)
    doc = open_pdf(path)
    warn_signed(doc)
    fmt = f.get("format") or "{n}"
    start = int(f.get("start") or 1)
    pos = f.get("position") or "jos-centru"
    size = float(f.get("size") or 10)
    font = fx_sign.font_file("arial", False, False)
    fobj = fitz.Font(fontfile=font)
    chosen = pages_of(f.get("pages"), len(doc))
    total = len(chosen) + start - 1
    for k, i in enumerate(chosen):
        page = doc[i]
        r = page.rect * page.rotation_matrix if page.rotation else page.rect  # pagina cum se vede
        r = fitz.Rect(0, 0, r.width, r.height)
        label = fmt.replace("{n}", str(k + start)).replace("{N}", str(total))
        w = fobj.text_length(label, fontsize=size)
        x = {"stanga": 36, "dreapta": r.width - 36 - w}.get(pos.split("-")[-1], (r.width - w) / 2)
        y = 28 + size if pos.startswith("sus") else r.height - 24
        pt = fitz.Point(x, y) * page.derotation_matrix
        page.insert_text(pt, label, fontsize=size, fontname="fxpn", fontfile=font, color=(0.15, 0.15, 0.15), rotate=page.rotation)
    doc.subset_fonts()
    return {"kind": "pdf", "out": str(save(doc, next_to(src, "numerotat")))}


def flatten(path, f):
    """Câmpurile și adnotările devin parte din pagină (nu se mai pot modifica)."""
    src = Path(path)
    doc = open_pdf(path)
    warn_signed(doc)
    doc.bake(annots=True, widgets=True)
    return {"kind": "pdf", "out": str(save(doc, next_to(src, "aplatizat")))}


def repair(path, f):
    src = Path(path)
    doc = fitz.open(str(src))  # MuPDF reconstruiește tabela de obiecte la deschidere, dacă e stricată
    return {"kind": "pdf", "out": str(save(doc, next_to(src, "reparat"), garbage=4, clean=True))}


def extract_images(path, f):
    src = Path(path)
    doc = open_pdf(path)
    folder = free_name(src.parent, f"{src.stem}_imagini-extrase", "")
    files, seen = [], set()
    for page in doc:
        for img in page.get_images(full=True):
            xref = img[0]
            if xref in seen:
                continue
            seen.add(xref)
            data = doc.extract_image(xref)
            if not data or data.get("width", 0) < 32:
                continue
            folder.mkdir(exist_ok=True)
            name = f"p{page.number + 1:03d}_{xref}.{data['ext']}"
            (folder / name).write_bytes(data["image"])
            files.append(name)
    if not files:
        return {"kind": "report", "lines": ["PDF-ul nu are imagini."]}
    return {"kind": "folder", "out": str(folder), "files": files}


def validate_signatures(path, f):
    """Cine a semnat, când, cu ce certificat, și dacă fișierul a rămas neschimbat după semnătură."""
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    lines = []
    with open(path, "rb") as fh:
        reader = PdfFileReader(fh, strict=False)
        sigs = reader.embedded_signatures
        if not sigs:
            return {"kind": "report", "lines": ["PDF-ul nu are semnături digitale."]}
        for k, s in enumerate(sigs, 1):
            try:
                st = validate_pdf_signature(s)
                cert = s.signer_cert
                who = cert.subject.native.get("common_name", "?")
                issuer = cert.issuer.native.get("common_name", "?")
                when = s.self_reported_timestamp
                ok = st.intact and st.valid
                cover = "tot fișierul" if st.coverage.name == "ENTIRE_FILE" else "versiunea de atunci (după ea s-au adăugat alte semnături sau completări)"
                lines.append(f"{k}. {who}: {'semnătură validă' if ok else 'SEMNĂTURĂ INVALIDĂ'}, " +
                             (f"semnat {when:%d.%m.%Y %H:%M}, " if when else "") + f"emis de {issuer}, acoperă {cover}.")
                if not st.trusted:
                    lines.append("   Certificatul nu e verificat aici față de o autoritate de încredere (lista oficială); Adobe face asta.")
            except Exception as err:
                lines.append(f"{k}. {s.field_name}: nu am putut verifica ({err}).")
    return {"kind": "report", "lines": lines}


def info(path, f):
    src = Path(path)
    doc = open_pdf(path)
    meta = doc.metadata or {}
    lines = [f"Fișier: {src.name} ({src.stat().st_size // 1024} KB)", f"Pagini: {len(doc)}",
             f"Versiune: {meta.get('format', '')}", f"Criptat: {'da' if doc.is_encrypted else 'nu'}",
             f"Formular: {'XFA (ANAF)' if fx_sign.is_xfa(doc) else 'da' if doc.is_form_pdf else 'nu'}",
             f"Semnat digital: {'da' if fx_sign.is_signed(doc) else 'nu'}",
             f"Atașamente: {', '.join(doc.embfile_names()) or 'nu'}"]
    for k in ("title", "author", "subject", "creator", "producer", "creationDate", "modDate"):
        if meta.get(k):
            lines.append(f"{k}: {meta[k]}")
    return {"kind": "report", "lines": lines}


TOOLS = {
    "merge": merge, "split": split, "extract": extract, "removepages": remove_pages, "removeblanks": remove_blanks,
    "rotate": rotate, "compress": compress, "toword": to_word, "toexcel": to_excel, "totext": to_text, "toimg": to_images,
    "fromimg": from_images, "fromoffice": office_to_pdf, "password": protect, "unpassword": unprotect, "watermark": watermark,
    "pagenumbers": page_numbers, "flatten": flatten, "repair": repair, "images": extract_images,
    "validatesign": validate_signatures, "info": info,
}


def run(tool: str, path: str, fields: dict) -> dict:
    fn = TOOLS.get(tool)
    if not fn:
        raise ValueError(f"Unealtă necunoscută: {tool}")
    return {"ok": True, **fn(path, fields or {})}
