"""Semnătura electronică, cap-coadă, cu certificate de test din fișiere .pfx (fără card și fără PIN):
RSA și ECDSA P-384 (cheia buletinului electronic), vizibilă / în câmp / invizibilă, în bloc, peste un PDF deja
semnat, anulare și starea pentru editor. Fiecare semnătură e verificată criptografic cu pyHanko.

  python tests/test_sign.py [FOLDER]
"""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))
sys.path.insert(0, str(ROOT / "tests"))

import make_fixtures  # noqa: E402

FAILED = []


def check(name: str, ok: bool, detail: str = ""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""), flush=True)
    if not ok:
        FAILED.append(name)


def validate(pdf: Path) -> list:
    """[(câmp, algoritm hash, intactă, validă criptografic, acoperă tot fișierul de dinaintea ei)]"""
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext
    out = []
    with open(pdf, "rb") as fh:
        r = PdfFileReader(fh, strict=False)
        for sig in r.embedded_signatures:
            vc = ValidationContext(trust_roots=[sig.signer_cert], allow_fetching=False)
            st = validate_pdf_signature(sig, vc)
            out.append((sig.field_name, st.md_algorithm, st.intact, st.valid, st.coverage.name))
    return out


def main(folder: Path):
    import certsign
    import fitz
    f = make_fixtures.make(folder)
    os.environ["FX_TEST_PFX_PASS"] = make_fixtures.PFX_PASS

    for kind, pfx, want in (("RSA 2048", f["pfx_rsa"], "sha256"), ("ECDSA P-384 (ca buletinul)", f["pfx_ec"], "sha384")):
        print(f"\n== {kind} ==")
        os.environ["FX_TEST_PFX"] = str(pfx)
        work = folder / ("rsa" if "RSA" in kind else "ec")
        work.mkdir(exist_ok=True)
        src = work / "contract.pdf"
        src.write_bytes(f["doc"].read_bytes())

        # 1. vizibilă, într-un dreptunghi pe pagina 2
        res = certsign.sign_many("", [{"path": str(src), "place": {"page": 2, "rect": [320, 600, 520, 680]}}], "Test", "București")
        check("semnătură vizibilă (dreptunghi)", res[0].get("ok"), res[0].get("error", ""))
        out = Path(res[0].get("out", ""))
        if res[0].get("ok"):
            v = validate(out)
            check("validă criptografic", len(v) == 1 and v[0][2] and v[0][3], str(v))
            check(f"hash {want}", v and v[0][1] == want, str(v and v[0][1]))
            with fitz.open(out) as d:
                w = [x for x in d[1].widgets() if x.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE]
                check("ștampila e pe pagina 2, în locul ales", len(w) == 1 and abs(w[0].rect.x0 - 320) < 2 and abs(w[0].rect.y0 - 600) < 2,
                      str(w and w[0].rect))
                check("originalul a rămas neatins", src.read_bytes() == f["doc"].read_bytes())

            # 2. a doua semnătură peste copia semnată (invizibilă): prima rămâne validă
            res2 = certsign.sign_many("", [{"path": str(out), "place": None}])
            check("a doua semnătură pe același fișier", res2[0].get("ok") and res2[0]["out"] == str(out), res2[0].get("error", ""))
            v = validate(out)
            check("ambele semnături valide", len(v) == 2 and all(x[2] and x[3] for x in v), str(v))

        # 3. în câmpul de semnătură gol al unui formular
        form = work / "formular.pdf"
        form.write_bytes(f["form"].read_bytes())
        res = certsign.sign_many("", [{"path": str(form), "place": {"field": "Semnatura"}}])
        check("semnătură în câmpul formularului", res[0].get("ok"), res[0].get("error", ""))
        if res[0].get("ok"):
            v = validate(Path(res[0]["out"]))
            check("câmpul „Semnatura” e cel semnat", len(v) == 1 and v[0][0] == "Semnatura" and v[0][3], str(v))
            res = certsign.sign_many("", [{"path": res[0]["out"], "place": {"field": "Semnatura"}}])
            check("câmp deja semnat = refuz clar", not res[0].get("ok") and "deja semnat" in res[0].get("error", ""), res[0].get("error", ""))

        # 4. în bloc: 3 fișiere, „auto” (câmpul gol dacă există, altfel invizibilă), o singură deschidere a cheii
        batch = []
        for i, name in enumerate(("a.pdf", "b.pdf", "formular2.pdf")):
            p = work / name
            p.write_bytes((f["form"] if "formular" in name else f["doc2"]).read_bytes())
            batch.append({"path": str(p), "place": "auto"})
        batch.append({"path": str(work / "nu-exista.pdf"), "place": "auto"})
        seen = []
        res = certsign.sign_many("", batch, on_done=lambda r: seen.append(r))
        check("în bloc: 3 semnate, fișierul lipsă raportat, restul nu se opresc",
              [r.get("ok") for r in res] == [True, True, True, False], str([r.get("error") for r in res]))
        check("în bloc: progres raportat pe fiecare fișier", len(seen) == 4)
        if res[2].get("ok"):
            v = validate(Path(res[2]["out"]))
            check("în bloc: formularul semnat în câmpul lui", v and v[0][0] == "Semnatura" and v[0][3], str(v))

    # 5. o singură semnare o dată + stare + anulare
    print("\n== stare și anulare ==")
    check("stare: nimic în curs", certsign.status()["active"] is False)
    key = certsign.WinKey("")
    certsign.ACTIVE["key"] = key
    check("stare: cheie deschisă", certsign.status()["active"] is True and certsign.status()["phase"] == "open")
    box = {}
    t = threading.Thread(target=lambda: box.update(r=certsign.cancel()))
    t.start()
    t.join(15)
    time.sleep(0.5)
    check("anulare: procesul de semnare e oprit", box.get("r") is True and key.proc.poll() is not None)
    certsign.ACTIVE.update(key=None, phase="")
    certsign.BUSY.acquire()
    try:
        try:
            certsign.sign_many("", [{"path": str(f["doc"]), "place": None}])
            check("a doua semnare în paralel e refuzată", False)
        except RuntimeError as err:
            check("a doua semnare în paralel e refuzată", "deja în curs" in str(err), str(err))
    finally:
        certsign.BUSY.release()

    # 6. mesajele pentru erorile Windows
    print("\n== mesaje de eroare ==")
    m, stop = certsign.explain("ERR 8010006B The card cannot be accessed because the wrong PIN was presented.")
    check("PIN greșit: mesaj clar, oprește tot", stop and "PIN greșit" in m)
    m, stop = certsign.explain("ERR 8010006C blocked")
    check("card blocat: mesaj clar", stop and "blocat" in m)
    m, stop = certsign.explain("ERR 8010006E The action was cancelled by the user.")
    check("anulare în fereastra de PIN", stop and "anulată" in m)
    m, stop = certsign.explain("ERR 80090020 An internal error occurred.")
    check("eroare necunoscută: textul Windows + cod, fără oprirea lotului", not stop and "80090020" in m)

    # 7. certificat inexistent în Windows (fără .pfx de test)
    os.environ.pop("FX_TEST_PFX", None)
    res = certsign.sign_many("00" * 20, [{"path": str(f["doc"]), "place": None}])
    check("certificat lipsă: eroare, fără blocaj", not res[0].get("ok") and bool(res[0].get("error")), res[0].get("error", ""))
    check("după eroare, semnarea nu rămâne «în curs»", certsign.status()["active"] is False and not certsign.BUSY.locked())

    print("\n" + ("TOATE TESTELE DE SEMNARE AU TRECUT" if not FAILED else f"{len(FAILED)} TESTE PICATE: {FAILED}"))
    return 1 if FAILED else 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="pdfsign-test-"))
    sys.exit(main(target))
