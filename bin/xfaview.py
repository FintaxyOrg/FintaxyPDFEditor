"""Formularele XFA dinamice (PDF-urile „inteligente” ale ANAF: D300, D394, D101, D112 nesalvate din Adobe).

În fișier, pagina PDF e doar mesajul „Please wait…”: conținutul adevărat stă în formularul XFA, pe care MuPDF nu
îl desenează. Aici îl desenăm cu pdf.js (motorul din Firefox, care știe XFA) și îl tipărim cu Edge, fără fereastră,
într-un PDF de vizualizare ținut în STATE/xfa. Editorul arată paginile din acest PDF; fișierul original rămâne
neatins și el e cel care se semnează.
"""
import functools
import hashlib
import http.server
import json
import os
import secrets
import subprocess
import sys
import threading
from pathlib import Path

import fitz

import fx_sign

XFA_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "editor" / "xfa"
CACHE = fx_sign.STATE / "xfa"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PLACEHOLDER = ("please wait", "proper contents of the document")
TYPES = {".html": "text/html; charset=utf-8", ".mjs": "text/javascript", ".js": "text/javascript", ".css": "text/css",
         ".pdf": "application/pdf", ".json": "application/json", ".otf": "font/otf", ".ttf": "font/ttf"}
_lock = threading.Lock()
_failed: dict = {}

# Fonturile Adobe ale formularelor ANAF (Myriad Pro, Minion Pro) nu sunt în Windows, dar vin cu Acrobat / Adobe Reader.
# Dacă sunt pe calculator, formularul se desenează cu ele (ca în Adobe); altfel pdf.js pune un font asemănător.
ADOBE_FONT_DIRS = [Path(os.environ.get(v, d)) / sub for v, d in (("ProgramFiles", r"C:\Program Files"),
                                                                   ("ProgramFiles(x86)", r"C:\Program Files (x86)"))
                   for sub in (r"Adobe\Acrobat DC\Resource\Font", r"Adobe\Acrobat Reader DC\Resource\Font",
                               r"Adobe\Acrobat Reader\Resource\Font")]
ADOBE_FONT_DIRS += [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
                    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"]
FONT_FILES = {  # fișier -> (familie, grosime, stil)
    f"{fam.replace(' ', '')}-{name}.otf": (fam, weight, style)
    for fam in ("Myriad Pro", "Minion Pro")
    for name, weight, style in (("Regular", "normal", "normal"), ("Bold", "bold", "normal"), ("It", "normal", "italic"),
                                ("BoldIt", "bold", "italic"))
}


@functools.lru_cache(maxsize=1)
def adobe_fonts() -> dict:
    """Fonturile Adobe găsite pe calculator: nume fișier -> cale (căutate o dată; editorul întreabă la fiecare pagină)."""
    found = {}
    for d in ADOBE_FONT_DIRS:
        for name in FONT_FILES:
            if name not in found and (d / name).is_file():
                found[name] = d / name
    return found


def placeholder(doc) -> bool:
    """Paginile din fișier sunt doar mesajul pentru cititoarele care nu știu XFA?"""
    if doc.page_count == 0 or doc.page_count > 2:
        return False
    text = doc[0].get_text().lower()
    return any(p in text for p in PLACEHOLDER)


def needs(doc) -> bool:
    """Formular XFA dinamic: catalogul spune /NeedsRendering true (paginile trebuie desenate din formular) sau, la
    fișierele fără acest semn, pagina e doar mesajul de așteptare."""
    if not fx_sign.is_xfa(doc):
        return False
    return doc.xref_get_key(doc.pdf_catalog(), "NeedsRendering")[1] == "true" or placeholder(doc)


RENDER_VERSION = 8  # crește la orice schimbare a desenării, ca PDF-urile de vizualizare vechi să fie refăcute


def _key(path: Path) -> str:
    st = path.stat()
    fonts = ",".join(sorted(adobe_fonts()))
    return hashlib.sha1(f"{RENDER_VERSION}|{path}|{st.st_mtime_ns}|{st.st_size}|{fonts}".encode("utf-8", "replace")
                        ).hexdigest()[:24]


GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")


def _serve(pdf: bytes, wait: int):
    """Server local doar pentru această tipărire: paginile pdf.js din editor/xfa și PDF-ul, sub o cale greu de ghicit.
    Edge tipărește la evenimentul „load”, iar pdf.js desenează după el; de aceea pagina are o imagine („hold.gif”) pe
    care o ținem în așteptare până când pagina anunță că a terminat („done”)."""
    token = secrets.token_hex(12)
    done = threading.Event()
    fonts = adobe_fonts()
    fonts_json = json.dumps([{"file": n, "family": FONT_FILES[n][0], "weight": FONT_FILES[n][1],
                              "style": FONT_FILES[n][2]} for n in fonts]).encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if not path.startswith(f"/{token}/"):
                return self.send_error(404)
            name = path[len(token) + 2:]
            if name == "doc.pdf":
                data = pdf
            elif name == "done":
                done.set()
                data = b"ok"
            elif name == "hold.gif":
                done.wait(wait)
                data = GIF
            elif name == "fonts.json":
                data = fonts_json
            elif name.startswith("font/") and name[5:] in fonts:
                data = fonts[name[5:]].read_bytes()
            else:
                f = (XFA_DIR / name).resolve()
                if XFA_DIR.resolve() not in f.parents or not f.is_file():
                    return self.send_error(404)
                data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", TYPES.get(Path(name).suffix.lower(), "application/octet-stream"))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/{token}/xfa.html"


def _print(url: str, out: Path, timeout: int):
    profile = CACHE / "profile"
    subprocess.run([fx_sign.browser(), "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", "--no-first-run",
                    "--no-pdf-header-footer",
                    f"--print-to-pdf={out}", url],
                   capture_output=True, timeout=timeout, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)


def _good(pdf: Path) -> bool:
    if not pdf.exists() or pdf.stat().st_size < 500:
        return False
    try:
        with fitz.open(pdf) as d:
            text = d[0].get_text() if d.page_count else ""
            return d.page_count > 0 and "XFA-ERROR" not in text and not placeholder(d)
    except Exception:
        return False


def preview(path, timeout: int = 150):
    """PDF-ul de vizualizare al unui formular XFA dinamic (din cache sau făcut acum); None dacă nu se poate face."""
    path = Path(path)
    key = _key(path)
    target = CACHE / f"{key}.pdf"
    if target.exists():
        return target
    with _lock:
        if target.exists():
            return target
        if key in _failed:
            return None
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = CACHE / f"{key}-{os.getpid()}.tmp.pdf"
        tmp.unlink(missing_ok=True)
        server, url = _serve(path.read_bytes(), timeout - 30)
        try:
            _print(url, tmp, timeout)
        except Exception as e:  # Edge lipsă sau blocat: editorul arată pagina din fișier, ca până acum
            _failed[key] = str(e)
        finally:
            server.shutdown()
            server.server_close()
        if not _good(tmp):
            tmp.unlink(missing_ok=True)
            _failed.setdefault(key, "Edge nu a putut desena formularul.")
            return None
        os.replace(tmp, target)
        for old in sorted(CACHE.glob("*.pdf"), key=lambda f: f.stat().st_mtime)[:-40]:  # păstrăm ultimele 40
            old.unlink(missing_ok=True)
        return target


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for arg in sys.argv[1:]:
        with fitz.open(arg) as d:
            print(arg, "| XFA dinamic:", needs(d))
            if needs(d):
                p = preview(arg)
                print("   ->", p, "|", fitz.open(p).page_count if p else _failed)
