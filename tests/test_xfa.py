"""Formularele XFA dinamice (PDF-urile „inteligente” ale ANAF): în fișier e doar pagina „Please wait…”, iar conținutul
stă în formular. Verifică, pe un formular făcut pe loc (fără date reale): recunoașterea, PDF-ul de vizualizare făcut
cu pdf.js + Edge, ce arată editorul, refuzul modificărilor și semnarea electronică a fișierului original.

  python tests/test_xfa.py [FOLDER] [alte.pdf ...]      (PDF-urile date în plus sunt doar desenate și numărate)
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
args = [a for a in sys.argv[1:]]
folder = Path(args[0]).resolve() if args and not args[0].lower().endswith(".pdf") else Path(tempfile.mkdtemp(prefix="pdfsign-xfa-"))
extra = [Path(a) for a in args if a.lower().endswith(".pdf")]
os.environ["FX_STATE"] = str(folder / "state")
os.environ["FX_NO_COMPONENTS"] = "1"
sys.path.insert(0, str(ROOT / "bin"))
sys.path.insert(0, str(ROOT / "tests"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
(folder / "state").mkdir(parents=True, exist_ok=True)

import fitz  # noqa: E402

import make_fixtures  # noqa: E402

FAILED = []

XDP_OPEN = '<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/">'
XDP_CLOSE = "</xdp:xdp>"
TEMPLATE = """<template xmlns="http://www.xfa.org/schema/xfa-template/3.3/">
<subform name="form1" layout="tb" locale="ro_RO">
<pageSet><pageArea name="Page1" id="Page1"><contentArea x="36pt" y="36pt" w="523pt" h="770pt"/><medium stock="a4" short="595pt" long="842pt"/></pageArea></pageSet>
<subform name="p1" w="523pt" h="770pt">
<draw name="titlu" x="10pt" y="10pt" w="480pt" h="30pt"><ui><textEdit/></ui><value><text>FORMULAR DE TEST XFA</text></value><font typeface="Arial" size="18pt" weight="bold"/></draw>
<field name="cui" x="10pt" y="70pt" w="300pt" h="24pt"><ui><textEdit><border><edge/></border></textEdit></ui><caption placement="left" reserve="120pt"><value><text>Cod fiscal</text></value><font typeface="Arial" size="10pt"/></caption><value><text>12345678</text></value><font typeface="Arial" size="11pt"/><bind match="dataRef" ref="$.cui"/></field>
<field name="denumire" x="10pt" y="110pt" w="480pt" h="24pt"><ui><textEdit><border><edge/></border></textEdit></ui><caption placement="left" reserve="120pt"><value><text>Denumire</text></value><font typeface="Arial" size="10pt"/></caption><font typeface="Arial" size="11pt"/><bind match="dataRef" ref="$.denumire"/></field>
<field name="suma" x="10pt" y="150pt" w="300pt" h="24pt"><ui><numericEdit><border><edge/></border></numericEdit></ui><caption placement="left" reserve="120pt"><value><text>Suma</text></value></caption><para hAlign="right"/><value><decimal/></value><font typeface="Times New Roman" size="11pt"/><bind match="dataRef" ref="$.suma"/></field>
<field name="cif" x="10pt" y="190pt" w="300pt" h="24pt"><ui><textEdit><border><edge/></border><comb numberOfCells="10"/></textEdit></ui><font typeface="Times New Roman" size="11pt"/><bind match="dataRef" ref="$.cif"/></field>
<subform name="tabel" layout="table" x="10pt" y="230pt" columnWidths="120pt 0mm"><subform name="rand" layout="row">
<draw w="120pt" h="20pt"><ui><textEdit/></ui><value><text>Baza 100</text></value><font typeface="Times New Roman" size="10pt"/></draw>
<draw w="90pt" h="20pt"><ui><textEdit/></ui><value><text>TVA 21</text></value><font typeface="Times New Roman" size="10pt"/></draw>
</subform></subform>
<field name="bifa" x="10pt" y="270pt" w="200pt" h="20pt"><ui><checkButton/></ui><caption placement="right" reserve="180pt"><value><text>Bifat</text></value></caption><items><integer>1</integer><integer>0</integer></items><bind match="dataRef" ref="$.bifa"/></field>
<field name="semnatura" x="250pt" y="270pt" w="200pt" h="60pt"><ui><signature><border><edge/></border></signature></ui><caption placement="bottom" reserve="14pt"><para hAlign="center"/><value><text>Semnătura</text></value></caption><font typeface="Times New Roman" size="10pt"/><bind match="none"/></field>
<draw name="sigla" x="10pt" y="350pt" w="80pt" h="40pt"><value><image contentType="image/bmp" aspect="none">%BMP%</image></value></draw>
</subform>
<subform name="p2" w="523pt" h="770pt"><break before="pageArea"/>
<draw name="pagina2" x="10pt" y="10pt" w="480pt" h="30pt"><ui><textEdit/></ui><value><text>PAGINA A DOUA</text></value><font typeface="Arial" size="14pt"/></draw>
</subform>
</subform>
</template>"""
DATASETS = ('<xfa:datasets xmlns:xfa="http://www.xfa.org/schema/xfa-data/1.0/"><xfa:data><form1><cui>12345678</cui>'
            "<denumire>EXEMPLU TEST SRL</denumire><suma>27525.5</suma><cif>4365</cif><bifa>1</bifa></form1></xfa:data>"
            "</xfa:datasets>")


def bmp_offset_zero() -> str:
    """Sigla ANAF are offsetul datelor din antetul BMP pus pe 0 (Adobe o arată, Chrome o decalează): o imagine
    40x20 roșu în stânga, albastru în dreapta, cu același defect."""
    import base64
    import io
    from PIL import Image
    im = Image.new("RGB", (40, 20), (255, 0, 0))
    im.paste((0, 0, 255), (20, 0, 40, 20))
    buf = io.BytesIO()
    im.save(buf, "BMP")
    data = bytearray(buf.getvalue())
    data[10:14] = bytes(4)
    return base64.b64encode(bytes(data)).decode("ascii")


TEMPLATE = TEMPLATE.replace("%BMP%", bmp_offset_zero())


def check(name: str, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  [{str(detail)[:300]}]" if detail and not ok else ""), flush=True)
    if not ok:
        FAILED.append(name)
    return bool(ok)


def make_xfa(path: Path):
    """PDF cu o singură pagină („Please wait…”) și formularul adevărat în AcroForm/XFA, ca la ANAF."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Please wait...", fontsize=14)
    page.insert_text((72, 130), "If this message is not eventually replaced by the proper contents of the document,", fontsize=9)
    page.insert_text((72, 144), "your PDF viewer may not be able to display this type of document.", fontsize=9)
    packets = []  # ca în fișierele ANAF: XFA e o listă de bucăți numite, fiecare în fluxul ei
    for name, body in (("xdp:xdp", XDP_OPEN), ("template", TEMPLATE), ("datasets", DATASETS), ("</xdp:xdp>", XDP_CLOSE)):
        x = doc.get_new_xref()
        doc.update_object(x, "<<>>")
        doc.update_stream(x, body.encode("utf-8"))
        packets.append(f"({name}) {x} 0 R")
    form = doc.get_new_xref()
    doc.update_object(form, f"<</Fields[]/XFA[{' '.join(packets)}]>>")
    doc.xref_set_key(doc.pdf_catalog(), "AcroForm", f"{form} 0 R")
    doc.xref_set_key(doc.pdf_catalog(), "NeedsRendering", "true")  # semnul formularelor XFA dinamice
    doc.save(path)
    doc.close()


