"""Componentele aplicației care nu sunt scrise de noi: LibreOffice (Word / Excel → PDF), Stirling PDF (uneltele rare),
Node.js și legătura cu Claude (chatul din editor).

Fac parte din PDF Sign: omul nu instalează nimic. La prima pornire aplicația le aduce singură, în fundal, de la sursa
lor oficială, în folderul ei (`%LOCALAPPDATA%\\fintaxy-pdf-sign\\components`), fără drepturi de administrator, fără
terminal și fără întrebări. Ce e deja instalat pe calculator (LibreOffice, Stirling PDF, Node.js) e folosit de acolo
și nu se mai descarcă. Aplicația merge și cât încă se descarcă: semnăturile, editarea și uneltele obișnuite nu au
nevoie de ele.

De ce de la sursa oficială și nu din kitul nostru: Claude Code nu poate fi redistribuit de noi, iar pentru celelalte
rămânem curați cu licențele și kitul rămâne mic (~105 MB în loc de peste 1 GB).
"""
import hashlib
import os
import shutil
import subprocess
import threading
import time
import zipfile
from pathlib import Path

from fx_sign import STATE

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PF = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
PF86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
LOCAL = Path(os.environ.get("LOCALAPPDATA", ""))
COMP = STATE / "components"
# La teste: ca pe un calculator curat, fără programele instalate pe acesta (FX_IGNORE_SYSTEM=1).
CLEAN = bool(os.environ.get("FX_IGNORE_SYSTEM"))

# Versiuni fixe, testate cu aplicația. Adresele sunt cele permanente ale fiecărui proiect.
COMPONENTS = {
    "libreoffice": {
        "name": "LibreOffice", "use": "Word, Excel, PowerPoint → PDF (când nu ai Microsoft Office)", "kind": "msi",
        "url": "https://downloadarchive.documentfoundation.org/libreoffice/old/26.8.1.1/win/x86_64/LibreOffice_26.8.1.1_Win_x86-64.msi",
        "size": 374870016,
    },
    "node": {
        "name": "Node.js", "use": "Motorul pentru chatul cu Claude", "kind": "zip",
        "url": "https://nodejs.org/dist/v24.14.1/node-v24.14.1-win-x64.zip", "size": 36358527,
    },
    "claude": {"name": "Legătura cu Claude", "use": "Chatul cu Claude din editor", "kind": "npm", "needs": "node"},
    "stirling": {
        "name": "Stirling PDF", "use": "Unelte rare: conversii exotice, verificări, broșuri", "kind": "msi",
        "url": "https://github.com/Stirling-Tools/Stirling-PDF/releases/download/v3.0.2/Stirling-PDF-windows-x86_64.msi",
    },
    # Doar la cerere (nu e în ORDER): validatoarele ANAF folosesc Java din Stirling PDF; ăsta e de rezervă, când Stirling lipsește.
    "java": {
        "name": "Java", "use": "Validatoarele ANAF (când lipsește Stirling PDF)", "kind": "zip",
        "url": "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.5%2B11/OpenJDK21U-jre_x64_windows_hotspot_21.0.5_11.zip",
        "size": 49281474, "sha256": "1749b36cfac273cee11802bf3e90caada5062de6a3fef1a3814c0568b25fd654",
    },
}
ORDER = ("libreoffice", "node", "claude", "stirling")


# ---------------------------------------------------------------- unde sunt

def _first(base: Path, pattern: str):
    try:
        return next(iter(sorted(base.glob(pattern))), None) if base.exists() else None
    except OSError:
        return None


def soffice() -> str:
    """LibreOffice, varianta de consolă (soffice.com): nu deschide nicio fereastră și nu cere niciodată Enter.
    Cel instalat pe calculator, altfel cel adus de aplicație."""
    for base in () if CLEAN else (PF / "LibreOffice" / "program", PF86 / "LibreOffice" / "program"):
        for name in ("soffice.com", "soffice.exe"):
            if (base / name).is_file():
                return str(base / name)
    hit = _first(COMP / "libreoffice", "program/soffice.com") or _first(COMP / "libreoffice", "**/program/soffice.com")
    return str(hit) if hit else ""


