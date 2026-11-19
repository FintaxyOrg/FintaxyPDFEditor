"""Validare și semnare declarații (bin/anaf.py), cap-coadă, fără date reale: XML-urile sunt făcute pe loc.

Partea obișnuită nu are nevoie de internet sau de Java: un server local ține loc de site-ul ANAF (versiuni.xml și
jar-urile), iar tests/fake_duk.py ține loc de Java + DUKIntegrator. Acoperă: aducerea și actualizarea validatoarelor
(o dată pe zi, versiune nouă, fără internet), recunoașterea declarației, erorile pe înțeles, PDF-ul, semnarea cu
certificate de test, verificarea PDF-ului semnat și rutele serverului editorului.

  python tests/test_anaf.py FOLDER            fără internet, fără Java
  python tests/test_anaf.py FOLDER --live     validatoarele adevărate de la ANAF, cu Java de pe calculator (cel din
                                              Stirling PDF); descarcă ~3 MB în FOLDER
  python tests/test_anaf.py FOLDER --live --clean   ca pe un calculator fără Stirling și fără Java: aplicația își aduce
                                              singură Java (~50 MB)
"""
import http.server
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
FOLDER = Path(_args[0]).resolve() if _args else Path(__import__("tempfile").mkdtemp(prefix="pdfsign-anaf-"))
LIVE = "--live" in sys.argv
CLEAN = "--clean" in sys.argv
FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  [{str(detail)[:300]}]" if detail and not ok else ""), flush=True)
    if not ok:
        FAILED.append(name)
    return bool(ok)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------- un „site ANAF” local

SITE = FOLDER / "site"
HITS = []


