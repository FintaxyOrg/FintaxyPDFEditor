"""Fișierele Markdown (.md) deschise în editor: PDF-ul de citit (bin/mdview.py), ce primește editorul, unde se
scriu copiile salvate. Totul pe un .md făcut pe loc.

  python tests/test_md.py [FOLDER]
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
folder = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="pdfsign-md-"))
os.environ["FX_STATE"] = str(folder / "state")
os.environ["FX_NO_COMPONENTS"] = "1"
sys.path.insert(0, str(ROOT / "bin"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
(folder / "state").mkdir(parents=True, exist_ok=True)

import fitz  # noqa: E402

FAILED = []

MD = """# Notă de ședință

Text cu **îngroșat**, *cursiv*, `cod` și ~~tăiat~~. Diacritice: ăâîșț ĂÂÎȘȚ.

## Hotărâri

- prima hotărâre
- a doua hotărâre
- [x] sarcină făcută
- [ ] sarcină rămasă

1. pasul unu
2. pasul doi

> Un citat pe un rând.

---

| Firmă | Sumă |
|---|---|
| Exemplu SRL | 1.250,00 |
| Alt Exemplu SRL | 450,50 |

```
linie de cod
```

Link: [Fintaxy](https://fintaxy.com)
"""


def check(name: str, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  [{str(detail)[:300]}]" if detail and not ok else ""), flush=True)
    if not ok:
        FAILED.append(name)
    return bool(ok)


def main():
    import editor_server
    import fx_sign
    import localtools
    import mdview

    docs = folder / "note"
    docs.mkdir(parents=True, exist_ok=True)
    md = docs / "Notă ședință.md"
    md.write_text(MD, encoding="utf-8")
    before = md.read_bytes()

    print("== convertorul ==")
    html = localtools._md_html(MD, base="file:///D:/Documente%20firma/")
    for what, piece in (("titlu", "<h1>Notă de ședință</h1>"), ("îngroșat", "<b>îngroșat</b>"), ("tăiat", "<s>tăiat</s>"),
                        ("listă de bifat", "☑ sarcină făcută"), ("citat", "<blockquote>Un citat pe un rând.</blockquote>"),
                        ("linie", "<hr>"), ("tabel", "<th>Firmă</th>"), ("bază pentru imagini", '<base href="file:///D:/Documente%20firma/">')):
        check(what, piece in html, html[:400])
    check("imagine", '<img alt="siglă" src="poze/sigla.png">' in localtools._md_html("![siglă](poze/sigla.png)"))
    check("linkul rămâne link, nu imagine", '<a href="https://fintaxy.com">Fintaxy</a>' in html)

    print("== PDF-ul de citit ==")
    check("recunoaște .md și .markdown, nu și .pdf", mdview.is_md(md) and mdview.is_md("a.MARKDOWN") and not mdview.is_md("a.pdf"))
    pv = mdview.preview(md)
    if not check("se face PDF-ul de citit", pv.is_file(), pv):
        return
    with fitz.open(pv) as d:
        text = "\n".join(p.get_text() for p in d)
    check("are textul din .md, cu diacritice", all(w in text for w in ("Notă de ședință", "ăâîșț", "Exemplu SRL", "1.250,00", "pasul doi")), text[:300])
    check("stă în folderul aplicației, nu lângă .md", fx_sign.STATE in pv.parents and sorted(p.name for p in docs.iterdir()) == [md.name])
    check("a doua deschidere vine din memorie", mdview.preview(md) == pv)
    check("știe din ce .md a fost făcut", mdview.source(pv) == md.resolve(), mdview.source(pv))
    check("un PDF obișnuit nu are sursă .md", mdview.source(docs / "altul.pdf") is None)

    print("== editorul ==")
    info = editor_server.doc_info(str(pv))
    check("numele arătat e al fișierului .md", info["name"] == md.name, info["name"])
    check("folderul de lucru e al fișierului .md", Path(info["dir"]) == docs.resolve(), info["dir"])
    check("mdSource e fișierul .md", Path(info["mdSource"]) == md.resolve(), info["mdSource"])
    check("are pagini", len(info["pages"]) >= 1 and not info["xfaView"])

    print("== salvarea ==")
    out = fx_sign.output_path(pv, signed=False)
    check("copia _editat.pdf se scrie lângă .md", out == docs.resolve() / "Notă ședință_editat.pdf", out)
    import certsign
    check("copia _semnat.pdf se scrie lângă .md", certsign.output_for(pv) == docs.resolve() / "Notă ședință_semnat.pdf", certsign.output_for(pv))
    plain = docs / "contract.pdf"
    check("un PDF obișnuit își păstrează folderul", fx_sign.output_path(plain, signed=True) == docs / "contract_semnat.pdf")

    print("== .md schimbat ==")
    md.write_text(MD + "\n\nRând adăugat după prima deschidere.\n", encoding="utf-8")
    pv2 = mdview.preview(md)
    with fitz.open(pv2) as d:
        text2 = "\n".join(p.get_text() for p in d)
    check("se tipărește din nou, cu textul nou", pv2 != pv and "Rând adăugat" in text2)
    md.write_bytes(before)
    check("fișierul .md nu e atins de aplicație", md.read_bytes() == before)
    try:
        mdview.preview(docs / "lipsă.md")
        gone = False
    except FileNotFoundError:
        gone = True
    check("un .md care nu mai există dă mesaj, nu se blochează", gone)


if __name__ == "__main__":
    main()
    print()
    if FAILED:
        print(f"{len(FAILED)} TESTE PICATE: {FAILED}")
        sys.exit(1)
    print("FIȘIERELE MARKDOWN: TOATE TESTELE AU TRECUT")
