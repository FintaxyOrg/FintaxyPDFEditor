"""Toate uneltele din editor, rulate prin API-ul serverului (ca din interfață), pe documente de test:

  A. editorul: semnătură olografă nouă în bibliotecă, salvare cu semnătură + text + text editat, anulare, formulare,
     organizarea paginilor, rotire, comentarii, printare, atașamente
  B. uneltele locale (bin/localtools.py), fiecare cu verificarea rezultatului
  C. uneltele Stirling din catalog (editor/tools.js), cu câmpurile din specificația lui

Cere serverul de test pornit:  python tests/dev_server.py FOLDER 8765
  python tests/test_tools.py FOLDER [8765] [--no-stirling] [--only=id1,id2]
Scrie FOLDER/raport-unelte.json și întoarce 1 dacă pică ceva din A sau B (C e raportat pe categorii).
"""
import base64
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import fitz

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
FOLDER = Path(sys.argv[1]).resolve()
PORT = next((a for a in sys.argv[2:] if a.isdigit()), "8765")
ONLY = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
BASE = f"http://127.0.0.1:{PORT}"
DOCS = FOLDER / "docs"
RESULTS = []


def call(method, path, body=None, q=None, timeout=600):
    url = f"{BASE}/api/{path}?" + urllib.parse.urlencode({"t": "test", **(q or {})})
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raw, ctype = e.read(), e.headers.get("Content-Type", "")
        try:
            return {"ok": False, **json.loads(raw)}
        except ValueError:
            return {"ok": False, "error": f"HTTP {e.code}"}
    return json.loads(raw) if "json" in ctype else raw


def get(_p, **q):
    return call("GET", _p, q=q)


def post(_p, **body):
    return call("POST", _p, body)


def record(section, name, ok, detail="", kind=""):
    RESULTS.append({"section": section, "name": name, "ok": bool(ok), "detail": str(detail)[:400], "kind": kind})
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  [{str(detail)[:160]}]" if detail and not ok else ""), flush=True)
    return bool(ok)


def pages(p):
    with fitz.open(str(p)) as d:
        return len(d)


def text_of(p, page=0):
    """Textul paginii. Arial scos din PDF dă spațiul ca U+00A0 și cratima ca U+00AD: le aducem la forma obișnuită."""
    with fitz.open(str(p)) as d:
        return d[page].get_text().replace(" ", " ").replace("­", "-")


def fresh(name, src="contract.pdf"):
    """O copie de lucru a unui document de test, ca uneltele să nu se calce între ele."""
    work = FOLDER / "work"
    work.mkdir(exist_ok=True)
    target = work / name
    target.write_bytes((DOCS / src).read_bytes())
    for old in work.glob(f"{target.stem}_*"):
        if old.is_file():
            old.unlink()
    return target


def b64file(p: Path, mime="application/octet-stream"):
    return {"name": p.name, "type": mime, "b64": base64.b64encode(p.read_bytes()).decode()}


# ---------------------------------------------------------------- A. editorul

