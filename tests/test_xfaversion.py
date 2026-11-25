"""Versiunea formularului ANAF (universalCode) în datele XFA: fără ea ANAF respinge depunerea („Versiunea formularului
nu este corecta”). PDF-urile din SAGA Web n-o au; semnarea o completează, cum face butonul „Validare” din Adobe.
Pe formulare făcute pe loc (fără date reale), cu structura formularelor ANAF D112 și D300.

  python tests/test_xfaversion.py [FOLDER]
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
folder = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="pdfsign-xfaver-"))
os.environ["FX_STATE"] = str(folder / "state")
os.environ["FX_NO_COMPONENTS"] = "1"
sys.path.insert(0, str(ROOT / "bin"))
sys.path.insert(0, str(ROOT / "tests"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
(folder / "state").mkdir(parents=True, exist_ok=True)

import fitz  # noqa: E402

import make_fixtures  # noqa: E402
import xfaversion  # noqa: E402

FAILED = []
TPL = '<template xmlns="http://www.xfa.org/schema/xfa-template/2.8/">{}</template>'
# ca D112: câmpul direct în subformularul rădăcină; valoarea implicită A7.2.5, dar scripturile scriu A7.2.4
# (și A7.2.2 într-o ramură veche): ANAF a primit A7.2.4, cum îl scrie Adobe la „Validare”
D112_TPL = TPL.format(
    '<subform name="frmMAIN"><pageSet><pageArea name="P"/></pageSet>'
    '<subform name="sbfrmPage1Ang"><field name="cif"/></subform>'
    '<field access="protected" name="universalCode"><ui><textEdit/></ui><value><text>D112_A7.2.5</text></value></field>'
    '<field name="versionHistory"><bind match="none"/></field>'
    '<script contentType="application/x-javascript">function fnValid1(vv) { frmMAIN.universalCode.rawValue="D112_A7.2.4"; }'
    ' function vechi() { frmMAIN.universalCode.rawValue=&quot;D112_A7.2.2&quot;; }</script>'
    '</subform>')
D112_DATA = ('<xfa:datasets xmlns:xfa="http://www.xfa.org/schema/xfa-data/1.0/"><xfa:data><frmMAIN>'
             '<sbfrmPage1Ang><cif>12345678</cif></sbfrmPage1Ang></frmMAIN></xfa:data></xfa:datasets>')
# ca D300: câmpul în form1 > Antet > IdDoc, printre subformulare fără nume și cu bind="none"; doar valoarea implicită
D300_TPL = TPL.format(
    '<subform name="form1"><subform><subform name="Antet"><subform name="IdDoc">'
    '<field name="formValid"/><field name="universalCode"><value><text>D300_A12.0.2</text></value></field>'
    '</subform></subform></subform><subform name="btnDoc"><bind match="none"/><field name="x"/></subform></subform>')
D300_DATA = ('<xfa:datasets xmlns:xfa="http://www.xfa.org/schema/xfa-data/1.0/"><xfa:data><form1><Antet>'
             '<cifS/></Antet></form1></xfa:data></xfa:datasets>')


def check(name: str, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  [{str(detail)[:300]}]" if detail and not ok else ""), flush=True)
    if not ok:
        FAILED.append(name)
    return bool(ok)


def make_xfa(path: Path, template: str, datasets: str):
    """PDF cu pagina „Please wait…” și formularul în AcroForm/XFA, ca la ANAF (bucăți numite, fiecare în fluxul ei)."""
    doc = fitz.open()
    doc.new_page(width=595, height=842).insert_text((72, 100), "Please wait...", fontsize=14)
    packets = []
    for name, body in (("xdp:xdp", '<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/">'), ("template", template),
                       ("datasets", datasets), ("</xdp:xdp>", "</xdp:xdp>")):
        x = doc.get_new_xref()
        doc.update_object(x, "<<>>")
        doc.update_stream(x, body.encode("utf-8"))
        packets.append(f"({name}) {x} 0 R")
    form = doc.get_new_xref()
    doc.update_object(form, f"<</Fields[]/XFA[{' '.join(packets)}]>>")
    doc.xref_set_key(doc.pdf_catalog(), "AcroForm", f"{form} 0 R")
    doc.xref_set_key(doc.pdf_catalog(), "NeedsRendering", "true")
    doc.save(path)
    doc.close()


def datasets_of(path) -> bytes:
    with fitz.open(path) as d:
        arr = d.xref_get_key(d.pdf_catalog(), "AcroForm/XFA")[1]
        import re
        xref = dict(re.findall(r"\(([^)]*)\)\s*(\d+) 0 R", arr))["datasets"]
        return d.xref_stream(int(xref))


def main():
    print("== ce versiune scrie formularul și unde ==")
    e = xfaversion.expected(D112_TPL.encode())
    check("D112: valoarea scrisă de scripturi, cea mai nouă (A7.2.4), nu cea implicită (A7.2.5)",
          e == {"path": ["frmMAIN", "universalCode"], "value": "D112_A7.2.4"}, e)
    e3 = xfaversion.expected(D300_TPL.encode())
    check("D300: valoarea implicită; subformularele fără nume nu intră în cale",
          e3 == {"path": ["form1", "Antet", "IdDoc", "universalCode"], "value": "D300_A12.0.2"}, e3)
    check("formular fără câmpul de versiune: nimic de făcut", xfaversion.expected(TPL.format('<subform name="f"><field name="a"/></subform>').encode()) is None)
    check("șablon stricat: nimic de făcut", xfaversion.expected(b"<template") is None)

    print("== completarea datelor ==")
    raw = D112_DATA.encode()
    check("D112 din SAGA: versiunea lipsește", xfaversion.current(raw, e["path"]) == "")
    new = xfaversion.add(raw, e["path"], e["value"])
    check("se adaugă în frmMAIN", xfaversion.current(new, e["path"]) == "D112_A7.2.4", new)
    check("restul datelor rămâne octet cu octet", new.replace(b"<universalCode>D112_A7.2.4</universalCode>", b"") == raw)
    new3 = xfaversion.add(D300_DATA.encode(), e3["path"], e3["value"])
    check("D300: grupul IdDoc lipsă se creează în Antet", xfaversion.current(new3, e3["path"]) == "D300_A12.0.2", new3)
    empty = D300_DATA.replace("<cifS/>", "<cifS/><IdDoc><formValid/><universalCode/></IdDoc>").encode()
    check("câmpul gol (<universalCode/>) se completează", xfaversion.current(xfaversion.add(empty, e3["path"], e3["value"]), e3["path"]) == "D300_A12.0.2")
    selfc = D300_DATA.replace("<cifS/>", '<cifS/><IdDoc xfa:dataNode="dataGroup"/>').encode()
    got = xfaversion.add(selfc, e3["path"], e3["value"])
    check("grupul gol (<IdDoc .../>) se deschide și primește câmpul", xfaversion.current(got, e3["path"]) == "D300_A12.0.2"
          and b'xfa:dataNode="dataGroup"' in got, got)
    check("date care nu sunt ale formularului: nu se ating", xfaversion.current(b"<x/>", e["path"]) is None)

    print("== la semnare ==")
    import certsign
    from test_sign import validate
    docs = folder / "docs"
    fx = make_fixtures.make(docs)
    os.environ["FX_TEST_PFX"] = str(fx["pfx_rsa"])
    os.environ["FX_TEST_PFX_PASS"] = make_fixtures.PFX_PASS
    saga = docs / "D112_saga.pdf"
    make_xfa(saga, D112_TPL, D112_DATA)
    original = saga.read_bytes()
    check("PDF-ul din SAGA are nevoie de versiune", xfaversion.needed(str(saga)) == e, xfaversion.needed(str(saga)))
    res = certsign.sign_many("", [{"path": str(saga), "place": None}], "Test", "")
    if check("se semnează", res[0].get("ok"), res[0].get("error", "")):
        out = Path(res[0]["out"])
        check("rezultatul spune ce versiune s-a completat", res[0].get("form_version") == "D112_A7.2.4", res[0])
        check("în PDF-ul semnat datele au versiunea", xfaversion.current(datasets_of(out), e["path"]) == "D112_A7.2.4")
        v = validate(out)
        check("semnătura e validă și acoperă tot fișierul", len(v) == 1 and v[0][2] and v[0][3], v)
        check("după semnare nu mai e nevoie de nimic", xfaversion.needed(str(out)) is None)
        res2 = certsign.sign_many("", [{"path": str(out), "place": None}], "A doua", "")
        check("a doua semnătură nu mai schimbă datele", res2[0].get("ok") and "form_version" not in res2[0]
              and datasets_of(res2[0]["out"]) == datasets_of(out), res2[0])
    check("originalul nesemnat a rămas neatins", saga.read_bytes() == original)

    ok_pdf = docs / "D112_validat.pdf"
    make_xfa(ok_pdf, D112_TPL, D112_DATA.replace("</frmMAIN>", "<universalCode>D112_A7.2.4</universalCode></frmMAIN>"))
    before = datasets_of(ok_pdf)
    res = certsign.sign_many("", [{"path": str(ok_pdf), "place": None}], "Test", "")
    check("formular validat în Adobe: datele rămân cum sunt", res[0].get("ok") and "form_version" not in res[0]
          and datasets_of(res[0]["out"]) == before, res[0])
    res = certsign.sign_many("", [{"path": str(fx["doc"]), "place": None}], "Test", "")
    check("un PDF obișnuit se semnează ca înainte", res[0].get("ok") and "form_version" not in res[0], res[0])

    print("== verificarea cu validatorul ANAF ==")
    import anaf
    (anaf.HOME / "lib").mkdir(parents=True, exist_ok=True)
    (anaf.HOME / "lib" / "D112Validator.jar").write_bytes(b"PK")
    real = anaf._duk
    try:
        anaf._duk = lambda args, timeout=900: ("Validare fara erori fisier PDF\nTipul declaratiei (D112) nu corespunde cu cel din PDF ()\n")
        vr = anaf.verify_signed(str(fx["doc"]), "D112")
        check("„Tipul declaratiei … ()” = lipsește versiunea: spune cauza", vr["status"] == "errors" and "universalCode" in vr["note"], vr)
        anaf._duk = lambda args, timeout=900: "Validare fara erori fisier PDF\nErori verificare valori PDF cu valori XML: an\n"
        vr = anaf.verify_signed(str(fx["doc"]), "D112")
        check("alte erori: mesajul obișnuit", vr["status"] == "errors" and "universalCode" not in vr["note"], vr)
    finally:
        anaf._duk = real


if __name__ == "__main__":
    main()
    print()
    if FAILED:
        print(f"{len(FAILED)} TESTE PICATE: {FAILED}")
        sys.exit(1)
    print("VERSIUNEA FORMULARULUI: TOATE TESTELE AU TRECUT")