def jar(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("versiune.txt", text)
    return buf.getvalue()


def publish(port: int, versions: dict, integrator: str = "1.0.0"):
    """Scrie versiuni.xml și jar-urile, ca la o publicare ANAF: {cod: (J, P, numărul folderului)}."""
    base = f"http://127.0.0.1:{port}/update5"
    up = SITE / "update5"
    for rel in ("ii/iText.jar", "ss1/DecValidation.jar", "zz1/DUKIntegrator.jar"):
        (up / rel).parent.mkdir(parents=True, exist_ok=True)
        (up / rel).write_bytes(jar(f"{rel} {integrator}"))
    (up / "zz1" / "ajutor.chm").write_bytes(b"chm")
    (up / "cc1").mkdir(exist_ok=True)
    (up / "cc1" / "config.properties").write_text("proxy=auto\n", encoding="utf-8")
    decl = ""
    for code, (j, p, n) in versions.items():
        d = up / f"{code}_{n}"
        d.mkdir(exist_ok=True)
        (d / f"{code}Validator.jar").write_bytes(jar(f"{code} {j}"))
        (d / f"{code}Pdf.jar").write_bytes(jar(f"{code} {p}"))
        decl += (f"<{code}>\n<versiuneJ>{j}</versiuneJ>\n<versiuneP>{p}</versiuneP>\n<JURL>{base}/{code}_{n}/{code}Validator.jar</JURL>\n"
                 f"<PURL>{base}/{code}_{n}/{code}Pdf.jar</PURL>\n<DURL>{base}/{code}_{n}/{code}IstoriaVersiunilor.txt</DURL>\n</{code}>\n")
    (up / "versiuni.xml").write_text(
        f"<versiuni>\n<integrator>\n<versiune>{integrator}</versiune>\n<iJars><jarURL>{base}/ii/iText.jar</jarURL></iJars>\n"
        f"<sJars><jarURL>{base}/ss1/DecValidation.jar</jarURL></sJars>\n"
        f"<zJars><jarURL>{base}/zz1/DUKIntegrator.jar</jarURL><jarURL>{base}/zz1/ajutor.chm</jarURL></zJars>\n"
        f"<cFisiere><fisierURL>{base}/cc1/config.properties</fisierURL></cFisiere>\n</integrator>\n"
        f"<declaratii>\n<!-- <D999><versiuneJ>J0</versiuneJ><versiuneP>P0</versiuneP><JURL>x</JURL><PURL>y</PURL></D999> -->\n{decl}</declaratii>\n</versiuni>\n",
        encoding="utf-8")


class Site(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(SITE), **k)

    def do_GET(self):
        HITS.append(self.path)
        name = self.path.rsplit("/", 1)[-1]
        if FLAKY.get(name):  # o întrerupere de moment a site-ului
            FLAKY[name] -= 1
            return self.send_error(503)
        super().do_GET()

    def log_message(self, *a):
        pass


FLAKY = {}  # nume de fișier -> de câte ori mai răspunde site-ul simulat cu eroare


def hardening():
    """Observațiile din verificarea codului: reluarea descărcării și intrările neașteptate."""
    import anaf
    print("== descărcări întrerupte și intrări neașteptate ==")
    anaf.RETRY_WAIT = (0.1, 0.1)
    site = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Site)  # cel de la început a fost oprit la „fără internet”
    threading.Thread(target=site.serve_forever, daemon=True).start()
    publish(PORT, {"D300": ("J1.0.0", "P1.0.0", 1), "D112": ("J1.0.0", "P1.0.0", 1), "D390": ("J9.9.9", "P1.0.0", 9)})
    v = anaf.versions(force=True)
    FLAKY["D390Validator.jar"] = 1
    HITS.clear()
    try:
        changed = anaf.ensure("D390", v)
    except anaf.AnafError as err:
        changed = str(err)
    hits = sum(h.endswith("D390Validator.jar") for h in HITS)
    check("o descărcare întreruptă o dată e reluată singură", isinstance(changed, list) and changed and hits == 2, (changed, hits))
    publish(PORT, {"D300": ("J1.0.0", "P1.0.0", 1), "D112": ("J1.0.0", "P1.0.0", 1), "D390": ("J9.9.10", "P1.0.0", 10)})
    v = anaf.versions(force=True)
    FLAKY["D390Validator.jar"] = 9
    try:
        anaf.ensure("D390", v)
        gave_up = False
    except anaf.AnafError:
        gave_up = True
    FLAKY.clear()
    check("după trei încercări nereușite se oprește, cu mesaj", gave_up)
    check("validatorul vechi rămâne pe loc când cel nou nu vine", (anaf.HOME / "lib" / "D390Validator.jar").is_file())
    text = (SITE / "update5" / "versiuni.xml").read_text(encoding="utf-8")
    bad = text.replace("DUKIntegrator.jar", "..%5C..%5Crau.jar", 1) if "DUKIntegrator.jar" in text else ""
    try:
        anaf.parse_versions(bad)
        refused = not bad
    except anaf.AnafError:
        refused = True
    check("un nume de fișier neașteptat în lista ANAF e refuzat", bool(bad) and refused, bad[:80])
    doc = FOLDER / "declaratii" / "oarecare.pdf"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_bytes(b"%PDF-1.4")
    for code in ("../../x", "D300 -jar alt.jar", "Z999"):
        try:
            anaf.verify_signed(str(doc), code)
            ok = False
        except anaf.AnafError:
            ok = True
        check(f"verificarea PDF-ului semnat refuză tipul „{code}”", ok)


def xml_decl(code: str, cui: str = "12345678", extra: str = "", ns: str = "") -> bytes:
    ns = ns or f"mfp:anaf:dgti:{code.lower()}:declaratie:v1"
    return (f'<?xml version="1.0"?>\n<declaratie{code[1:]} luna="10" an="2026" cui="{cui}" den="TEST SRL" totalPlata_A="100" {extra} '
            f'xmlns="{ns}">\n  <rezumat total="100"/>\n</declaratie{code[1:]}>\n').encode("utf-8")