def editor_tests():
    print("\n== A. editorul ==")
    S = "editor"
    info = get("info")
    record(S, "server pornit, aplicația separată", info.get("standalone") is True, info)
    doc = fresh("editor.pdf")
    d = get("doc", path=str(doc))
    record(S, "documentul se deschide: 3 pagini A4", len(d.get("pages", [])) == 3 and round(d["pages"][0]["w"]) == 595, d)
    png = get("page", path=str(doc), n=1, w=800)
    record(S, "pagina se desenează (PNG)", isinstance(png, bytes) and png[:4] == b"\x89PNG" and len(png) > 5000)
    runs = get("runs", path=str(doc), n=1)
    lines = runs.get("lines") if isinstance(runs, dict) else runs
    record(S, "rândurile de text sunt citite pentru editare", bool(lines) and any("Pagina 1" in json.dumps(x, ensure_ascii=False) for x in lines),
           str(runs)[:200])

    # semnătură nouă în bibliotecă, din „poza” semnăturii pe hârtie
    up = post("lib/process", b64=base64.b64encode((DOCS / "semnatura-hartie.jpg").read_bytes()).decode(), filename="IMG_0001.jpg", color="blue")
    record(S, "semnătură nouă: fundalul e scos (PNG transparent)", up.get("ok") and up.get("w", 0) > 100, up.get("error", ""))
    saved = post("lib/save", id=up.get("id"), name="Test Semnatar", replace=True)  # replace: testul se poate rula de mai multe ori
    record(S, "semnătura e salvată în bibliotecă", saved.get("ok") and Path(saved.get("file", "")).is_file(), saved)
    lib = get("lib")
    record(S, "biblioteca arată semnătura, cu numele ei", any(s["name"] == "Test Semnatar" for s in lib), lib)
    sigfile = saved.get("file", "")
    sigpng = get("sig", f=sigfile)
    with fitz.open(stream=sigpng, filetype="png") as im:
        pix = im[0].get_pixmap(alpha=True)
    record(S, "semnătura are fundal transparent", pix.alpha and pix.pixel(2, 2)[3] == 0, pix.pixel(2, 2))

    # salvare: semnătură + text nou
    items = [{"type": "sig", "page": 2, "sig": sigfile, "x": 300, "y": 620, "w": 140},
             {"type": "text", "page": 2, "x": 60, "y": 700, "text": "Semnat azi, 18.11.2026 - ăîâșț", "fs": 12, "color": "#1f3fbf", "font": "arial"}]
    r = post("save", path=str(doc), items=items)
    out = Path(r.get("out", ""))
    ok = record(S, "salvare cu semnătură și text: <nume>_semnat.pdf", r.get("ok") and out.name == "editor_semnat.pdf" and out.is_file(), r)
    if ok:
        record(S, "originalul a rămas neatins", pages(doc) == 3 and "Semnat azi" not in text_of(doc, 1))
        record(S, "textul nou e în PDF, cu diacritice", "Semnat azi, 18.11.2026 - ăîâșț" in text_of(out, 1).replace(" ", " "), text_of(out, 1)[-120:])
        with fitz.open(str(out)) as dd:
            imgs = dd[1].get_images()
            record(S, "semnătura e pe pagina 2", len(imgs) == 1, imgs)
        # a doua salvare scrie peste, cu rezervă pentru Anulează
        r2 = post("save", path=str(out), items=[{"type": "text", "page": 1, "x": 60, "y": 760, "text": "A doua salvare", "fs": 10}])
        record(S, "a doua salvare scrie în același fișier", r2.get("out") == str(out) and "A doua salvare" in text_of(out, 0), r2)
        u = post("undo", path=str(out))
        record(S, "Anulează: revine la varianta dinainte", u.get("ok") and "A doua salvare" not in text_of(out, 0), u)

    # rotire
    rot = fresh("rotire.pdf")
    r = post("save", path=str(rot), items=[], rotate={"pages": [1], "angle": 90})
    with fitz.open(r.get("out") or str(rot)) as dd:
        record(S, "rotirea unei pagini se salvează", dd[0].rotation == 90 and dd[1].rotation == 0, r)

    # editarea unui rând existent
    ed = fresh("editare.pdf")
    lines = get("runs", path=str(ed), n=1)
    lines = lines.get("lines") if isinstance(lines, dict) else lines
    first = next((ln for ln in lines if "Pagina 1" in json.dumps(ln, ensure_ascii=False)), None)
    if first:
        # la fel ca editorul (startEdit + serialize): rândul întreg, cu segmentele lui și textul nou
        seg = {**first["segments"][0], "orig": first["segments"][0]["text"], "text": "Pagina întâi (editată)"}
        item = {"type": "edit", "page": 1, "raw": first["raw"], "segments": [seg], "text": seg["text"]}
        r = post("save", path=str(ed), items=[item])
        got = text_of(Path(r["out"]), 0).replace("\u00a0", " ") if r.get("ok") else ""
        record(S, "editarea unui rând: textul vechi e înlocuit", r.get("ok") and "Pagina întâi (editată)" in got and "Pagina 1 din 3" not in got,
               r.get("error") or got[:80])
        record(S, "editarea unui rând: restul paginii rămâne", "Contract de prest" in got, got[:120])
    else:
        record(S, "editarea unui rând: textul vechi e înlocuit", False, "nu am găsit rândul")

    # formular
    form = fresh("form.pdf", "formular.pdf")
    d = get("doc", path=str(form))
    record(S, "formular: câmpurile și câmpul de semnătură sunt văzute", d.get("fields") == 3 and any(not f["signed"] for f in d.get("sigfields", [])), d)
    fields = get("fields", path=str(form), n=1)
    names = {f["name"]: f for f in fields}
    items = [{"type": "field", "page": 1, "name": "nume", "value": "ȘTEFAN TEST SRL", **{k: names["nume"][k] for k in names["nume"] if k not in ("value",)}},
             {"type": "field", "page": 1, "name": "acord", "value": True, **{k: names["acord"][k] for k in names["acord"] if k not in ("value",)}}]
    r = post("save", path=str(form), items=items)
    if r.get("ok"):
        with fitz.open(r["out"]) as dd:
            vals = {w.field_name: w.field_value for w in dd[0].widgets()}
        record(S, "formular: valorile completate sunt salvate (<nume>_editat.pdf)", vals.get("nume") == "ȘTEFAN TEST SRL" and vals.get("acord") not in (False, "Off", None)
               and Path(r["out"]).name == "form_editat.pdf", vals)
    else:
        record(S, "formular: valorile completate sunt salvate (<nume>_editat.pdf)", False, r)

    # organizarea paginilor: ordine nouă, o pagină ștearsă, una rotită
    org = fresh("organizare.pdf")
    r = post("organize", path=str(org), pages=[{"n": 3, "rot": 0}, {"n": 1, "rot": 90}])
    if r.get("ok"):
        with fitz.open(r["out"]) as dd:
            record(S, "organizează: ordinea, ștergerea și rotirea se salvează", len(dd) == 2 and "Pagina 3" in dd[0].get_text() and dd[1].rotation == 90,
                   [p.get_text()[:12] for p in dd])
    else:
        record(S, "organizează: ordinea, ștergerea și rotirea se salvează", False, r)

    # comentarii (fără trimitere la AI), captură de zonă
    for old_c in get("comments", path=str(doc)):  # rămase de la o rulare dinainte
        post("comment/delete", path=str(doc), id=old_c["id"])
    c = post("comment", path=str(doc), page=1, kind="point", x=100, y=115, text="Verifică suma", send=False)
    record(S, "comentariu pe pagină, cu textul de lângă el", c.get("ok") and c["comment"].get("context"), c)
    c2 = post("comment", path=str(doc), page=1, kind="region", rect=[50, 60, 400, 200], text="Ce scrie aici?", send=False)
    cap = c2.get("comment", {}).get("capture", "")
    record(S, "captură de zonă: imaginea e salvată", c2.get("ok") and Path(cap).is_file() and Path(cap).stat().st_size > 1000, c2)
    lst = get("comments", path=str(doc))
    record(S, "lista de comentarii", len(lst) == 2 and [x["number"] for x in lst] == [1, 2], lst)
    post("comment/delete", path=str(doc), id=c["comment"]["id"])
    record(S, "ștergerea unui comentariu", len(get("comments", path=str(doc))) == 1)

    # printare
    pr = post("print", path=str(doc), items=[{"type": "text", "page": 1, "x": 60, "y": 780, "text": "NESALVAT", "fs": 12}])
    record(S, "printare: paginile sunt pregătite (cu ce e nesalvat)", pr.get("ok") and len(pr.get("pages", [])) == 3, pr)
    if pr.get("ok"):
        img = get("printpage", id=pr["id"], n=1, dpi=150)
        record(S, "printare: pagina de tipar (PNG)", isinstance(img, bytes) and img[:4] == b"\x89PNG")

    # certificate și mediul de semnare (fără semnare: aceea cere PIN)
    certs = get("certs")
    record(S, "lista de certificate răspunde", isinstance(certs, list), str(certs)[:200])
    env = get("signenv")
    record(S, "starea FintaxySign răspunde", "fintaxysign" in env, env)
    record(S, "programele în plus: stare", get("deps").get("ok"))
    record(S, "token greșit = refuz", call("GET", "info", q={"t": "gresit"}).get("ok") is False)


