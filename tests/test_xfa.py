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
</subform>
<subform name="p2" w="523pt" h="770pt"><break before="pageArea"/>
<draw name="pagina2" x="10pt" y="10pt" w="480pt" h="30pt"><ui><textEdit/></ui><value><text>PAGINA A DOUA</text></value><font typeface="Arial" size="14pt"/></draw>
</subform>
</subform>
</template>"""
DATASETS = ('<xfa:datasets xmlns:xfa="http://www.xfa.org/schema/xfa-data/1.0/"><xfa:data><form1><cui>12345678</cui>'
            "<denumire>EXEMPLU TEST SRL</denumire></form1></xfa:data></xfa:datasets>")


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
