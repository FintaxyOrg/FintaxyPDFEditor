"""Aplicația construită (dist\\PDF Sign\\PDF Sign.exe), pornită ca la un om, dar cu stare separată:
versiunea, limbile OCR din pachet, semnătura electronică (certificat de test .pfx), toate uneltele locale,
chatul (agent simulat), închiderea singură după ultima fereastră.

  python tests/test_packaged.py [FOLDER] [--stirling] [--sleep]     (--sleep: și testul de 3 minute cu pagina adormită)

Fereastra editorului (Edge) se deschide în afara ecranului cât durează testul și e închisă la final.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "bin"))

import make_fixtures  # noqa: E402

PORT = "8791"
FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  [{str(detail)[:200]}]" if detail and not ok else ""), flush=True)
    if not ok:
        FAILED.append(name)
    return ok


def api(method, path, body=None, q=None, timeout=120):
    url = f"http://127.0.0.1:{PORT}/api/{path}?" + urllib.parse.urlencode({"t": "test", **(q or {})})
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return {"ok": False, **json.loads(e.read())}
        except ValueError:
            return {"ok": False, "error": f"HTTP {e.code}"}


def editor_windows():
    """Procesele Edge ale ferestrei de test (după portul din linia de comandă)."""
    ps = (f"Get-CimInstance Win32_Process | Where-Object {{ $_.Name -eq 'msedge.exe' -and $_.CommandLine -match '--app=http://127.0.0.1:{PORT}/' }} "
          "| ForEach-Object { $_.ProcessId }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    return [int(x) for x in r.stdout.split() if x.isdigit()]


def main(folder: Path):
    exe = ROOT / "dist" / "PDF Sign" / "PDF Sign.exe"
    if not exe.is_file():
        print(f"Nu există {exe}: rulează întâi app\\build.ps1")
        return 2
    f = make_fixtures.make(folder / "docs")
    env = {**os.environ, "FX_STATE": str(folder / "state"), "FX_PORT": PORT, "FX_TOKEN": "test", "FX_NO_COMPONENTS": "1", "FX_WINDOW_POS": "-3000,100",
           "FX_TEST_PFX": str(f["pfx_ec"]), "FX_TEST_PFX_PASS": make_fixtures.PFX_PASS,
           "FX_ACP_CMD": json.dumps([sys.executable, str(ROOT / "tests" / "fake_acp_agent.py")])}
    (folder / "state").mkdir(parents=True, exist_ok=True)
    # ca un om care a trecut de ghid: aplicația deschide direct PDF-ul primit
    (folder / "state" / "settings.json").write_text(json.dumps({"onboarded": "test", "library": str(folder / "semnaturi")}), encoding="utf-8")
    (folder / "semnaturi").mkdir(exist_ok=True)
    t0 = time.time()
    app = subprocess.Popen([str(exe), str(f["doc"])], env=env, cwd=str(exe.parent))
    info = {}
    for _ in range(80):
        time.sleep(0.5)
        try:
            info = api("GET", "info", timeout=3)
            if info.get("ok"):
                break
        except Exception:
            pass
    print(f"== aplicația construită: pornire în {round(time.time() - t0, 1)} s ==")
    try:
        check("aplicația pornește și răspunde", info.get("ok") and info.get("standalone"), info)
        want = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
        check(f"versiunea din pachet = {want}", info.get("version") == want, info.get("version"))
        time.sleep(2)
        wins = editor_windows()
        check("fereastra editorului s-a deschis (Edge)", bool(wins), wins)
        d = api("GET", "doc", q={"path": str(f["doc"])})
        check("documentul se deschide", len(d.get("pages", [])) == 3, d)

        # semnătura electronică în aplicația construită (pyHanko + PowerShell din pachet), cu certificatul de test P-384
        src = folder / "docs" / "de-semnat.pdf"
        src.write_bytes(f["doc"].read_bytes())
        r = api("POST", "certsign", {"thumb": "", "items": [{"path": str(src), "place": {"page": 1, "rect": [300, 600, 520, 680]}}], "reason": "Test"})
        res = (r.get("results") or [{}])[0]
        if check("semnătură electronică (certificat de test, P-384)", res.get("ok"), r):
            from pyhanko.pdf_utils.reader import PdfFileReader
            from pyhanko.sign.validation import validate_pdf_signature
            from pyhanko_certvalidator import ValidationContext
            with open(res["out"], "rb") as fh:
                sig = PdfFileReader(fh, strict=False).embedded_signatures[0]
                st = validate_pdf_signature(sig, ValidationContext(trust_roots=[sig.signer_cert], allow_fetching=False))
            check("semnătura e validă, SHA-384", st.intact and st.valid and st.md_algorithm == "sha384", st.md_algorithm)
        check("starea semnării revine la «nimic în curs»", api("GET", "certsign/status").get("active") is False)
        certs = api("GET", "certs")
        check("lista certificatelor din Windows (citire directă) merge în pachet", isinstance(certs, list), certs)

        # toate uneltele locale + editorul, prin API-ul aplicației construite
        args = [sys.executable, str(ROOT / "tests" / "test_tools.py"), str(folder), PORT] + ([] if "--stirling" in sys.argv else ["--no-stirling"])
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        tail = [ln for ln in r.stdout.splitlines() if "trec" in ln or "FAIL" in ln or "[" in ln[:6]]
        check("editorul și toate uneltele locale trec în aplicația construită (OCR, LibreOffice, Edge incluse)", r.returncode == 0, " | ".join(tail[-8:]))
        for ln in r.stdout.splitlines():
            if ln.startswith(("A.", "B.", "C.")) or "FAIL" in ln:
                print("      " + ln)

        # chatul (agent simulat)
        st = api("GET", "chat/status")
        check("chatul e disponibil", st.get("available"), st)
        api("POST", "chat/send", {"path": str(f["doc"]), "text": "Ce număr are contractul?", "page": 1})
        text, done = "", False
        for _ in range(100):
            time.sleep(0.3)
            ev = api("GET", "chat/events", q={"path": str(f["doc"]), "since": 0, "wait": 1})
            text = "".join(e.get("text", "") for e in ev.get("events", []) if e["type"] == "text")
            done = any(e["type"] == "done" for e in ev.get("events", []))
            if done:
                break
        check("chatul răspunde prin ACP din aplicația construită", done and "42" in text, text[:120])
    finally:
        # închidem fereastra de test; aplicația trebuie să se oprească singură în câteva secunde
        # închidere obișnuită (ca butonul X): pagina apucă să anunțe serverul; abia apoi, cu forța
        for pid in editor_windows():
            subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(4)
        for pid in editor_windows():
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        gone = False
        for _ in range(60):
            if app.poll() is not None:
                gone = True
                break
            time.sleep(0.5)
        check("după închiderea ferestrei, aplicația se oprește singură", gone)
        if not gone:
            subprocess.run(["taskkill", "/PID", str(app.pid), "/T", "/F"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        # Stirling-ul pornit de instanța de test (dacă a apucat)
        try:
            sj = json.loads((folder / "state" / "stirling.json").read_text(encoding="utf-8"))
            subprocess.run(["taskkill", "/PID", str(sj["pid"]), "/T", "/F"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass
        log = folder / "state" / "app-log.txt"
        if log.exists():
            # Testele provoacă intenționat erori (parolă greșită, pagină inexistentă...): le arătăm pe tipuri, de citit.
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            kinds = sorted({ln.split(":")[0] for i, ln in enumerate(lines) if i and not ln.startswith((" ", "Traceback", "{", "20"))
                            and ":" in ln and lines[i - 1].startswith(" ")})
            print(f"      jurnal: erori apărute (provocate de teste): {kinds}")
            crash = [ln for ln in lines if ln.startswith(("ModuleNotFoundError", "ImportError", "FileNotFoundError: [Errno 2] No such file or directory: 'C:\\\\Users"))]
            check("jurnalul aplicației: niciun modul sau fișier lipsă din pachet", not crash, crash[:3])
    start_screen(folder, exe)
    print("\n" + ("APLICAȚIA CONSTRUITĂ A TRECUT TOATE TESTELE" if not FAILED else f"{len(FAILED)} TESTE PICATE: {FAILED}"))
    return 1 if FAILED else 0


def start_screen(folder: Path, exe: Path):
    """Pornită fără niciun PDF (din scurtătură), la prima folosire: ecranul de start cu ghidul, iar aplicația rămâne
    deschisă (nu se mai închide dacă omul nu alege un fișier)."""
    global PORT
    PORT = "8792"
    state = folder / "state-start"
    state.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "FX_STATE": str(state), "FX_PORT": PORT, "FX_TOKEN": "test", "FX_NO_COMPONENTS": "1", "FX_WINDOW_POS": "-3000,100"}
    env.pop("FX_TEST_PFX", None)
    print("== pornire fără PDF (prima folosire) ==")
    app = subprocess.Popen([str(exe)], env=env, cwd=str(exe.parent))
    info = {}
    try:
        for _ in range(60):
            time.sleep(0.5)
            try:
                info = api("GET", "info", timeout=3)
                if info.get("ok"):
                    break
            except Exception:
                pass
        check("fără PDF: aplicația pornește pe ecranul de start", info.get("ok") and not info.get("onboarded"), info)
        time.sleep(8)
        check("fără PDF: aplicația rămâne deschisă", app.poll() is None)
        if "--sleep" in sys.argv:
            # Pagina „adormită” (fereastra acoperită, calculator pe baterie): pagina nu mai dă semn de viață.
            # O simulăm înghețând procesele Edge ale ferestrei mai mult decât răbdarea serverului (150 s + 6 s);
            # aplicația trebuie să rămână pornită cât fereastra există.
            import ctypes
            ps2 = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'msedge.exe' -and $_.CommandLine -match 'state-start' } "
                   "| ForEach-Object { $_.ProcessId }")
            out = subprocess.run(["powershell", "-NoProfile", "-Command", ps2], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            pids = [int(x) for x in out.stdout.split() if x.isdigit()]
            nt, k32 = ctypes.WinDLL("ntdll"), ctypes.WinDLL("kernel32")
            k32.OpenProcess.restype = ctypes.c_void_p
            handles = [h for h in (k32.OpenProcess(0x0800, False, pid) for pid in pids) if h]
            for h in handles:
                nt.NtSuspendProcess(ctypes.c_void_p(h))
            print(f"      {len(handles)} procese Edge înghețate; aștept 175 s…", flush=True)
            time.sleep(175)
            alive = app.poll() is None
            try:
                alive = alive and api("GET", "info", timeout=5).get("ok")
            except Exception:
                alive = False
            for h in handles:
                nt.NtResumeProcess(ctypes.c_void_p(h))
                k32.CloseHandle(ctypes.c_void_p(h))
            check("pagina adormită 175 s: aplicația rămâne pornită cât fereastra există", bool(handles) and alive)
            time.sleep(3)
        ps = (f"Get-CimInstance Win32_Process | Where-Object {{ $_.Name -eq 'msedge.exe' -and $_.CommandLine -match '--app=http://127.0.0.1:{PORT}/' }} "
              "| ForEach-Object { $_.CommandLine }")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        check("fără PDF: fereastra e pe ecranul de start (fără fișier)", "path=&pick=1" in r.stdout, r.stdout[:200])
        js = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/editor/assist.js", timeout=5).read().decode("utf-8")
        check("pachetul are ghidul care revine după „Renunță” și butonul „?”", "suspend" in js and "btnHelp" in js)
    finally:
        for pid in editor_windows():
            subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(4)
        for pid in editor_windows():
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        gone = False
        for _ in range(60):
            if app.poll() is not None:
                gone = True
                break
            time.sleep(0.5)
        check("fără PDF: se oprește după închiderea ferestrei", gone)
        if not gone:
            subprocess.run(["taskkill", "/PID", str(app.pid), "/T", "/F"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            sj = json.loads((state / "stirling.json").read_text(encoding="utf-8"))
            subprocess.run(["taskkill", "/PID", str(sj["pid"]), "/T", "/F"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(main(Path(args[0]).resolve() if args else Path(tempfile.mkdtemp(prefix="pdfsign-pkg-"))))