# ---------------------------------------------------------------- B. uneltele locale

def local(tool, path, label, **fields):
    return post("local", tool=tool, path=str(path) if path else "", fields=fields, label=label)


def local_tests():
    print("\n== B. uneltele din aplicație (fără Stirling) ==")
    S = "local"
    doc = fresh("l.pdf")

    r = local("merge", doc, "Unește", files=[str(DOCS / "anexa.pdf")])
    record(S, "Unește PDF-uri: 3 + 2 = 5 pagini", r.get("ok") and pages(r["out"]) == 5, r)
    r = local("split", doc, "Împarte", mode="ranges", ranges="1-2, 3")
    record(S, "Împarte în bucăți", r.get("ok") and r["kind"] == "folder" and len(r["files"]) == 2, r)
    r = local("split", doc, "Împarte", mode="each")
    record(S, "Împarte: fiecare pagină separat", r.get("ok") and len(r["files"]) == 3, r)
    r = local("extract", doc, "Extrage", pages="2-3")
    record(S, "Extrage pagini", r.get("ok") and pages(r["out"]) == 2 and "Pagina 2" in text_of(r["out"]), r)
    r = local("extract", doc, "Extrage", pages="9")
    record(S, "Extrage: pagină inexistentă = mesaj clar", not r.get("ok") and "nu există" in r.get("error", ""), r)
    r = local("removepages", doc, "Șterge", pages="1")
    record(S, "Șterge pagini", r.get("ok") and pages(r["out"]) == 2 and "Pagina 2" in text_of(r["out"]), r)
    blank = fresh("gol.pdf", "cu-pagina-goala.pdf")
    r = local("removeblanks", blank, "Goale")
    record(S, "Șterge paginile goale", r.get("ok") and pages(r["out"]) == 2, r)
    r = local("rotate", doc, "Rotește", angle="90", pages="1")
    with fitz.open(r.get("out", str(doc))) as d:
        record(S, "Rotește", r.get("ok") and d[0].rotation == 90 and d[1].rotation == 0, r)
    r = local("compress", doc, "Comprimă", level="puternic")
    record(S, "Comprimă", r.get("ok") and pages(r["out"]) == 3 and Path(r["out"]).stat().st_size > 500, r)
    r = local("toword", doc, "Word")
    okw = r.get("ok") and Path(r["out"]).suffix == ".docx"
    if okw:
        from docx import Document
        dd = Document(r["out"])
        body = "\n".join(p.text for p in dd.paragraphs)
        okw = "Pagina 1" in body and len(dd.tables) >= 1
    record(S, "PDF → Word (text și tabel)", okw, r)
    r = local("toexcel", doc, "Excel")
    okx = r.get("ok") and Path(r["out"]).suffix == ".xlsx"
    if okx:
        from openpyxl import load_workbook
        wb = load_workbook(r["out"])
        cells = [c.value for ws in wb for row in ws.iter_rows() for c in row]
        okx = "Servicii contabilitate" in cells and 1250.0 in cells
    record(S, "PDF → Excel (tabelul, sumele ca numere)", okx, r if not okx else "")
    r = local("totext", doc, "Text")
    record(S, "PDF → Text", r.get("ok") and "Pagina 3 din 3" in Path(r["out"]).read_text(encoding="utf-8"), r)
    r = local("toimg", doc, "Imagini", format="png", dpi="100", pages="1-2")
    record(S, "PDF → Imagini", r.get("ok") and len(r.get("files", [])) == 2 and r["files"][0].endswith(".png"), r)
    r = local("fromimg", "", "Imagini → PDF", files=[str(DOCS / "scan1.jpg"), str(DOCS / "scan2.jpg")], page="a4")
    record(S, "Imagini → PDF", r.get("ok") and pages(r["out"]) == 2, r)
    for f in (DOCS / "document.pdf", DOCS / "tabel.pdf"):
        if f.exists():
            f.unlink()
    r = local("fromoffice", "", "Office → PDF", files=[str(DOCS / "document.docx"), str(DOCS / "tabel.xlsx")])
    record(S, "Word + Excel → PDF (LibreOffice, fără fereastră)", r.get("ok") and (DOCS / "document.pdf").is_file() and (DOCS / "tabel.pdf").is_file()
           and "diacritice" in text_of(DOCS / "document.pdf"), r)
    r = local("password", doc, "Parolă", password="secret12", allowCopy=False)
    okp = r.get("ok")
    if okp:
        with fitz.open(r["out"]) as d:
            okp = d.needs_pass and d.authenticate("secret12")
    record(S, "Adaugă parolă", okp, r)
    if okp:
        r2 = local("unpassword", r["out"], "Scoate parola", password="secret12")
        with fitz.open(r2.get("out", str(doc))) as d:
            record(S, "Elimină parola", r2.get("ok") and not d.needs_pass, r2)
        r3 = local("unpassword", r["out"], "Scoate parola", password="gresita")
        record(S, "Elimină parola: parolă greșită = mesaj clar", not r3.get("ok") and "parol" in r3.get("error", "").lower(), r3)
    r = local("password", doc, "Parolă", password="12")
    record(S, "Parolă prea scurtă = mesaj clar", not r.get("ok") and "4 caractere" in r.get("error", ""), r)
    r = local("watermark", doc, "Watermark", text="COPIE", opacity=30, pages="")
    record(S, "Watermark", r.get("ok") and "COPIE" in text_of(r["out"]), r)
    r = local("pagenumbers", doc, "Numere", format="Pagina {n} din {N}", position="jos-dreapta", start=1, pages="")
    record(S, "Numere de pagină", r.get("ok") and text_of(r["out"], 2).replace("\u00a0", " ").count("Pagina 3 din 3") >= 2, r)
    form = fresh("lform.pdf", "formular.pdf")
    r = local("flatten", form, "Aplatizează")
    with fitz.open(r.get("out", str(form))) as d:
        record(S, "Aplatizează (formularul devine pagină)", r.get("ok") and not list(d[0].widgets()), r)
    r = local("repair", doc, "Repară")
    record(S, "Repară PDF", r.get("ok") and pages(r["out"]) == 3, r)
    withimg = local("fromimg", "", "x", files=[str(DOCS / "scan1.jpg")], page="image")
    r = local("images", withimg["out"], "Extrage imaginile")
    record(S, "Extrage imaginile", r.get("ok") and len(r.get("files", [])) == 1, r)
    r = local("validatesign", doc, "Validează")
    record(S, "Validează semnătura: PDF nesemnat", r.get("ok") and r.get("kind") == "report", r)
    signed = FOLDER / "work" / "semnat-test.pdf"
    r = local("info", doc, "Info")
    record(S, "Informații de bază", r.get("ok") and any("3" in ln for ln in r.get("lines", [])), r)
    r = local("nu-exista", doc, "x")
    record(S, "unealtă necunoscută = eroare, nu blocaj", not r.get("ok"), r)

    # OCR făcut de aplicație (fără Tesseract / OCRmyPDF instalate)
    extra_fixtures()
    scan = fresh("scan.pdf", "scanari.pdf")
    r = local("ocr", scan, "OCR", languages="ron+eng", mode="skip")
    got = text_of(r["out"]) if r.get("ok") else ""
    record(S, "OCR: textul din scanare devine căutabil", r.get("ok") and "Scanare" in got and "test" in got.lower(), r.get("error") or got[:80])
    if r.get("ok"):
        with fitz.open(r["out"]) as d, fitz.open(str(scan)) as o:
            record(S, "OCR: paginile își păstrează mărimea și numărul", len(d) == len(o) and abs(d[0].rect.width - o[0].rect.width) < 1, d[0].rect)
    r = local("ocr", doc, "OCR", languages="ron+eng", mode="skip")
    record(S, "OCR pe un PDF care are deja text = mesaj clar", not r.get("ok") and "deja text" in r.get("error", ""), r)
    mixed = FOLDER / "work" / "mixt.pdf"
    with fitz.open(str(doc)) as a, fitz.open(str(scan)) as b:
        a.insert_pdf(b, from_page=0, to_page=0)
        a.save(str(mixed))
    r = local("ocr", mixed, "OCR", languages="ron+eng", mode="skip")
    record(S, "OCR mixt: doar pagina scanată e recunoscută, restul rămân neatinse", r.get("ok") and "1 din 4" in " ".join(r.get("lines", []))
           and "Pagina 1 din 3" in text_of(r["out"], 0) and "Scanare" in text_of(r["out"], 3), r)

    # redactare: textul e scos din PDF, nu doar acoperit
    r = local("autoredact", doc, "Redactează", texts="TEST SRL; RO49AAAA1B31007593840000; nu-exista-xyz")
    got = "".join(text_of(r["out"], i) for i in range(3)) if r.get("ok") else ""
    record(S, "Redactează text: textele nu mai există în PDF", r.get("ok") and "TEST SRL" not in got and "RO49AAAA" not in got and "Contract" in got,
           r.get("error") or r.get("lines"))
    r = local("autoredact", doc, "Redactează", texts="nu-exista-xyz")
    record(S, "Redactează: text negăsit = mesaj clar", not r.get("ok") and "Nu am găsit" in r.get("error", ""), r)

    # caută și înlocuiește
    rp = fresh("inlocuire.pdf")
    r = local("replace", rp, "Înlocuiește", find="Pagina", replace="Fila", matchCase=True)
    got = [text_of(r["out"], i) for i in range(3)] if r.get("ok") else []
    record(S, "Caută și înlocuiește: pe toate paginile", r.get("ok") and all(f"Fila {i + 1} din 3" in got[i] for i in range(3)) and "Pagina" not in "".join(got),
           r.get("error") or [g[:20] for g in got])
    record(S, "Caută și înlocuiește: originalul rămâne neatins", "Pagina 1 din 3" in text_of(rp))
    r = local("replace", rp, "Înlocuiește", find="nu-exista-xyz", replace="a")
    record(S, "Caută și înlocuiește: negăsit = mesaj clar", not r.get("ok") and "Nu am găsit" in r.get("error", ""), r)

    # HTML, Markdown și pagină web -> PDF (Edge, fără WeasyPrint)
    for f in (DOCS / "pagina.pdf", DOCS / "nota.pdf"):
        f.unlink(missing_ok=True)
    r = local("fromweb", "", "HTML → PDF", files=[str(DOCS / "pagina.html"), str(DOCS / "nota.md")])
    record(S, "HTML + Markdown → PDF", r.get("ok") and "Test HTML" in text_of(DOCS / "pagina.pdf") and "Test Markdown" in text_of(DOCS / "nota.pdf")
           and "unu" in text_of(DOCS / "nota.pdf"), r)
    r = post("local", tool="fromweb", path="", dir=str(FOLDER / "work"), fields={"url": "https://example.com"}, label="URL")
    record(S, "Pagină web → PDF, lângă documentul deschis", r.get("ok") and Path(r["out"]).parent == FOLDER / "work" and "documentation examples" in text_of(r["out"]), r)
    r = local("fromweb", "", "URL", url="example.com")
    record(S, "Pagină web: adresă fără https = mesaj clar", not r.get("ok") and "https" in r.get("error", ""), r)
    (DOCS / "desen.pdf").unlink(missing_ok=True)
    r = local("fromoffice", "", "Orice fișier → PDF", files=[str(DOCS / "desen.svg")])
    record(S, "Orice fișier → PDF (SVG, prin LibreOffice)", r.get("ok") and pages(DOCS / "desen.pdf") == 1, r)
    del signed