def main():
    import editor_server
    import fx_sign
    import xfaview
    docs = folder / "docs"
    f = make_fixtures.make(docs)
    xfa = docs / "formular-xfa.pdf"
    make_xfa(xfa)
    original = xfa.read_bytes()

    print("== recunoaștere ==")
    with fitz.open(xfa) as d:
        check("formularul de test e XFA și are doar pagina «Please wait»", fx_sign.is_xfa(d) and xfaview.needs(d))
    with fitz.open(f["doc"]) as d:
        check("un PDF obișnuit nu e tratat ca XFA", not xfaview.needs(d))
    with fitz.open(f["form"]) as d:
        check("un formular obișnuit (AcroForm) nu e tratat ca XFA dinamic", not xfaview.needs(d))

    print("== PDF-ul de vizualizare (pdf.js + Edge) ==")
    pv = xfaview.preview(xfa)
    if not check("se face", pv and pv.exists(), xfaview._failed):
        return
    with fitz.open(pv) as d:
        text = [p.get_text() for p in d]
        check("are cele două pagini ale formularului", d.page_count == 2, d.page_count)
        check("pagina e A4, ca în formular", abs(d[0].rect.width - 595) < 2 and abs(d[0].rect.height - 842) < 2, d[0].rect)
        check("se vede textul formularului", "FORMULAR DE TEST XFA" in text[0] and "PAGINA A DOUA" in text[-1], text[0][:120])
        check("se văd datele completate", "12345678" in text[0] and "EXEMPLU TEST SRL" in text[0], text[0][:200])
        check("nu mai apare «Please wait»", "please wait" not in " ".join(text).lower())

    print("== ca în Adobe ==")
    with fitz.open(pv) as d:
        page = d[0]
        words = [w[4] for w in page.get_text("words")]
        check("numărul are separatorii limbii (ro_RO: 27.525,5) și e aliniat la dreapta",
              "27.525,5" in words and next(w for w in page.get_text("words") if w[4] == "27.525,5")[2] > 300,
              [w for w in page.get_text("words") if "27" in w[4]])
        check("CIF-ul pe căsuțe (comb): fiecare cifră în căsuța ei", words.count("4") >= 1 and "4365" not in words,
              [w for w in words if w and w[0] in "4365"])
        check("coloana de tabel cu lățime 0 primește lățimea conținutului (ca în Adobe)", "21" in words and "TVA" in words, words)
        check("câmpul de semnătură se vede, cu textul de sub el", "Semnătura" in page.get_text())
        pix = page.get_pixmap(dpi=72, clip=fitz.Rect(36 + 10, 36 + 350, 36 + 90, 36 + 390))
        left, right = pix.pixel(pix.width // 4, pix.height // 2), pix.pixel(3 * pix.width // 4, pix.height // 2)
        check("imaginea BMP cu offsetul 0 (sigla ANAF) nu e decalată", left[0] > 200 and left[2] < 80 and right[2] > 200 and right[0] < 80,
              (left, right))
        box = fitz.Rect(36 + 10, 36 + 270, 36 + 30, 36 + 290)
        lines = [it for dr in page.get_drawings() if box.intersects(dr["rect"]) and dr["rect"].width < 30
                 for it in dr["items"] if it[0] == "l"]
        diag = {(it[2].x - it[1].x) * (it[2].y - it[1].y) > 0 for it in lines
                if abs(abs(it[2].x - it[1].x) - abs(it[2].y - it[1].y)) < 0.5 and abs(it[2].x - it[1].x) > 2}
        check("bifa e ca în Adobe: pătrat cu X (nu bifa rotunjită a browserului)", diag == {True, False}, lines[:4])
    check("a doua cerere vine din cache", xfaview.preview(xfa) == pv)

    print("== editorul ==")
    info = editor_server.doc_info(str(xfa))
    check("editorul arată paginile formularului, nu pagina de așteptare", info["xfaView"] and len(info["pages"]) == 2, info.get("pages"))
    png = editor_server.page_png(str(xfa), 2, 800)
    check("pagina 2 se desenează", png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 2000, len(png))
    check("textul paginii se poate citi (comentarii, copiere)", "FORMULAR" in editor_server.region_text(str(xfa), 1, [0, 0, 595, 200]))
    pr = editor_server.print_prepare(str(xfa), [])
    check("printarea ia paginile formularului", pr.get("ok") and len(pr["pages"]) == 2, pr)
    check("un PDF obișnuit nu e atins de vizualizare", not editor_server.doc_info(str(f["doc"]))["xfaView"])
    check("fișierul original a rămas neatins", xfa.read_bytes() == original)

    print("== semnarea electronică ==")
    import certsign
    from test_sign import validate
    os.environ["FX_TEST_PFX"] = str(f["pfx_ec"])
    os.environ["FX_TEST_PFX_PASS"] = make_fixtures.PFX_PASS
    res = certsign.sign_many("", [{"path": str(xfa), "place": None}], "Test", "București")
    if check("formularul XFA se semnează (invizibil)", res[0].get("ok"), res[0].get("error", "")):
        out = Path(res[0]["out"])
        v = validate(out)
        check("semnătura e validă și acoperă tot fișierul", len(v) == 1 and v[0][2] and v[0][3], v)
        with fitz.open(out) as d:
            check("formularul XFA a rămas în fișierul semnat", fx_sign.is_xfa(d) and fx_sign.is_signed(d))
        info = editor_server.doc_info(str(out))
        check("fișierul semnat se vede tot ca formular (2 pagini)", info["xfaView"] and len(info["pages"]) == 2 and info["signed"], info.get("pages"))
    check("originalul nesemnat a rămas neatins", xfa.read_bytes() == original)

    print("== semnătură vizibilă pe formularul XFA (ca în Acrobat) ==")
    viz = folder / "xfa_vizibil.pdf"
    viz.write_bytes(original)
    # câmpul „semnatura” din șablon: x=250pt y=270pt în zona de conținut (36pt, 36pt), 200x60pt
    res = certsign.sign_many("", [{"path": str(viz), "place": {"page": 1, "rect": [286, 306, 486, 352]}}], "Test", "")
    if check("se semnează vizibil", res[0].get("ok"), res[0].get("error", "")):
        out = Path(res[0]["out"])
        v = validate(out)
        check("semnătura vizibilă e validă", len(v) == 1 and v[0][2] and v[0][3], v)
        pv = xfaview.preview(out)
        if check("formularul se desenează și cu semnătură vizibilă (nu «Please wait»)", pv, xfaview._failed):
            with fitz.open(pv) as d:
                check("are tot cele două pagini ale formularului", d.page_count == 2, d.page_count)
                hits = d[0].search_for("Semnat digital")
                check("aspectul semnăturii e pus în caseta de semnătură a formularului",
                      len(hits) == 1 and 270 < hits[0].x0 < 500 and 290 < hits[0].y0 < 380, hits)
                check("textul formularului e tot acolo", "FORMULAR DE TEST XFA" in d[0].get_text())

    for p in extra:
        print(f"== {p.name} ==")
        with fitz.open(p) as d:
            dyn = xfaview.needs(d)
        print("      XFA dinamic:", dyn)
        if dyn:
            pv = xfaview.preview(p)
            if check("se desenează", pv, xfaview._failed):
                with fitz.open(pv) as d:
                    check(f"are conținut ({d.page_count} pagini)", d.page_count >= 1 and len(d[0].get_text()) > 200)


if __name__ == "__main__":
    main()
    print()
    if FAILED:
        print(f"{len(FAILED)} TESTE PICATE: {FAILED}")
        sys.exit(1)
    print("FORMULARELE XFA DINAMICE: TOATE TESTELE AU TRECUT")
