"""Helper-ul mod-ului pdf-sign: preview-uri PDF și semnături ca SVG pentru cardul din chat,
plus partea comună cu editorul (scrierea semnăturilor, textelor și modificărilor de text în PDF).

  python fx_sign.py render PDF PAGE [ZOOM]   -> JSON {pages, page, svg, signed}
  python fx_sign.py thumbs DIR               -> JSON [{name, file, svg}]
  python fx_sign.py undo PDF                 -> pune la loc versiunea de dinainte de ultima salvare
  python fx_sign.py serve [LIBRARY]          -> serverul editorului (vezi editor_server.py); evenimente JSON pe stdout
  python fx_sign.py paths                    -> JSON {state, library, local}: unde stau jurnalele și semnăturile
  python fx_sign.py window URL               -> deschide URL-ul într-o fereastră Edge separată (rezerva panoului)

Semnătura se pune ca în semnare-pdf/place_signature.py: imagine PNG transparentă peste pagină,
fără să atingă un PDF care are deja semnătură digitală.
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# PyMuPDF 2.x încarcă singur pymupdf.layout și pymupdf4llm (onnxruntime, ~3 s) dacă sunt instalate; nu le folosim,
# iar cardul din chat pornește helperul la fiecare preview. Un modul pus pe None în sys.modules dă ImportError.
sys.modules.setdefault("pymupdf.layout", None)
sys.modules.setdefault("pymupdf4llm", None)
import fitz  # noqa: E402  PyMuPDF

fitz.TOOLS.mupdf_display_errors(False)
MM = 72 / 25.4
SVG_LIMIT = 118000  # Svg-ul din chat are voie la 131072 caractere
# FX_STATE: alt folder de stare, pentru teste (ca să nu atingă setările omului).
STATE = Path(os.environ.get("FX_STATE") or Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "fintaxy-pdf-sign")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def out(obj):
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


# ---------- preview în chat ----------

def render(pdf: str, page_no: int, zoom: float = 1.0):
    doc = fitz.open(pdf)
    n = len(doc)
    pi = min(max(page_no, 1), n) - 1
    page = doc[pi]
    w, h = page.rect.width, page.rect.height
    zoom = min(max(zoom, 0.5), 2.0)
    show_w = round((420 if w <= h else 560) * zoom)  # lățimea în chat, px CSS
    show_h = round(show_w * h / w)
    # De două ori mai mare pentru ecrane HiDPI; scade calitatea până intră în limita Svg-ului.
    for scale, quality in ((2.0, 80), (2.0, 65), (1.6, 60), (1.3, 55), (1.0, 50), (1.0, 35), (0.8, 35), (0.6, 30)):
        pix = page.get_pixmap(matrix=fitz.Matrix(show_w * scale / w, show_w * scale / w), alpha=False)
        img = b64(pix.tobytes("jpg", jpg_quality=quality))
        if len(img) < SVG_LIMIT - 600:
            break
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{show_w}" height="{show_h}" '
        f'viewBox="0 0 {show_w} {show_h}">'
        f'<rect width="{show_w}" height="{show_h}" fill="#fff"/>'
        f'<image href="data:image/jpeg;base64,{img}" width="{show_w}" height="{show_h}"/>'
        f'<rect x="0.5" y="0.5" width="{show_w - 1}" height="{show_h - 1}" fill="none" stroke="#d9dce3"/>'
        "</svg>"
    )
    out({"pages": n, "page": pi + 1, "width": show_w, "height": show_h, "svg": svg,
         "signed": is_signed(doc)})


# ---------- câmpuri de semnătură și formulare ----------

def signature_fields(doc) -> list:
    """Câmpurile de semnătură ale PDF-ului (ex. „Semnătura” din declarațiile ANAF): nume, pagină, loc (pt, pagina cum
    se vede), semnat sau nu."""
    found = []
    for page in doc:
        for w in page.widgets(types=[fitz.PDF_WIDGET_TYPE_SIGNATURE]):
            v = doc.xref_get_key(w.xref, "V")
            if v[0] == "null":  # câmp combinat cu un părinte: valoarea e la părinte
                parent = doc.xref_get_key(w.xref, "Parent")
                if parent[0] == "xref":
                    v = doc.xref_get_key(int(parent[1].split()[0]), "V")
            r = w.rect * page.rotation_matrix
            found.append({"name": w.field_name or "", "page": page.number + 1, "rect": [r.x0, r.y0, r.x1, r.y1],
                          "signed": v[0] not in ("null", ""), "visible": r.width > 1 and r.height > 1})
    return found


def is_signed(doc) -> bool:
    """Are o semnătură digitală pusă. Un câmp de semnătură gol (formularele, declarațiile ANAF nesemnate) nu contează:
    SigFlags îl marchează și pe el, dar PDF-ul se poate încă completa și semna."""
    if doc.get_sigflags() <= 0:
        return False
    try:
        return any(f["signed"] for f in signature_fields(doc))
    except Exception:
        return True


def is_xfa(doc) -> bool:
    """Formular XFA (Adobe LiveCycle): așa sunt PDF-urile inteligente ale ANAF (D100, D112, D300...)."""
    return doc.xref_get_key(doc.pdf_catalog(), "AcroForm/XFA")[0] not in ("null", "")


FIELD_KINDS = {fitz.PDF_WIDGET_TYPE_TEXT: "text", fitz.PDF_WIDGET_TYPE_CHECKBOX: "check",
               fitz.PDF_WIDGET_TYPE_RADIOBUTTON: "radio", fitz.PDF_WIDGET_TYPE_COMBOBOX: "combo",
               fitz.PDF_WIDGET_TYPE_LISTBOX: "list"}


def form_fields(page) -> list:
    """Câmpurile de completat de pe pagină, cu locul lor în pagina cum se vede."""
    items = []
    for w in page.widgets():
        kind = FIELD_KINDS.get(w.field_type)
        if not kind:
            continue
        r = w.rect * page.rotation_matrix
        it = {"xref": w.xref, "name": w.field_name or "", "label": w.field_label or "", "kind": kind,
              "rect": [r.x0, r.y0, r.x1, r.y1], "readonly": bool(w.field_flags & 1),
              "fs": w.text_fontsize or 0}
        if kind == "text":
            it.update(value=str(w.field_value or ""), multiline=bool(w.field_flags & (1 << 12)), maxlen=w.text_maxlen or 0)
        elif kind in ("check", "radio"):
            on = w.on_state()
            on = on if isinstance(on, str) and on else "Yes"
            it.update(on=on, value=w.field_value is True or str(w.field_value) == on)
        else:
            it.update(value=str(w.field_value or ""), options=[o if isinstance(o, str) else o[1] for o in (w.choice_values or [])])
        items.append(it)
    return items


def fill_fields(doc, fills: list):
    """fills: [{page, xref, value}] din editor; textele și listele primesc textul, bifele True/False."""
    by_page = {}
    for f in fills:
        by_page.setdefault(int(f["page"]), {})[int(f["xref"])] = f["value"]
    for pno, values in by_page.items():
        for w in doc[pno - 1].widgets():
            if w.xref not in values:
                continue
            v = values[w.xref]
            if w.field_type in (fitz.PDF_WIDGET_TYPE_CHECKBOX, fitz.PDF_WIDGET_TYPE_RADIOBUTTON):
                on = w.on_state()
                w.field_value = (on if isinstance(on, str) and on else True) if v else "Off"
            else:
                w.field_value = str(v)
            w.update()


def label_of(path: Path) -> str:
    name = path.stem
    for prefix in ("Semnatura ", "Semnătura ", "Semnatura_", "Semnătura_"):
        if name.lower().startswith(prefix.lower()):
            return name[len(prefix):].strip() or name
    return name


def default_library() -> str:
    """Folderul cu semnături: „library” din settings.json, altfel Documente\\Semnaturi PDF Sign (creat la nevoie)."""
    try:
        lib = json.loads((STATE / "settings.json").read_text(encoding="utf-8")).get("library")
    except (OSError, ValueError):
        lib = None
    if not lib:
        docs = Path.home() / "Documents"
        try:  # Documentele pot fi mutate (OneDrive, alt disc)
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
                docs = Path(os.path.expandvars(winreg.QueryValueEx(k, "Personal")[0]))
        except OSError:
            pass
        lib = str(docs / "Semnaturi PDF Sign")
    try:
        Path(lib).mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return lib


def library(folder: str) -> list:
    return sorted(Path(folder).glob("*.png"), key=lambda x: label_of(x).lower()) if folder else []


def thumbs(folder: str):
    items = []
    for p in library(folder):
        try:
            pix = fitz.Pixmap(str(p))
            if pix.alpha == 0:
                pix = fitz.Pixmap(pix, 1)
            # Mică (desktopul nu mai redesenează un card prea mare), încape într-un 170x60.
            k = min(170 / pix.width, 60 / pix.height, 1)
            small = fitz.Pixmap(pix, max(1, int(pix.width * k)), max(1, int(pix.height * k)), None)
            data = b64(small.tobytes("png"))
            tw, th = small.width, small.height
            W, H = 200, 76
            x, y = (W - tw) / 2, (H - th) / 2
            svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
                f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="#fff" stroke="#e3e6ec"/>'
                f'<image href="data:image/png;base64,{data}" x="{x:.1f}" y="{y:.1f}" width="{tw}" height="{th}"/>'
                "</svg>"
            )
            items.append({"name": label_of(p), "file": str(p), "svg": svg})
        except Exception as err:  # o imagine stricată nu oprește lista
            items.append({"name": label_of(p), "file": str(p), "svg": "", "error": str(err)})
    out(items)


# ---------- scrierea în PDF ----------

FONTS_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
# Fonturile Windows cu diacritice românești: normal, bold, italic, bold italic.
FONTS = {
    "arial": ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
    "times": ("times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"),
    "calibri": ("calibri.ttf", "calibrib.ttf", "calibrii.ttf", "calibriz.ttf"),
    "cour": ("cour.ttf", "courbd.ttf", "couri.ttf", "courbi.ttf"),
    "georgia": ("georgia.ttf", "georgiab.ttf", "georgiai.ttf", "georgiaz.ttf"),
    "verdana": ("verdana.ttf", "verdanab.ttf", "verdanai.ttf", "verdanaz.ttf"),
    "tahoma": ("tahoma.ttf", "tahomabd.ttf", "tahoma.ttf", "tahomabd.ttf"),
    "segoe": ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"),
    "cambria": ("cambria.ttc", "cambriab.ttf", "cambriai.ttf", "cambriaz.ttf"),
}


def font_key(name: str) -> str:
    n = (name or "").lower()
    for key, words in (("times", ("times", "garamond", "antiqua", "serif")), ("calibri", ("calibri",)),
                       ("cour", ("courier", "cour", "mono")), ("georgia", ("georgia",)), ("verdana", ("verdana",)),
                       ("tahoma", ("tahoma",)), ("segoe", ("segoe",)), ("cambria", ("cambria",))):
        if any(w in n for w in words) and not (key == "times" and "sans" in n):
            return key
    return "arial"


def font_file(key: str, bold: bool, italic: bool) -> str:
    files = FONTS.get(key, FONTS["arial"])
    f = FONTS_DIR / files[(1 if bold else 0) + (2 if italic else 0)]
    if not f.exists():
        f = FONTS_DIR / files[0]
    if not f.exists():
        f = FONTS_DIR / "arial.ttf"
    return str(f)


# Fonturile instalate, după nume: Windows, ale utilizatorului și cele aduse de LibreOffice (DejaVu, Liberation...).
FONT_DIRS = [FONTS_DIR, Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts",
             Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "LibreOffice" / "share" / "fonts" / "truetype"]
_FONT_INDEX = None


def norm_font(name: str) -> str:
    """„ABCDEF+TimesNewRomanPS-BoldMT”, „Times New Roman Bold” -> „timesnewromanbold”."""
    n = re.sub(r"^[A-Z]{6}\+", "", name or "")
    n = re.sub(r"[^a-z0-9]", "", n.lower())
    n = re.sub(r"(psmt|mt|ps)(?=(bold|italic|oblique)*$)", "", n)
    return re.sub(r"regular$", "", n)


def font_index() -> dict:
    """{nume normalizat: fișier} pentru fonturile instalate; ținut în font-index.json cât timp nu se schimbă fonturile."""
    global _FONT_INDEX
    if _FONT_INDEX is None:
        files = sorted(str(f) for d in FONT_DIRS if d.is_dir() for f in d.iterdir() if f.suffix.lower() in (".ttf", ".otf", ".ttc"))
        sig = hashlib.sha1("\n".join(files).encode("utf-8")).hexdigest()
        cache = STATE / "font-index.json"
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data["sig"] != sig:
                raise ValueError
            _FONT_INDEX = data["index"]
        except (OSError, ValueError, KeyError):
            idx = {}
            for f in files:
                try:
                    name = fitz.Font(fontfile=f).name
                except Exception:
                    continue
                for key in (norm_font(name), norm_font(Path(f).stem)):
                    idx.setdefault(key, f)
            STATE.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"sig": sig, "index": idx}), encoding="utf-8")
            _FONT_INDEX = idx
    return _FONT_INDEX


def embedded_fonts(page) -> dict:
    """{nume normalizat: xref} pentru fonturile încorporate folosite pe pagină."""
    return {norm_font(f[3]): f[0] for f in page.get_fonts(full=True) if f[1] not in ("n/a", "")}


def font_refs(doc, name: str, embedded: dict) -> dict:
    """Unde găsim fontul unui segment: încorporat în PDF (x:xref) și/sau instalat (calea fișierului)."""
    key = norm_font(name)
    xref = embedded.get(key)
    ext = doc.extract_font(xref)[1] if xref else ""
    return {"embedded": f"x:{xref}" if xref else None, "embeddedWeb": ext in ("ttf", "otf"), "system": font_index().get(key)}


def font_chain(doc, seg: dict) -> list:
    """Fonturile pentru textul nou al unui segment, în ordinea preferinței: cel din PDF (de obicei doar cu literele
    folosite deja), același font instalat, apoi cel mai apropiat font Windows. Fiecare literă ia primul care o are."""
    chain = []
    refs = seg.get("fonts") or {}
    if str(refs.get("embedded") or "").startswith("x:"):
        buf = doc.extract_font(int(refs["embedded"][2:]))[3]
        if buf:
            try:
                chain.append(("x" + hashlib.sha1(buf).hexdigest()[:8], fitz.Font(fontbuffer=buf), {"fontbuffer": buf}))
            except Exception:
                pass
    files = [refs["system"]] if refs.get("system") in font_index().values() else []
    files.append(font_file(seg.get("font", "arial"), bool(seg.get("bold")), bool(seg.get("italic"))))
    for f in files:
        try:
            chain.append(("fx" + hashlib.sha1(f.encode()).hexdigest()[:6], fitz.Font(fontfile=f), {"fontfile": f}))
        except Exception:
            pass
    return chain


def write_line(page, segments: list, chains: list, scale: float = 1.0, dry: bool = False) -> float:
    """Scrie un rând editat: segmentele unul după altul, cu spațiul de dinainte dintre ele; întoarce unde se termină.
    Coordonatele sunt cele din pagina nerotită, în direcția textului (dir = 1, 0). dry: doar măsoară."""
    x, prev_end = None, None
    for sg, chain in zip(segments, chains):
        ox, oy = sg["origin"]
        x = ox if x is None else x + max(0.0, ox - prev_end) * scale
        prev_end = sg["raw"][2]
        txt = str(sg.get("text", "")).replace(" ", " ")
        if txt and chain:
            x = write_segment(page, chain, x, oy, txt, float(sg["size"]) * scale, hex_rgb(sg.get("color")), dry)
    return x if x is not None else 0.0


def write_segment(page, chain: list, x: float, y: float, text: str, size: float, color, dry: bool = False) -> float:
    """Scrie textul de la (x, y) pe linia de bază, literă cu literă din primul font care o are; întoarce unde se termină."""
    chunks = []
    for ch in text:
        k = next((i for i, (_n, f, _a) in enumerate(chain) if f.has_glyph(ord(ch))), len(chain) - 1)
        if chunks and chunks[-1][0] == k:
            chunks[-1][1] += ch
        else:
            chunks.append([k, ch])
    for k, chunk in chunks:
        name, font, args = chain[k]
        if not dry:
            page.insert_font(fontname=name, **args)
            page.insert_text(fitz.Point(x, y), chunk, fontsize=size, fontname=name, color=color)
        x += font.text_length(chunk, fontsize=size)
    return x


def home_dir(pdf: Path) -> Path:
    """Folderul în care se scriu copiile unui PDF. De obicei al lui; pentru PDF-ul de citit al unui fișier Markdown
    (bin/mdview.py, ținut în STATE/md) e folderul .md-ului, ca omul să-și găsească fișierul lângă original."""
    pdf = Path(pdf)
    try:
        if pdf.parent.parent.resolve() == (STATE / "md").resolve():
            return Path(json.loads((pdf.parent / "origin.json").read_text(encoding="utf-8"))["source"]).parent
    except (OSError, ValueError, KeyError):
        pass
    return pdf.parent


def output_path(pdf: Path, signed: bool = True) -> Path:
    stem = pdf.stem
    if stem.lower().endswith(("_semnat", "_editat")):
        return pdf  # a doua trecere: scriem peste copia noastră
    return home_dir(pdf) / f"{stem}_{'semnat' if signed else 'editat'}.pdf"


def backup_path(target: Path) -> Path:
    (STATE / "undo").mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(str(target).lower().encode("utf-8")).hexdigest()[:16]
    return STATE / "undo" / f"{key}.pdf"


def hex_rgb(color: str):
    c = (color or "#141720").lstrip("#")
    if len(c) != 6:
        c = "141720"
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def stamp(pdf: Path, items: list, sigs: list, rotate: dict | None = None) -> Path:
    """Scrie în PDF ce s-a pus în editor. Pozițiile vin în pt, în pagina așa cum se vede (rotită).

    rotate: {pages: [n, ...], angle: ±90} se aplică la sfârșit, după ce elementele s-au scris în pagina de dinainte.

    items: {type: 'sig', page, x, y, w, sig}         semnătură (x, y = colțul stânga-sus, w = lățimea)
           {type: 'text', page, x, y, fs, text, ...} text nou (y = partea de sus a primului rând)
           {type: 'edit', page, raw, segments: [{text, raw, origin, size, font, bold, italic, color, fonts}]}
               un rând existent rescris; segmentele se scriu unul după altul, cu spațiile dintre ele de dinainte
           {type: 'field', page, xref, value}       un câmp de formular completat
    """
    doc = fitz.open(stream=pdf.read_bytes(), filetype="pdf")  # din memorie: putem scrie peste același fișier
    if is_signed(doc):
        raise ValueError("PDF-ul are deja o semnătură digitală; orice modificare acum o invalidează.")
    target = output_path(pdf, signed=any(it.get("type") == "sig" for it in items))
    bak = backup_path(target)
    if target.exists():
        shutil.copy2(target, bak)
    elif bak.exists():
        bak.unlink()
    apply_items(doc, items, sigs, rotate)
    tmp = target.with_name(f".{target.stem}.tmp.pdf")
    doc.save(str(tmp), garbage=3, deflate=True)
    doc.close()
    try:
        os.replace(tmp, target)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return target


def apply_items(doc, items: list, sigs: list, rotate: dict | None = None):
    """Elementele din editor scrise în documentul deschis (în memorie); folosit la salvare și la printare."""
    # 0. Câmpurile formularului completate în editor.
    fills = [it for it in items if it.get("type") == "field"]
    if fills:
        fill_fields(doc, fills)

    # 1. Textul existent modificat: întâi se scoate (redactare fără umplere), apoi se scrie noul text.
    edits = [it for it in items if it.get("type") == "edit"]
    for pno in sorted({int(it["page"]) for it in edits}):
        page = doc[pno - 1]
        mine = [it for it in edits if int(it["page"]) == pno]
        for it in mine:
            x0, y0, x1, y1 = it["raw"]
            h = y1 - y0
            # Puțin mai mic decât rândul, ca să nu prindă literele rândurilor vecine.
            page.add_redact_annot(fitz.Rect(x0 + 0.2, y0 + h * 0.18, x1 - 0.2, y1 - h * 0.18), fill=False, cross_out=False)
        # Fonturile se citesc înainte de redactare (care poate scoate de pe pagină fonturile rămase nefolosite).
        chains = [[font_chain(doc, sg) for sg in it["segments"]] for it in mine]
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
        for it, chain in zip(mine, chains):
            # Un rând care s-a lungit peste marginea din dreapta (cât cea din stânga) se micșorează, cel mult la 80%.
            start = it["segments"][0]["origin"][0]
            limit = max(it["raw"][2], page.mediabox.width - it["raw"][0])
            end = write_line(page, it["segments"], chain, 1.0, dry=True)
            scale = 1.0 if end <= limit or end <= start else max(0.8, (limit - start) / (end - start))
            write_line(page, it["segments"], chain, scale)

    # 2. Texte noi și semnături, peste pagină.
    for it in items:
        if it.get("type") not in ("sig", "text"):
            continue
        page = doc[int(it["page"]) - 1]
        x, y = float(it["x"]), float(it["y"])
        if it["type"] == "sig":
            sig = sigs[int(it["sig"])]
            pix = fitz.Pixmap(str(sig))
            w = float(it["w"])
            rect = fitz.Rect(x, y, x + w, y + w * pix.height / pix.width)
            page.insert_image(rect * page.derotation_matrix, filename=str(sig), keep_proportion=True, overlay=True,
                              rotate=page.rotation)  # pe pagină rotită, imaginea stă dreaptă doar așa
        elif str(it.get("text", "")).strip():
            fs = float(it["fs"])
            ff = font_file(it.get("font", "arial"), bool(it.get("bold")), bool(it.get("italic")))
            for k, line in enumerate(str(it["text"]).replace("\u00a0", " ").rstrip("\n").split("\n")):
                # Linia de bază: aceeași ca în editor (line-height 1.15).
                pt = fitz.Point(x, y + fs * 0.92 + k * fs * 1.15) * page.derotation_matrix
                page.insert_text(pt, line, fontsize=fs, fontname="fx" + hashlib.sha1(ff.encode()).hexdigest()[:6],
                                 fontfile=ff, rotate=page.rotation, color=hex_rgb(it.get("color")))

    # 3. Rotirea paginilor (în sensul acelor de ceasornic pentru unghi pozitiv).
    if rotate:
        for pno in rotate.get("pages") or []:
            page = doc[int(pno) - 1]
            page.set_rotation((page.rotation + int(rotate["angle"])) % 360)

    if any(it.get("type") in ("edit", "text") for it in items):
        try:  # fontul pus de noi se încorporează întreg (~800 KB); păstrăm doar literele folosite
            doc.subset_fonts()
        except Exception:
            pass


def organize(pdf: Path, pages: list) -> Path:
    """Paginile în ordinea nouă: pages = [{n, rot}] (n = numărul de acum, rot = cât se mai rotește, ±90/180).
    Ce lipsește din listă se șterge. Rezultatul e copia _editat.pdf (Anulează pune la loc ce era)."""
    if not pages:
        raise ValueError("Trebuie să rămână cel puțin o pagină.")
    doc = fitz.open(stream=pdf.read_bytes(), filetype="pdf")
    if is_signed(doc):
        raise ValueError("PDF-ul are semnătură digitală; reordonarea paginilor ar strica-o.")
    order = [int(p["n"]) - 1 for p in pages]
    if len(set(order)) != len(order) or any(not 0 <= i < len(doc) for i in order):
        raise ValueError("Lista de pagini nu se potrivește cu PDF-ul.")
    target = output_path(pdf, signed=False)
    bak = backup_path(target)
    if target.exists():
        shutil.copy2(target, bak)
    elif bak.exists():
        bak.unlink()
    doc.select(order)
    for i, p in enumerate(pages):
        if int(p.get("rot") or 0) % 360:
            page = doc[i]
            page.set_rotation((page.rotation + int(p["rot"])) % 360)
    tmp = target.with_name(f".{target.stem}.tmp.pdf")
    doc.save(str(tmp), garbage=3, deflate=True)
    doc.close()
    os.replace(tmp, target)
    return target


def undo_file(pdf: str) -> dict:
    target = Path(pdf)
    bak = backup_path(target)
    if bak.exists():
        shutil.copy2(bak, target)
        bak.unlink()
        return {"ok": True, "out": str(target), "restored": True}
    if target.stem.lower().endswith(("_semnat", "_editat")) and target.exists():
        target.unlink()  # prima salvare: copia dispare, originalul a rămas neatins
        return {"ok": True, "out": str(target), "removed": True}
    return {"ok": False, "error": "Nu am ce anula."}


# ---------- fereastra de rezervă ----------

def browser() -> str:
    for p in (
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ):
        if os.path.exists(p):
            return p
    raise SystemExit("Nu găsesc Edge sau Chrome.")


def window(url: str):
    profile = STATE / "browser"
    profile.mkdir(parents=True, exist_ok=True)
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    # Fereastra editorului nu trebuie „adormită” când e acoperită de alte ferestre: altfel pagina nu mai dă semn de
    # viață, chatul nu mai primește răspunsul și salvările întârzie.
    args = [browser(), f"--app={url}", f"--user-data-dir={profile}", "--window-size=1100,1200",
            "--no-first-run", "--no-default-browser-check", "--disable-features=Translate,msSleepingTabs,CalculateNativeWinOcclusion",
            "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows"]
    if os.environ.get("FX_WINDOW_POS"):  # doar la teste: fereastra în afara ecranului, ca să nu deranjeze omul
        args.append(f"--window-position={os.environ['FX_WINDOW_POS']}")
    subprocess.Popen(args, close_fds=True, creationflags=flags)
    out({"ok": True})


def browser_alive() -> bool:
    """Mai e deschisă vreo fereastră a editorului? Edge ține fișierul `lockfile` din profilul aplicației deschis doar
    pentru el cât rulează; dacă îl putem deschide noi (sau nu există), nu mai rulează."""
    lock = STATE / "browser" / "lockfile"
    if not lock.exists():
        return False
    try:
        os.close(os.open(str(lock), os.O_RDWR))
        return False
    except OSError:
        return True


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    try:  # jurnal scurt, ca să se vadă ce a cerut mod-ul
        STATE.mkdir(parents=True, exist_ok=True)
        with open(STATE / "log.txt", "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " | ".join(sys.argv[1:])[:400] + "\n")
    except OSError:
        pass
    try:
        if cmd == "render":
            render(sys.argv[2], int(sys.argv[3]), float(sys.argv[4]) if len(sys.argv) > 4 else 1.0)
        elif cmd == "thumbs":
            thumbs(sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else default_library())
        elif cmd == "undo":
            out(undo_file(sys.argv[2]))
        elif cmd == "paths":  # pentru mod: unde ține aplicația jurnalele și semnăturile pe calculatorul ăsta
            out({"state": str(STATE), "library": default_library(), "local": os.environ.get("LOCALAPPDATA", "")})
        elif cmd == "serve":
            import editor_server
            editor_server.serve(sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else default_library())
        elif cmd == "window":
            window(sys.argv[2])
        else:
            raise SystemExit(__doc__)
    except SystemExit:
        raise
    except Exception as err:
        out({"ok": False, "error": f"{type(err).__name__}: {err}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