# ---------------------------------------------------------------- C. Stirling

OVERRIDES = {
    "security/auto-redact": {"listOfText": "TEST SRL", "useRegex": False, "wholeWordSearch": False, "redactColor": "#000000", "customPadding": 0, "convertPDFToImage": True},
    "general/edit-text": {"findText": "Beneficiar", "replaceText": "Client", "find": "Beneficiar", "replace": "Client", "searchText": "Beneficiar", "replacementText": "Client"},
    "security/add-password": {"password": "secret12", "ownerPassword": "owner123", "keyLength": 256},
    "misc/add-stamp": {"stampType": "text", "stampText": "COPIE", "pageNumbers": "1", "fontSize": 30, "rotation": 0, "opacity": 0.5, "position": 5,
                       "overrideX": -1, "overrideY": -1, "customMargin": "medium", "customColor": "#d3d3d3", "alphabet": "roman"},
    "security/redact": {"pageNumbers": "1", "pageRedactionColor": "#000000", "convertPDFToImage": True},
    "misc/update-metadata": {"title": "Titlu de test", "author": "PDF Sign", "deleteAll": False},
    "general/edit-table-of-contents": {"bookmarkData": '[{"title":"Capitol 1","pageNumber":1,"children":[]}]', "replaceExisting": True},
    "general/crop": {"x": 50, "y": 50, "width": 400, "height": 600},
    "general/rearrange-pages": {"pageNumbers": "3,2,1", "customMode": ""},
    "general/split-by-size-or-count": {"splitType": 1, "splitValue": "1"},
    "general/split-pdf-by-chapters": {"bookmarkLevel": 0, "includeMetadata": False, "allowDuplicates": False},
    "general/split-pdf-by-sections": {"horizontalDivisions": 1, "verticalDivisions": 1, "merge": False},
    "general/scale-pages": {"pageSize": "A4", "scaleFactor": 1},
    "general/multi-page-layout": {"pagesPerSheet": 2, "addBorder": False},
    "general/overlay-pdfs": {"overlayMode": "SequentialOverlay", "overlayPosition": 0},
    "misc/delete-attachment": {"attachmentName": "nota.txt"},
    "convert/pdf/presentation": {"outputFormat": "pptx"},
    "convert/pdf/csv": {"pageNumbers": "all"},
    "convert/pdf/pdfa": {"outputFormat": "pdfa-1"},
    "convert/pdf/vector": {"outputFormat": "ps"},
    "convert/pdf/text": {"outputFormat": "txt"},
    "convert/url/pdf": {"urlInput": "https://example.com"},
    "form/fill": {"data": '{"nume":"TEST SRL","cui":"123"}', "flatten": False},
    "form/delete-fields": {"names": '["cui"]'},
    "misc/add-comments": {"comments": '[{"pageIndex":0,"x":100,"y":700,"width":20,"height":20,"text":"Notă de test","author":"Test"}]'},
    "misc/ocr-pdf": {"languages": ["eng"], "ocrType": "force-ocr", "ocrRenderType": "hocr", "sidecar": False, "deskew": False, "clean": False, "cleanFinal": False},
}
# Fișierele în plus pe care le cer unele unelte: câmp -> fișier de test
EXTRA_FILES = {
    "general/overlay-pdfs": {"overlayFiles": ("anexa.pdf", "application/pdf")},
    "misc/add-image": {"imageFile": ("scan1.jpg", "image/jpeg")},
    "misc/add-attachments": {"attachments": ("nota.md", "text/markdown")},
    "misc/create-portfolio": {},
    "convert/file/pdf": {"fileInput": ("document.docx", "application/octet-stream")},
    "convert/html/pdf": {"fileInput": ("pagina.html", "text/html")},
    "convert/markdown/pdf": {"fileInput": ("nota.md", "text/markdown")},
    "convert/svg/pdf": {"fileInput": ("desen.svg", "image/svg+xml")},
    "convert/eml/pdf": {"fileInput": ("mesaj.eml", "message/rfc822")},
    "convert/ebook/pdf": {"fileInput": ("carte.epub", "application/epub+zip")},
}
SOURCE = {"form/": "formular.pdf", "misc/unlock-pdf-forms": "formular.pdf", "misc/extract-image-scans": "scanari.pdf", "misc/ocr-pdf": "scanari.pdf",
          "security/remove-cert-sign": "contract.pdf"}
