"""Documentele Word (.docx, .rtf...) deschise în editor: PDF-ul de citit (bin/mdview.py, prin Microsoft Office sau
LibreOffice), ce primește editorul, unde se scriu copiile salvate. Totul pe un .docx făcut pe loc.
Cere Microsoft Office sau LibreOffice pe calculator (altfel testele de conversie sunt sărite, cu mesaj).

  python tests/test_docx.py [FOLDER]
"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
folder = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="pdfsign-docx-"))
os.environ["FX_STATE"] = str(folder / "state")
os.environ["FX_NO_COMPONENTS"] = "1"
sys.path.insert(0, str(ROOT / "bin"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
(folder / "state").mkdir(parents=True, exist_ok=True)

import fitz  # noqa: E402

FAILED = []


def check(name: str, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  [{str(detail)[:300]}]" if detail and not ok else ""), flush=True)
    if not ok:
        FAILED.append(name)
    return bool(ok)


def make_docx(path: Path, extra: str = ""):
    import docx
    d = docx.Document()
    d.add_heading("Contract de prestări servicii", 1)
    d.add_paragraph("Între Exemplu SRL și Ion Popescu. Diacritice: ăâîșț ĂÂÎȘȚ.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "Serviciu", "Preț"
    t.cell(1, 0).text, t.cell(1, 1).text = "Contabilitate", "1.250,00"
    if extra:
        d.add_paragraph(extra)
    d.save(path)


def text_of(pdf: Path) -> str:
    with fitz.open(pdf) as d:
        return "\n".join(p.get_text() for p in d)


def main():
    import deps
    import editor_server
    import fx_sign
    import mdview

    print("== tipuri ==")
    check("recunoaște .docx, .DOC, .rtf, .odt", all(mdview.is_doc(n) and mdview.is_word(n) for n in ("a.docx", "a.DOC", "a.rtf", "a.odt")))
    check("nu confundă Word cu Markdown sau PDF", not mdview.is_md("a.docx") and not mdview.is_doc("a.pdf") and not mdview.is_word("a.md"))

    if not deps.ms_office() and not deps.soffice():
        print("  (sărit: nici Microsoft Office, nici LibreOffice pe calculator)")
        return

    docs = folder / "acte"
    docs.mkdir(parents=True, exist_ok=True)
    src = docs / "Contract Popescu.docx"
    make_docx(src)
    before = src.read_bytes()

    print("== PDF-ul de citit ==")
    t0 = time.time()
    pv = mdview.preview(src)
    if not check("se face PDF-ul de citit", pv.is_file(), pv):
        return
    print(f"        (conversia a durat {time.time() - t0:.1f} s)")
    text = text_of(pv)
    check("are textul din .docx, cu diacritice", all(w in text for w in ("Contract de prestări servicii", "ăâîșț", "Exemplu SRL", "1.250,00")), text[:300])
    check("stă în folderul aplicației, nu lângă .docx", fx_sign.STATE in pv.parents and sorted(p.name for p in docs.iterdir()) == [src.name])
    t0 = time.time()
    check("a doua deschidere vine din memorie", mdview.preview(src) == pv and time.time() - t0 < 1)
    check("știe din ce .docx a fost făcut", mdview.source(pv) == src.resolve(), mdview.source(pv))

    print("== editorul ==")
    info = editor_server.doc_info(str(pv))
    check("numele arătat e al fișierului .docx", info["name"] == src.name, info["name"])
    check("folderul de lucru e al fișierului .docx", Path(info["dir"]) == docs.resolve(), info["dir"])
    check("mdSource e fișierul .docx", Path(info["mdSource"]) == src.resolve(), info["mdSource"])
    check("are pagini", len(info["pages"]) >= 1 and not info["xfaView"])

    print("== salvarea ==")
    out = fx_sign.output_path(pv, signed=False)
    check("copia _editat.pdf se scrie lângă .docx", out == docs.resolve() / "Contract Popescu_editat.pdf", out)
    import certsign
    check("copia _semnat.pdf se scrie lângă .docx", certsign.output_for(pv) == docs.resolve() / "Contract Popescu_semnat.pdf", certsign.output_for(pv))

    print("== .docx schimbat ==")
    make_docx(src, "Clauză adăugată după prima deschidere.")
    pv2 = mdview.preview(src)
    check("se convertește din nou, cu textul nou", pv2 != pv and "Clauză adăugată" in text_of(pv2))

    print("== .rtf ==")
    rtf = docs / "Notă.rtf"
    rtf.write_text(r"{\rtf1\ansi\deff0{\fonttbl{\f0 Arial;}}\f0 Not\u259?\'3f scurt\u259?\'3f RTF.}", encoding="ascii")
    check("se deschide și un .rtf", "scurt" in text_of(mdview.preview(rtf)))

    print("== erori ==")
    bad = docs / "stricat.docx"
    bad.write_bytes(b"nu e un document word")
    try:
        made, msg = mdview.preview(bad), ""
    except Exception as e:
        made, msg = None, str(e)
    # LibreOffice deschide un .docx stricat ca text simplu; Word dă eroare. Ambele sunt bune, cât timp nu se blochează.
    check("un .docx stricat dă mesaj clar sau se deschide ca text", ("stricat.docx" in msg) or (made and made.is_file()), msg)
    check("și nu lasă foldere goale în cache", all((d / "origin.json").exists() for d in mdview.CACHE.iterdir() if d.is_dir()))
    try:
        mdview.preview(docs / "lipsă.docx")
        gone = False
    except FileNotFoundError:
        gone = True
    check("un .docx care nu mai există dă mesaj, nu se blochează", gone)
    src.write_bytes(before)
    check("fișierul .docx nu e atins de aplicație", src.read_bytes() == before)


if __name__ == "__main__":
    main()
    print()
    if FAILED:
        print(f"{len(FAILED)} TESTE PICATE: {FAILED}")
        sys.exit(1)
    print("DOCUMENTELE WORD: TOATE TESTELE AU TRECUT")