def stirling_dir() -> str:
    """Folderul Stirling PDF (cu libs\\stirling-pdf-*.jar și runtime\\jre): cel instalat, altfel cel adus de aplicație."""
    def ok(p: Path) -> bool:
        return bool(_first(p / "libs", "stirling-pdf-*.jar")) and (p / "runtime" / "jre" / "bin" / "java.exe").is_file()
    for p in () if CLEAN else (PF / "Stirling PDF", LOCAL / "Programs" / "Stirling PDF"):
        if ok(p):
            return str(p)
    jar = _first(COMP / "stirling", "**/libs/stirling-pdf-*.jar")
    if jar and ok(jar.parent.parent):
        return str(jar.parent.parent)
    return ""


def node() -> str:
    if not CLEAN:
        hit = shutil.which("node")
        if hit:
            return hit
        p = PF / "nodejs" / "node.exe"
        if p.is_file():
            return str(p)
    hit = _first(COMP / "node", "*/node.exe") or _first(COMP / "node", "node.exe")
    return str(hit) if hit else ""


def java() -> str:
    """Java pentru validatoarele ANAF: cel din Stirling PDF (instalat sau adus de aplicație), altfel cel adus de
    rezervă, altfel cel de pe calculator."""
    inst = stirling_dir()
    if inst:
        return str(Path(inst) / "runtime" / "jre" / "bin" / "java.exe")
    hit = _first(COMP / "java", "*/bin/java.exe") or _first(COMP / "java", "bin/java.exe")
    if hit:
        return str(hit)
    if not CLEAN:
        home = os.environ.get("JAVA_HOME")
        if home and (Path(home) / "bin" / "java.exe").is_file():
            return str(Path(home) / "bin" / "java.exe")
        return shutil.which("java") or ""
    return ""


def claude_link() -> bool:
    import acp_chat
    return bool(acp_chat.adapter_script())


def ms_office() -> bool:
    """Word instalat? (atunci Word/Excel → PDF merge cu el și LibreOffice nu e necesar)"""
    import winreg
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID"))
        return True
    except OSError:
        return False


PRESENT = {"libreoffice": lambda: bool(soffice()), "stirling": lambda: bool(stirling_dir()), "node": lambda: bool(node()),
           "claude": claude_link, "java": lambda: bool(java())}


def enabled() -> bool:
    """Aducerea automată e oprită la teste (FX_NO_COMPONENTS=1) sau din settings.json ("components": "off")."""
    if os.environ.get("FX_NO_COMPONENTS"):
        return False
    try:
        import desktop
        return desktop.settings().get("components") != "off"
    except Exception:
        return True


# ---------------------------------------------------------------- starea

JOBS: dict = {}  # id -> {"state": waiting | running | done | error, "line": ce face acum, "pct": 0-100 | None}
_LOCK = threading.Lock()
_AUTO = {"thread": None}


def job(cid: str):
    j = JOBS.get(cid)
    return dict(j) if j else None


def status() -> dict:
    items = {}
    for cid in ORDER:
        c = COMPONENTS[cid]
        items[cid] = {"name": c["name"], "use": c["use"], "installed": PRESENT[cid](), "job": job(cid)}
    busy = any((it["job"] or {}).get("state") in ("running", "waiting") for it in items.values())
    return {"ok": True, "auto": enabled(), "busy": busy, "msOffice": ms_office(), "items": items}


# ---------------------------------------------------------------- aducerea unei componente