# De ce poate lipsi un rezultat fără să fie o greșeală a aplicației
EXPECTED = {
    "security/timestamp-pdf": "cere un server de marcare temporală (internet)",
    "general/split-pdf-by-chapters": "documentul de test nu are capitole (bookmark-uri)",
    "convert/ebook/pdf": "cere un eBook de test valid",
    "convert/pdf/cbr": "cere WinRAR (plătit)",
    "security/validate-compliance": "verdictul corect: documentul de test nu e PDF/A",
    "form/add-fields": "cere definițiile câmpurilor (JSON), scrise de om",
    "misc/create-portfolio": "cere fișierele de pus în portofoliu",
    "security/redact": "cere zonele de acoperit (JSON), scrise de om",
    "convert/eml/pdf": "cere WeasyPrint (neinstalat implicit)",
}


def catalog():
    """Uneltele din editor/tools.js: id, etichetă, endpoint, local, noDoc, suffix, defaults."""
    src = (ROOT / "editor" / "tools.js").read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"^\s*\{ id: '([^']+)'.*$", src, re.M):
        line = m.group(0)

        def g(pat):
            mm = re.search(pat, line)
            return mm.group(1) if mm else None
        out.append({"id": m.group(1), "label": g(r"label: '([^']+)'"), "endpoint": g(r"endpoint: A \+ '([^']+)'"), "local": g(r"local: '([^']+)'"),
                    "noDoc": "noDoc: true" in line, "suffix": g(r"suffix: '([^']+)'"), "native": g(r"native: '([^']+)'"), "custom": g(r"custom: '([^']+)'")})
    return out