def offline():
    import fitz

    import anaf
    import certsign
    import make_fixtures
    docs = FOLDER / "declaratii"
    docs.mkdir(parents=True, exist_ok=True)
    fx = make_fixtures.make(FOLDER / "docs")
    os.environ["FX_TEST_PFX_PASS"] = make_fixtures.PFX_PASS

    print("\n== lista ANAF și recunoașterea declarației ==")
    v = anaf.parse_versions((SITE / "update5" / "versiuni.xml").read_text(encoding="utf-8"))
    check("versiuni.xml: declarațiile, fără cele comentate", set(v["decl"]) == {"D300", "D112", "D390"}, v["decl"].keys())
    check("versiuni.xml: fișierele de bază au locul lor (lib, config), fără ajutor.chm",
          sorted(rel for _u, rel in v["base"]) == ["DUKIntegrator.jar", "config/config.properties", "lib/DecValidation.jar", "lib/iText.jar"], v["base"])
    real = ("<versiuni><integrator><versiune>1</versiune><zJars><jarURL>http://static.anaf.ro/static/10/Anaf/update5/zz9/DUKIntegrator.jar</jarURL></zJars>"
            "</integrator><D300><versiuneJ>J1</versiuneJ><versiuneP>P1</versiuneP><JURL>http://static.anaf.ro/a/D300Validator.jar</JURL>"
            "<PURL>http://static.anaf.ro/a/D300Pdf.jar</PURL></D300></versiuni>")
    check("adresele http:// ale ANAF sunt luate prin https://", anaf.parse_versions(real)["decl"]["D300"]["jurl"].startswith("https://static.anaf.ro/"))
    try:
        anaf.parse_versions(real.replace("http://static.anaf.ro/a/D300Pdf.jar", "http://alt-site.example/D300Pdf.jar"))
        check("o adresă din afara ANAF e refuzată", False)
    except anaf.AnafError:
        check("o adresă din afara ANAF e refuzată", True)
    known = v["decl"].keys()
    check("D300 după spațiul de nume", anaf.detect(xml_decl("D300"), "export.xml", known) == "D300")
    check("D112 după „declaratie_unica”", anaf.detect(b'<declaratieUnica xmlns="mfp:anaf:dgti:declaratie_unica:declaratie:v7"/>', "x.xml", known) == "D112")
    check("D390 după elementul rădăcină, fără spațiu de nume", anaf.detect(b"<declaratie390 luna='1'/>", "x.xml", known) == "D390")
    check("după numele fișierului, când XML-ul nu spune", anaf.detect(b"<date/>", "D300_10_2026.xml", known) == "D300")
    check("XML stricat: tot recunoaște tipul din început", anaf.detect(xml_decl("D390")[:120], "x.xml", known) == "D390")
    check("necunoscut: nu ghicește", anaf.detect(b"<factura/>", "factura.xml", known) == "")
    items = anaf.parse_errors("E: validari globale\r\n eroare atribut: cui: CUI invalid ('123')\r\nA: rezumat\r\n atentionare: total 0\r\n")
    check("fișierul de erori: eroare + atenționare, cu secțiunea lor", [(i["level"], i["section"]) for i in items] == [("error", "validari globale"), ("warning", "rezumat")], items)
    check("explicația pe înțeles pentru CUI", "cifrei de control" in items[0]["hint"], items[0]["hint"])
    check("explicația pentru alt câmp îi spune numele", "„luna”" in anaf.hint("eroare atribut: luna: valoare in afara intervalului"))

    print("\n== validatoarele se aduc singure ==")
    good = docs / "D300_test.xml"
    good.write_bytes(xml_decl("D300"))
    HITS.clear()
    r = anaf.process(str(good))
    check("XML valid: fără erori, tipul recunoscut", r["status"] == "ok" and r["decl"] == "D300", r)
    check("programul și validatorul D300 au fost aduse în folderul aplicației",
          all((anaf.HOME / p).is_file() for p in ("DUKIntegrator.jar", "lib/iText.jar", "lib/DecValidation.jar", "config/config.properties",
                                                   "lib/D300Validator.jar", "lib/D300Pdf.jar")) and str(FOLDER) in str(anaf.HOME))
    check("doar validatorul cerut (nu toate declarațiile)", not (anaf.HOME / "lib" / "D112Validator.jar").exists())
    check("rezultatul spune ce versiune s-a folosit și că a fost adusă acum", r["versions"]["J"] == "J1.0.0" and len(r["updated"]) == 2, r)
    pdf = Path(r["pdf"] or "x")
    check("PDF-ul e făcut lângă XML, cu același nume", pdf == good.with_suffix(".pdf") and pdf.is_file(), r["pdf"])
    with fitz.open(str(pdf)) as d:
        check("PDF-ul are XML-ul atașat, neschimbat", d.embfile_get(d.embfile_names()[0]) == good.read_bytes())
    check("de semnat: PDF-ul făcut, semnătură invizibilă", r["sign"] == {"path": str(pdf), "place": None}, r["sign"])
    check("copia de lucru a declarației nu rămâne în folderul aplicației", not list((anaf.HOME / "work").iterdir()))
    check("nimic în plus lângă XML (fișiere de erori, jurnale)", sorted(p.name for p in docs.iterdir()) == ["D300_test.pdf", "D300_test.xml"], list(docs.iterdir()))

    print("\n== actualizarea: cel mult o dată pe zi ==")
    HITS.clear()
    r = anaf.process(str(good))
    check("a doua oară în aceeași zi: nimic descărcat, nici lista", r["status"] == "ok" and not HITS and not r["updated"], HITS)
    check("PDF-ul făcut mai devreme de validator e înlocuit, nu dublat", r["pdf"] == str(pdf) and not (docs / "D300_test-2.pdf").exists(), r["pdf"])
    publish(PORT, {"D300": ("J1.0.1", "P1.0.0", 2), "D112": ("J1.0.0", "P1.0.0", 1), "D390": ("J1.0.0", "P1.0.0", 1)})
    HITS.clear()
    r = anaf.process(str(good))
    check("ANAF a publicat ceva nou, dar am verificat azi: nu mai întreabă", not HITS and r["versions"]["J"] == "J1.0.0", HITS)
    st = json.loads((anaf.HOME / "state.json").read_text(encoding="utf-8"))
    st["checked"] = time.time() - 25 * 3600
    (anaf.HOME / "state.json").write_text(json.dumps(st), encoding="utf-8")
    HITS.clear()
    r = anaf.process(str(good))
    check("a doua zi: citește lista și aduce validatorul nou", r["versions"]["J"] == "J1.0.1" and r["updated"] == ["D300 J1.0.0 → J1.0.1"], (r["versions"], r["updated"]))
    check("a descărcat doar lista și cele două fișiere ale lui D300", sorted(HITS) == ["/update5/D300_2/D300Pdf.jar", "/update5/D300_2/D300Validator.jar", "/update5/versiuni.xml"], HITS)
    with zipfile.ZipFile(anaf.HOME / "lib" / "D300Validator.jar") as z:
        check("fișierul din folder e cel nou", z.read("versiune.txt") == b"D300 J1.0.1")
    other = docs / "D390_test.xml"
    other.write_bytes(xml_decl("D390"))
    HITS.clear()
    r = anaf.process(str(other))
    check("altă declarație: se aduce doar validatorul ei", r["status"] == "ok" and sorted(HITS) == ["/update5/D390_1/D390Pdf.jar", "/update5/D390_1/D390Validator.jar"], HITS)

    print("\n== erorile, pe înțeles ==")
    bad = docs / "D300_cui.xml"
    bad.write_bytes(xml_decl("D300", cui="123"))
    r = anaf.process(str(bad))
    check("CUI greșit: eroare, cu mesajul ANAF și explicația", r["status"] == "errors" and len(r["messages"]) == 1 and "CUI invalid" in r["messages"][0]["lines"][0]
          and "cifrei de control" in r["messages"][0]["hint"], r)
    check("cu erori nu se face PDF și nu e nimic de semnat", not r["pdf"] and r["sign"] is None and not bad.with_suffix(".pdf").exists())
    old = docs / "D300_vechi.xml"
    old.write_bytes(xml_decl("D300", ns="mfp:anaf:dgti:d300:declaratie:v0"))
    r = anaf.process(str(old), decl="D300")
    check("formular de altă versiune: eroare de structură explicată", r["status"] == "errors" and "altă versiune a formularului" in r["messages"][0]["hint"], r)
    cut = docs / "D300_taiat.xml"
    cut.write_bytes(xml_decl("D300")[:150])
    r = anaf.process(str(cut))
    check("XML tăiat: spune că fișierul nu e întreg", r["status"] == "fatal" and "nu e un XML întreg" in r["note"], r)
    warn = docs / "D300_atentie.xml"
    warn.write_bytes(xml_decl("D300", extra='atentie="1"'))
    r = anaf.process(str(warn))
    check("doar atenționări: valid, cu atenționarea arătată și PDF făcut", r["status"] == "warnings" and r["messages"][0]["level"] == "warning"
          and Path(r["pdf"]).is_file(), r)
    unk = docs / "factura.xml"
    unk.write_bytes(b"<factura numar='1'/>")
    r = anaf.process(str(unk))
    check("tip nerecunoscut: cere alegerea din listă", r["status"] == "unknown" and any(t["code"] == "D112" for t in r["types"]), r)
    r = anaf.process(str(unk), decl="D300")
    check("tip ales de mână: validatorul lui spune ce nu e bine", r["status"] == "errors", r)
    try:
        anaf.process(str(unk), decl="D777")
        check("declarație fără validator la ANAF: mesaj clar", False)
    except anaf.AnafError as err:
        check("declarație fără validator la ANAF: mesaj clar", "D777" in str(err), err)
    mine = docs / "D390_test.pdf"
    mine.write_bytes(fx["doc"].read_bytes())  # un PDF al omului, cu numele pe care l-ar lua PDF-ul declarației
    r = anaf.process(str(other))
    check("un PDF al omului cu același nume nu e suprascris", r["pdf"].endswith("D390_test-2.pdf") and mine.read_bytes() == fx["doc"].read_bytes(), r["pdf"])

    print("\n== semnarea și verificarea PDF-ului semnat ==")
    for label, pfx, want in (("RSA", fx["pfx_rsa"], "ok"), ("ECDSA P-384 (ca buletinul)", fx["pfx_ec"], "unsupported")):
        os.environ["FX_TEST_PFX"] = str(pfx)
        src = docs / f"D300_{label[:2].lower()}.xml"
        src.write_bytes(xml_decl("D300"))
        r = anaf.process(str(src))
        res = certsign.sign_many("", [r["sign"]], f"Declarație {r['decl']}")
        check(f"{label}: PDF-ul declarației e semnat", res[0].get("ok") and res[0]["out"].endswith("_semnat.pdf"), res[0])
        with fitz.open(res[0]["out"]) as d:
            check(f"{label}: semnătura e în fișier și XML-ul atașat a rămas", d.get_sigflags() == 3 and d.embfile_get(d.embfile_names()[0]) == src.read_bytes())
        vr = anaf.verify_signed(res[0]["out"], r["decl"])
        check(f"{label}: verificarea cu validatorul → {want}", vr["status"] == want and vr["note"], vr)
    vr = anaf.verify_signed(str(pdf), "D300")
    check("PDF nesemnat dat la verificare: spune că nu e semnat", vr["status"] == "errors" and "nu este semnat" in " ".join(vr["lines"]), vr)

    print("\n== PDF cu XML atașat ==")
    os.environ["FX_TEST_PFX"] = str(fx["pfx_rsa"])
    smart = docs / "declaratie_din_pdf.pdf"
    d = fitz.open()
    d.new_page(width=595, height=842).insert_text((60, 80), "Formular (test)", fontsize=14, fontname="helv")
    d.embfile_add("D390.xml", xml_decl("D390"), filename="D390.xml")
    d.save(str(smart))
    d.close()
    before = sorted(p.name for p in docs.iterdir())
    r = anaf.process(str(smart))
    check("PDF cu XML atașat: XML-ul e validat, tipul recunoscut", r["status"] == "ok" and r["decl"] == "D390" and r["source"] == "pdf", r)
    check("nu se face alt PDF: se semnează cel ales", not r["pdf"] and r["sign"] == {"path": str(smart), "place": "auto"} and before == sorted(p.name for p in docs.iterdir()), r)
    d = fitz.open(str(smart))
    d.embfile_del("D390.xml")
    d.embfile_add("D390.xml", xml_decl("D390", cui="123"), filename="D390.xml")
    d.save(str(docs / "declaratie_gresita.pdf"))
    d.close()
    r = anaf.process(str(docs / "declaratie_gresita.pdf"))
    check("PDF cu XML greșit: erorile XML-ului, nimic de semnat", r["status"] == "errors" and r["sign"] is None, r)
    try:
        anaf.process(str(fx["doc"]))
        check("PDF fără XML atașat: mesaj clar", False)
    except anaf.AnafError as err:
        check("PDF fără XML atașat: mesaj clar", "nu are un XML atașat" in str(err), err)

    print("\n== fără internet ==")
    st = json.loads((anaf.HOME / "state.json").read_text(encoding="utf-8"))
    st["checked"] = time.time() - 30 * 3600
    (anaf.HOME / "state.json").write_text(json.dumps(st), encoding="utf-8")
    SERVER.shutdown()
    SERVER.server_close()
    r = anaf.process(str(good))
    check("site-ul ANAF nu răspunde: merge cu validatorul pe care îl are și o spune", r["status"] == "ok" and r["online"] is False, r)
    (docs / "D112.xml").write_bytes(xml_decl("D112"))
    try:
        anaf.process(str(docs / "D112.xml"))
        check("validator încă neadus + fără internet: mesaj clar", False)
    except anaf.AnafError as err:
        check("validator încă neadus + fără internet: mesaj clar", "Nu am putut descărca" in str(err), err)
    s = anaf.status()
    check("starea pentru editor: ce e instalat și lista tipurilor", s["installed"]["D300"]["J"] == "J1.0.1" and s["java"] and s["types"][0]["code"] == "D112", s)