def _download(cid: str, url: str, target: Path, size: int | None = None):
    """Descarcă cu reluare (fișierul .part rămâne dacă se întrerupe) și cu progres."""
    import requests
    part = target.with_suffix(target.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    with requests.get(url, headers=headers, stream=True, timeout=(20, 60), allow_redirects=True) as r:
        if r.status_code == 416:  # era deja întreg
            os.replace(part, target)
            return
        if have and r.status_code != 206:
            have = 0  # serverul nu știe reluare: de la capăt
        r.raise_for_status()
        total = have + int(r.headers.get("Content-Length") or 0) or size or 0
        done = have
        last = 0.0
        with open(part, "ab" if have else "wb") as f:
            for chunk in r.iter_content(1 << 18):
                f.write(chunk)
                done += len(chunk)
                if time.time() - last > 0.5:
                    last = time.time()
                    pct = int(done * 100 / total) if total else None
                    JOBS[cid].update(pct=pct, line=f"Se descarcă… {done // 1048576} din {total // 1048576} MB" if total else f"Se descarcă… {done // 1048576} MB")
    if total and part.stat().st_size != total:
        raise RuntimeError("Descărcarea s-a întrerupt. Se reia la următoarea încercare.")
    os.replace(part, target)


def _provision_msi(cid: str):
    """Despachetează un kit .msi în folderul aplicației („instalare administrativă”): doar copiază fișierele,
    fără drepturi de administrator, fără scurtături și fără nimic în registru."""
    c = COMPONENTS[cid]
    work = COMP / "_downloads"
    work.mkdir(parents=True, exist_ok=True)
    msi = work / f"{cid}.msi"
    if not msi.exists():
        _download(cid, c["url"], msi, c.get("size"))
    dest = COMP / cid
    tmp = COMP / f"{cid}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    JOBS[cid].update(pct=None, line="Se despachetează…")
    r = subprocess.run(["msiexec", "/a", str(msi), "/qn", "/norestart", f"TARGETDIR={tmp}"], stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=1800, creationflags=NO_WINDOW)
    if r.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        if r.returncode in (1620, 1619, 2):  # kit stricat: îl descărcăm din nou data viitoare
            msi.unlink(missing_ok=True)
        raise RuntimeError(f"Despachetarea nu a reușit (msiexec {r.returncode}).")
    for copy in tmp.glob("*.msi"):  # copia kitului lăsată de msiexec lângă fișiere
        copy.unlink(missing_ok=True)
    if cid == "libreoffice":
        _trim_libreoffice(tmp)
    shutil.rmtree(dest, ignore_errors=True)
    os.replace(tmp, dest)
    msi.unlink(missing_ok=True)


def _trim_libreoffice(root: Path):
    """LibreOffice despachetat are ~1,5 GB; pentru conversii în PDF ajunge mai puțin de jumătate.
    Scoatem ajutorul, fișierele de instalare în Windows și fonturile le punem unde le caută el."""
    JOBS["libreoffice"].update(line="Se curăță…")
    fonts = root / "Fonts"
    target = root / "share" / "fonts" / "truetype"
    if fonts.is_dir():
        try:
            target.mkdir(parents=True, exist_ok=True)
            for f in fonts.iterdir():
                if f.is_file() and not (target / f.name).exists():
                    os.replace(f, target / f.name)
        except OSError:
            pass
    for name in ("help", "readmes", "Fonts", "System", "System64", "sdk"):
        shutil.rmtree(root / name, ignore_errors=True)
    # dicționarele de corectură (460 MB) și traducerile interfeței (260 MB) pentru zeci de limbi: păstrăm româna și engleza
    try:
        for d in (root / "share" / "extensions").iterdir():
            if d.is_dir() and d.name.startswith("dict-") and d.name not in ("dict-en", "dict-ro"):
                shutil.rmtree(d, ignore_errors=True)
        for d in (root / "program" / "resource").iterdir():
            if d.is_dir() and not (d.name == "ro" or d.name.startswith("en")):
                shutil.rmtree(d, ignore_errors=True)
    except OSError:
        pass


def _provision_zip(cid: str):
    c = COMPONENTS[cid]
    work = COMP / "_downloads"
    work.mkdir(parents=True, exist_ok=True)
    z = work / f"{cid}.zip"
    if not z.exists():
        _download(cid, c["url"], z, c.get("size"))
    if c.get("sha256") and hashlib.sha256(z.read_bytes()).hexdigest() != c["sha256"]:
        z.unlink(missing_ok=True)
        raise RuntimeError("Fișierul descărcat nu e cel așteptat. Se descarcă din nou la următoarea încercare.")
    dest = COMP / cid
    tmp = COMP / f"{cid}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    JOBS[cid].update(pct=None, line="Se despachetează…")
    try:
        with zipfile.ZipFile(z) as zf:
            zf.extractall(tmp)
    except zipfile.BadZipFile:
        z.unlink(missing_ok=True)
        raise RuntimeError("Arhiva descărcată e stricată. Se descarcă din nou la următoarea încercare.") from None
    shutil.rmtree(dest, ignore_errors=True)
    os.replace(tmp, dest)
    z.unlink(missing_ok=True)


def _provision_npm(cid: str):
    """Legătura cu Claude: adaptorul ACP, instalat cu npm în folderul aplicației."""
    import acp_chat
    if not node():
        raise RuntimeError("Lipsește Node.js (se aduce înaintea legăturii cu Claude).")
    JOBS[cid].update(pct=None, line="Se instalează… (~1 minut)")
    acp_chat.setup()
    t = time.time()
    while acp_chat.SETUP["state"] == "running" and time.time() - t < 900:
        time.sleep(1)
    if acp_chat.SETUP["state"] != "done" or not acp_chat.adapter_script():
        raise RuntimeError(acp_chat.SETUP.get("line") or "Instalarea nu a reușit.")


def provision(cid: str) -> dict:
    """Aduce o componentă (dacă lipsește). Blochează până termină; starea e în JOBS."""
    c = COMPONENTS[cid]
    if PRESENT[cid]():
        JOBS[cid] = {"state": "done", "line": "", "pct": 100}
        return JOBS[cid]
    JOBS[cid] = {"state": "running", "line": "Se pregătește…", "pct": None, "t": time.time()}
    try:
        need = {"libreoffice": 1500, "stirling": 1300, "node": 250, "claude": 600, "java": 250}[cid]
        COMP.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(COMP).free < need * 1048576:
            raise RuntimeError(f"Nu e destul loc pe disc (trebuie ~{need} MB liberi).")
        if c.get("needs") and not PRESENT[c["needs"]]():
            provision(c["needs"])
            if not PRESENT[c["needs"]]():
                raise RuntimeError(f"Lipsește {COMPONENTS[c['needs']]['name']}.")
        {"msi": _provision_msi, "zip": _provision_zip, "npm": _provision_npm}[c["kind"]](cid)
        if not PRESENT[cid]():
            raise RuntimeError("Componenta nu a putut fi pregătită.")
        JOBS[cid].update(state="done", line="", pct=100)
    except Exception as err:
        msg = str(err)
        if "Max retries" in msg or "getaddrinfo" in msg or "Connection" in type(err).__name__:
            msg = "Nu am putut descărca (fără internet?). Se reîncearcă la următoarea pornire."
        JOBS[cid].update(state="error", line=msg[:300], pct=None)
    return JOBS[cid]


def _auto_run(only=None):
    try:
        todo = [cid for cid in (only or ORDER) if not PRESENT[cid]()]
        for cid in todo:
            JOBS[cid] = {"state": "waiting", "line": "Urmează…", "pct": None}
        for cid in todo:
            provision(cid)
    finally:
        _AUTO["thread"] = None


def auto(only=None) -> bool:
    """Pornește în fundal aducerea componentelor care lipsesc (o singură dată în același timp)."""
    if not enabled() and not only:
        return False
    with _LOCK:
        if _AUTO["thread"] is not None:
            return True
        _AUTO["thread"] = threading.Thread(target=_auto_run, args=(only,), daemon=True)
        _AUTO["thread"].start()
    return True


def install(cid: str) -> dict:
    """„Reîncearcă” din interfață: aduce din nou o componentă rămasă cu eroare."""
    if cid not in COMPONENTS:
        raise ValueError("Componentă necunoscută.")
    JOBS[cid] = {"state": "waiting", "line": "Urmează…", "pct": None}
    if not auto([cid]):
        # rulează deja aducerea celorlalte: asta intră la rând după ele
        threading.Thread(target=lambda: (_wait_idle(), auto([cid])), daemon=True).start()
    return job(cid)


def _wait_idle():
    while _AUTO["thread"] is not None:
        time.sleep(0.5)


# ---------------------------------------------------------------- LibreOffice: orice document → PDF

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