def extra_fixtures():
    (DOCS / "desen.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200"><rect width="300" height="200" fill="#eaf0ff"/>'
                                    '<text x="20" y="100" font-size="24">Test SVG</text></svg>', encoding="utf-8")
    (DOCS / "mesaj.eml").write_text("From: test@example.com\nTo: dest@example.com\nSubject: Mesaj de test\nDate: Wed, 18 Nov 2026 10:00:00 +0200\n"
                                    "MIME-Version: 1.0\nContent-Type: text/plain; charset=utf-8\n\nSalut, acesta e un mesaj de test.\n", encoding="utf-8")
    # „scanări”: un PDF făcut doar din imagini, pentru OCR și extragerea scanărilor
    d = fitz.open()
    for name in ("scan1.jpg", "scan2.jpg"):
        img = fitz.open(str(DOCS / name))
        d.insert_pdf(fitz.open("pdf", img.convert_to_pdf()))
    d.save(str(DOCS / "scanari.pdf"))
    d.close()
    # PDF cu un atașament, pentru uneltele de atașamente
    d = fitz.open(str(DOCS / "contract.pdf"))
    d.embfile_add("nota.txt", b"atasament de test", filename="nota.txt")
    d.save(str(DOCS / "cu-atasament.pdf"))
    d.close()