def server_routes():
    """Aceleași drumuri prin serverul editorului (ca din interfață): /api/anaf/status, run, verify + /api/certsign."""
    import make_fixtures
    print("\n== rutele serverului editorului ==")
    port = free_port()
    srv_folder = FOLDER / "srv"
    env = {**os.environ, "FX_STATE": str(FOLDER / "state"), "FX_TEST_PFX": str(FOLDER / "docs" / "test-rsa.pfx"), "FX_TEST_PFX_PASS": make_fixtures.PFX_PASS}
    pfx = next((FOLDER / "docs").glob("*rsa*.pfx"), None)
    if pfx:
        env["FX_TEST_PFX"] = str(pfx)
    proc = subprocess.Popen([sys.executable, str(ROOT / "tests" / "dev_server.py"), str(srv_folder), str(port)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def call(method, path, body=None):
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/{path}?t=test", data=json.dumps(body).encode() if body is not None else None,
                                     method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return {"ok": False, **json.loads(e.read())}
    try:
        for _ in range(100):
            try:
                st = call("GET", "anaf/status")
                break
            except OSError:
                time.sleep(0.3)
        check("GET /api/anaf/status", st.get("ok") and "D300" in st["installed"] and st["types"], st)
        src = FOLDER / "declaratii" / "D300_server.xml"
        src.write_bytes(xml_decl("D300"))
        r = call("POST", "anaf/run", {"path": str(src)})
        check("POST /api/anaf/run: validat, PDF făcut", r.get("ok") and r["status"] == "ok" and Path(r["pdf"]).is_file(), r)
        s = call("POST", "certsign", {"thumb": "", "items": [r["sign"]]})
        ok = s.get("ok") and s["results"][0].get("ok")
        check("POST /api/certsign pe PDF-ul declarației", ok, s)
        if ok:
            vr = call("POST", "anaf/verify", {"path": s["results"][0]["out"], "decl": "D300"})
            check("POST /api/anaf/verify: PDF-ul semnat e în regulă", vr.get("status") == "ok", vr)
        e = call("POST", "anaf/run", {"path": str(FOLDER / "declaratii" / "nu-exista.xml")})
        check("fișier lipsă: eroare pe înțeles, nu excepție", e.get("ok") is False and "nu mai există" in e.get("error", ""), e)
    finally:
        proc.kill()


def cui_ok(body: str) -> str:
    """Un cod fiscal inventat, cu cifra de control corectă (cheia 753217532)."""
    key = "753217532"[-len(body):]
    c = sum(int(a) * int(b) for a, b in zip(body, key)) * 10 % 11 % 10
    return body + str(c)


def de_vat(body: str) -> str:
    """Un cod de TVA german inventat, cu cifra de control corectă (ISO 7064, MOD 11,10): validatorul ANAF o verifică."""
    p = 10
    for ch in body:
        s = (int(ch) + p) % 10 or 10
        p = 2 * s % 11
    return body + str((11 - p) % 10)


def live():
    """Validatoarele adevărate: descărcate de la ANAF în FOLDER și rulate cu Java de pe calculator."""
    import fitz

    import anaf
    import certsign
    import deps
    import make_fixtures
    print("\n== LIVE: validatoarele ANAF adevărate ==")
    if CLEAN:
        check("calculator „curat”: niciun Java la început", not deps.java(), deps.java())
    elif not deps.java():
        return check("Java pe calculator (cel din Stirling PDF)", False, "nu am găsit Java: instalează Stirling PDF sau lasă aplicația să-l aducă")
    docs = FOLDER / "live"
    shutil.rmtree(docs, ignore_errors=True)
    docs.mkdir(parents=True)
    cui = cui_ok("1234567")
    body = ('<?xml version="1.0"?>\n<declaratie390 luna="10" an="2026" d_rec="0" nume_declar="POPESCU" prenume_declar="ION" functie_declar="ADMINISTRATOR" '
            f'cui="{cui}" den="TEST SRL" adresa="BUCURESTI str. Exemplu nr. 1" telefon="0210000000" mail="test@example.com" totalPlata_A="1001" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="mfp:anaf:dgti:d390:declaratie:v3 D390.xsd" xmlns="mfp:anaf:dgti:d390:declaratie:v3">\n'
            '\t<rezumat nr_pag="1" nrOPI="1" bazaL="0" bazaT="0" bazaA="0" bazaP="1000" bazaS="0" bazaR="0" total_baza="1000" />\n'
            '\t<operatie tip="P" tara="DE" codO="{vat}" denO="TEST GMBH" baza="1000" />\n</declaratie390>\n')
    wrong_vat = body.replace("{vat}", "123456789")
    body = body.replace("{vat}", de_vat("12345678"))
    src = docs / "D390_test.xml"
    src.write_text(body, encoding="utf-8")
    t = time.time()
    r = anaf.process(str(src))
    check(f"D390 făcut pe loc: validat de validatorul ANAF ({round(time.time() - t)} s, {r.get('versions')})", r["status"] in ("ok", "warnings") and r["decl"] == "D390", r)
    if CLEAN:
        out = subprocess.run([deps.java(), "-version"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW).stderr
        check("Java a fost adus în folderul aplicației și pornește", str(FOLDER) in deps.java() and "Runtime" in out, (deps.java(), out[:120]))
    check("validatoarele au venit de la static.anaf.ro, în folderul de test", (anaf.HOME / "lib" / "D390Validator.jar").stat().st_size > 10000 and str(FOLDER) in str(anaf.HOME))
    if r.get("pdf"):
        with fitz.open(r["pdf"]) as d:
            check("PDF-ul făcut de programul ANAF are XML-ul atașat", bool(d.embfile_names()) and d.embfile_get(d.embfile_names()[0]) == src.read_bytes())
        fx = make_fixtures.make(FOLDER / "docs")
        os.environ["FX_TEST_PFX_PASS"] = make_fixtures.PFX_PASS
        os.environ["FX_TEST_PFX"] = str(fx["pfx_rsa"])
        res = certsign.sign_many("", [r["sign"]])
        check("semnat cu certificatul de test (RSA)", res[0].get("ok"), res[0])
        if res[0].get("ok"):
            vr = anaf.verify_signed(res[0]["out"], "D390")
            check("programul ANAF verifică PDF-ul semnat de noi: fără erori", vr["status"] == "ok", vr)
    bad = docs / "D390_cui.xml"
    bad.write_text(body.replace(f'cui="{cui}"', 'cui="123"'), encoding="utf-8")
    r = anaf.process(str(bad))
    check("CUI greșit: validatorul ANAF dă eroare, aplicația o explică", r["status"] == "errors" and any(m["hint"] for m in r["messages"]), r)
    vat = docs / "D390_tva.xml"
    vat.write_text(wrong_vat, encoding="utf-8")
    r = anaf.process(str(vat))
    check("cod de TVA al partenerului greșit: eroare explicată, cu secțiunea ei", r["status"] == "errors" and "cod de TVA" in r["messages"][0]["hint"]
          and r["messages"][0]["section"].startswith("operatie"), r)
    cut = docs / "D390_taiat.xml"
    cut.write_text(body[:300], encoding="utf-8")
    r = anaf.process(str(cut))
    check("XML tăiat: nu e validat", r["status"] == "fatal", r)


if __name__ == "__main__":
    if LIVE:
        os.environ["FX_STATE"] = str(FOLDER / ("state-clean" if CLEAN else "state-live"))
        os.environ.setdefault("FX_NO_COMPONENTS", "1")
        if CLEAN:
            os.environ["FX_IGNORE_SYSTEM"] = "1"
        sys.path.insert(0, str(ROOT / "bin"))
        sys.path.insert(0, str(ROOT / "tests"))
        Path(os.environ["FX_STATE"]).mkdir(parents=True, exist_ok=True)
        live()
    else:
        shutil.rmtree(FOLDER / "state", ignore_errors=True)
        shutil.rmtree(FOLDER / "declaratii", ignore_errors=True)
        shutil.rmtree(SITE, ignore_errors=True)
        PORT = free_port()
        publish(PORT, {"D300": ("J1.0.0", "P1.0.0", 1), "D112": ("J1.0.0", "P1.0.0", 1), "D390": ("J1.0.0", "P1.0.0", 1)})
        SERVER = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Site)
        threading.Thread(target=SERVER.serve_forever, daemon=True).start()
        os.environ["FX_STATE"] = str(FOLDER / "state")
        os.environ["FX_NO_COMPONENTS"] = "1"
        os.environ["FX_ANAF_URL"] = f"http://127.0.0.1:{PORT}/update5/versiuni.xml"
        os.environ["FX_ANAF_JAVA"] = json.dumps([sys.executable, str(ROOT / "tests" / "fake_duk.py")])
        sys.path.insert(0, str(ROOT / "bin"))
        sys.path.insert(0, str(ROOT / "tests"))
        (FOLDER / "state").mkdir(parents=True, exist_ok=True)
        offline()
        server_routes()
        hardening()
    print("\n" + ("VALIDARE ȘI SEMNARE DECLARAȚII: TOATE TESTELE AU TRECUT" if not FAILED else f"{len(FAILED)} TESTE PICATE: {FAILED}"))
    sys.exit(1 if FAILED else 0)
