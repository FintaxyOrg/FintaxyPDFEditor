"""Programele de care au nevoie unele unelte (LibreOffice, Stirling PDF, Node.js pentru chatul cu Claude):
ce e instalat și instalarea lor din aplicație, fără terminal și fără întrebări (winget, pe tăcute).

Aplicația merge și fără ele: semnăturile, editarea și uneltele obișnuite nu au nevoie de nimic instalat.
"""
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PF = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
PF86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
LOCAL = Path(os.environ.get("LOCALAPPDATA", ""))

# Ce știm să instalăm: id-ul winget, la ce folosește (un rând, pentru ecranul de pornire) și cât de mare e.
PACKAGES = {
    "libreoffice": {"winget": "TheDocumentFoundation.LibreOffice", "name": "LibreOffice", "size": "~350 MB",
                    "use": "Word, Excel, PowerPoint → PDF (când nu ai Microsoft Office)"},
    "stirling": {"winget": "StirlingTools.StirlingPDF", "name": "Stirling PDF", "size": "~500 MB",
                 "use": "Unelte rare: OCR, redactare automată, conversii exotice"},
    "node": {"winget": "OpenJS.NodeJS.LTS", "name": "Node.js", "size": "~30 MB",
             "use": "Chatul cu Claude din editor"},
}


def soffice() -> str:
    """LibreOffice, varianta de consolă (soffice.com): nu deschide nicio fereastră și nu cere niciodată Enter."""
    for base in (PF / "LibreOffice" / "program", PF86 / "LibreOffice" / "program"):
        for name in ("soffice.com", "soffice.exe"):
            if (base / name).is_file():
                return str(base / name)
    return ""


def stirling_dir() -> str:
    for p in (PF / "Stirling PDF", LOCAL / "Programs" / "Stirling PDF"):
        if (p / "Stirling-PDF.exe").is_file():
            return str(p)
    return ""


def node() -> str:
    hit = shutil.which("node")
    if hit:
        return hit
    p = PF / "nodejs" / "node.exe"
    return str(p) if p.is_file() else ""


def winget() -> str:
    p = LOCAL / "Microsoft" / "WindowsApps" / "winget.exe"
    return str(p) if p.exists() else (shutil.which("winget") or "")


def ms_office() -> bool:
    """Word instalat? (atunci Word/Excel → PDF merge cu el și LibreOffice nu e necesar)"""
    import winreg
    for root in (winreg.HKEY_CLASSES_ROOT,):
        try:
            winreg.CloseKey(winreg.OpenKey(root, r"Word.Application\CLSID"))
            return True
        except OSError:
            pass
    return False


def status() -> dict:
    office = ms_office()
    items = {
        "libreoffice": {"installed": bool(soffice()), "needed": not office},
        "stirling": {"installed": bool(stirling_dir()), "needed": False},
        "node": {"installed": bool(node()), "needed": False},
    }
    for k, v in items.items():
        v.update({kk: PACKAGES[k][kk] for kk in ("name", "use", "size")})
        v["job"] = job(k)
    return {"ok": True, "winget": bool(winget()), "msOffice": office, "items": items}


# ---------- instalarea ----------

JOBS: dict = {}  # id -> {"state": running | done | error, "line": ultimul rând de la winget, "t": start}
_LOCK = threading.Lock()


def job(pid: str):
    j = JOBS.get(pid)
    return {k: v for k, v in j.items() if k != "proc"} if j else None


def _clean(line: str) -> str:
    """Rândurile winget au bare de progres desenate cu caractere speciale: păstrăm doar textul."""
    line = re.sub(r"[\u2580-\u259f\u2500-\u257f\\|/\-]{2,}", " ", line)
    return re.sub(r"\s+", " ", line).strip()[:160]


def _run(pid: str):
    pkg = PACKAGES[pid]
    j = JOBS[pid]
    cmd = [winget(), "install", "--id", pkg["winget"], "-e", "--silent", "--accept-source-agreements",
           "--accept-package-agreements", "--disable-interactivity", "--no-upgrade"]
    try:
        p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             creationflags=NO_WINDOW, text=True, encoding="utf-8", errors="replace")
        j["proc"] = p
        # winget desenează progresul cu \r pe același rând: citim pe bucăți, nu pe rânduri.
        buf = ""
        while True:
            ch = p.stdout.read(1)
            if not ch:
                break
            if ch in "\r\n":
                text = _clean(buf)
                if text:
                    j["line"] = text
                buf = ""
            else:
                buf += ch
        code = p.wait()
        installed = {"libreoffice": soffice, "stirling": stirling_dir, "node": node}[pid]()
        if code == 0 or installed:
            j.update(state="done", line="Instalat.")
        elif code & 0xFFFFFFFF in (0x8A15002B, 0x8A150061):  # deja instalat
            j.update(state="done", line="Era deja instalat.")
        else:
            j.update(state="error", line=(j.get("line") or "Instalarea nu a reușit.") + f" (cod {code & 0xFFFFFFFF:X})")
    except Exception as err:
        j.update(state="error", line=f"Instalarea nu a pornit: {err}")
    finally:
        j.pop("proc", None)
        j["end"] = time.time()


def install(pid: str) -> dict:
    """Pornește instalarea în fundal. Windows poate cere o singură confirmare de administrator (fereastra lui albastră)."""
    if pid not in PACKAGES:
        raise ValueError("Program necunoscut.")
    if not winget():
        raise RuntimeError("Calculatorul nu are winget (App Installer din Microsoft Store). Instalează programul de pe site-ul lui.")
    with _LOCK:
        j = JOBS.get(pid)
        if j and j["state"] == "running":
            return job(pid)
        JOBS[pid] = {"state": "running", "line": "Pornesc instalarea…", "t": time.time()}
        threading.Thread(target=_run, args=(pid,), daemon=True).start()
    return job(pid)


# ---------- LibreOffice: orice document → PDF ----------

def office_to_pdf(src: Path, dst: Path, state_dir: Path, timeout: int = 240) -> None:
    """Convertește un document (Word, Excel, PowerPoint, ODT, RTF, TXT...) în PDF cu LibreOffice, fără nicio fereastră.
    Profil separat (în folderul aplicației): nu se încurcă cu un LibreOffice deschis de om și nu arată niciun asistent."""
    exe = soffice()
    if not exe:
        raise RuntimeError("LIBREOFFICE_MISSING")
    profile = state_dir / "lo-profile"
    work = state_dir / "lo-out" / f"{os.getpid()}-{threading.get_ident()}-{int(time.time() * 1000)}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        cmd = [exe, "--headless", "--norestore", "--nologo", "--nolockcheck", "--nodefault",
               f"-env:UserInstallation={profile.as_uri()}", "--convert-to", "pdf", "--outdir", str(work), str(src)]
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
        made = sorted(work.glob("*.pdf"))
        if not made:
            err = (r.stderr or r.stdout or b"").decode("utf-8", "replace").strip().splitlines()
            raise RuntimeError(err[-1] if err else "LibreOffice nu a putut converti fișierul.")
        os.replace(made[0], dst)
    finally:
        shutil.rmtree(work, ignore_errors=True)