def stirling_tests():
    print("\n== C. uneltele Stirling (din catalog) ==")
    S = "stirling"
    info = get("info")
    if not info.get("stirling"):
        print("  Stirling PDF nu e instalat: secțiunea e sărită.")
        return
    t0 = time.time()
    spec = get("stirling/tools")
    if not isinstance(spec, dict) or "tools" not in spec:
        record(S, "Stirling pornește și își dă lista de unelte", False, spec)
        return
    record(S, f"Stirling pornește și își dă lista de unelte ({len(spec['tools'])}, {round(time.time() - t0)} s)", len(spec["tools"]) > 40)
    extra_fixtures()
    for t in catalog():
        ep = t["endpoint"]
        if not ep or t["local"] or t["custom"]:
            continue  # cele locale sunt testate la B; semnătura cu certificat are testul ei
        if ONLY and t["id"] not in ONLY:
            continue
        full = "/api/v1/" + ep
        sp = spec["tools"].get(full)
        if not sp:
            record(S, f"{t['label']} ({ep})", False, "nu există în versiunea asta de Stirling", "missing")
            continue
        src_name = next((v for k, v in SOURCE.items() if ep.startswith(k)), "cu-atasament.pdf" if "attach" in ep else "contract.pdf")
        doc = fresh(f"s-{t['id']}.pdf", src_name)
        fields = {}
        ov = OVERRIDES.get(ep, {})
        names = {f["name"] for f in sp["fields"]}
        for f in sp["fields"]:
            n = f["name"]
            if f["format"] == "binary" or f["itemFormat"] == "binary" or n in ("fileId", "clientFileIds"):
                continue
            if n in ov:
                fields[n] = ov[n]
            elif f["default"] is not None:
                fields[n] = f["default"]
            elif f["required"]:
                fields[n] = f["enum"][0] if f["enum"] else (f["example"] if f["example"] is not None and not isinstance(f["example"], (dict, list))
                                                              else {"boolean": False, "integer": 1, "number": 1}.get(f["type"], "1"))
        for k, v in ov.items():  # endpoint-uri care nu-și descriu câmpurile în specificație
            if k not in names and not sp["fields"]:
                fields[k] = v
        files = {}
        for field, (fname, mime) in EXTRA_FILES.get(ep, {}).items():
            p = DOCS / fname
            if p.exists():
                files[field] = [b64file(p, mime)]
        if t["noDoc"] and not files and "urlInput" not in fields:
            record(S, f"{t['label']} ({ep})", False, EXPECTED.get(ep, "fără fișier de test"), "expected")
            continue
        t1 = time.time()
        r = post("stirling/run", path=str(doc), endpoint=full, fields=fields, files=files, suffix=t["suffix"] or t["id"], label=t["label"],
                 usesDocument=not t["noDoc"], outStem=(next(iter(files.values()))[0]["name"].rsplit(".", 1)[0] if t["noDoc"] and files else None))
        dt = round(time.time() - t1, 1)
        if r.get("ok"):
            detail = r.get("kind", "")
            good = True
            if r.get("kind") == "pdf":
                try:
                    with fitz.open(r["out"]) as dd:
                        if dd.needs_pass:  # unealta a pus parolă (ex. „Schimbă permisiunile”)
                            dd.authenticate(str(fields.get("password") or fields.get("ownerPassword") or ""))
                        good = len(dd) >= 1
                except Exception as err:
                    good, detail = False, f"PDF invalid: {err}"
            elif r.get("kind") in ("file", "folder"):
                good = Path(r["out"]).exists()
            record(S, f"{t['label']} ({ep}, {dt} s)", good, detail, "" if good else "bug")
        else:
            err = r.get("error", "")
            kind = "expected" if ep in EXPECTED else "disabled" if "dezactivat" in err else "error"
            record(S, f"{t['label']} ({ep}, {dt} s)", False, (EXPECTED.get(ep, "") + " | " if ep in EXPECTED else "") + err, kind)


def main():
    t0 = time.time()
    if not ONLY:
        editor_tests()
        local_tests()
    if "--no-stirling" not in sys.argv:
        stirling_tests()
    (FOLDER / "raport-unelte.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n== rezumat ({round(time.time() - t0)} s) ==")
    hard = 0
    for sec, title in (("editor", "A. editorul"), ("local", "B. uneltele din aplicație"), ("stirling", "C. uneltele Stirling")):
        rows = [r for r in RESULTS if r["section"] == sec]
        if not rows:
            continue
        bad = [r for r in rows if not r["ok"]]
        print(f"{title}: {len(rows) - len(bad)} din {len(rows)} trec")
        for r in bad:
            print(f"   - [{r['kind'] or 'pică'}] {r['name']}: {r['detail'][:200]}")
        if sec != "stirling":
            hard += len(bad)
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
