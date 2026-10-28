"""PDF Sign ca aplicație separată pe calculator: același editor ca în panoul lui Claude, fără Claude deschis.

  pythonw desktop.py [PDF ...]   -> deschide fiecare PDF într-o fereastră; fără PDF întreabă care

Un singur server pentru toate ferestrele (portul și tokenul în app.json); se oprește singur când se
închide ultima fereastră. Comentariile „pentru AI” pleacă la aplicația aleasă în editor (Claude Code,
Claude, ChatGPT, Gemini sau doar în clipboard), alegerea rămâne ținută minte în settings.json.
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fx_sign import STATE  # noqa: E402

APP_FILE = STATE / "app.json"
SETTINGS = STATE / "settings.json"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ---------- setări ----------


def settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(**changes) -> dict:
    s = {**settings(), **changes}
    STATE.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    return s


def library() -> str:
    import fx_sign
    return fx_sign.default_library()


# ---------- alegerea fișierului ----------

_PICK = threading.Lock()


def pick_pdf(initial: str = "") -> str:
    """Fereastra Windows de alegere a unui PDF (merge și din firele serverului)."""
    import tkinter as tk
    from tkinter import filedialog
    folder = initial if initial and os.path.isdir(initial) else settings().get("lastDir", "")
    with _PICK:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)  # altfel apare în spatele editorului
        try:
            en = english()
            p = filedialog.askopenfilename(parent=root, title="Choose the PDF" if en else "Alege PDF-ul", initialdir=folder or None,
                                           filetypes=[("PDF documents" if en else "Documente PDF", "*.pdf"),
                                                      ("All files" if en else "Toate fișierele", "*.*")])
        finally:
            root.destroy()
    if not p:
        return ""
    p = str(Path(p))
    save_settings(lastDir=str(Path(p).parent))
    return p


def pick_pdfs(initial: str = "") -> list:
    """Mai multe PDF-uri deodată (Ctrl/Shift + click), pentru semnarea în bloc."""
    import tkinter as tk
    from tkinter import filedialog
    folder = initial if initial and os.path.isdir(initial) else settings().get("lastDir", "")
    with _PICK:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            en = english()
            ps = filedialog.askopenfilenames(parent=root, title="Choose the PDFs to sign" if en else "Alege PDF-urile de semnat",
                                             initialdir=folder or None, filetypes=[("PDF documents" if en else "Documente PDF", "*.pdf")])
        finally:
            root.destroy()
    ps = [str(Path(p)) for p in ps or []]
    if ps:
        save_settings(lastDir=str(Path(ps[-1]).parent))
    return ps


# ---------- aplicațiile AI ----------

APPS = [
    {"id": "claude", "name": "Claude Desktop", "hint": "aplicația Claude; captura e în clipboard (Ctrl+V)"},
    {"id": "claude-code", "name": "Claude Code", "hint": "terminal în folderul PDF-ului; vede PDF-ul și captura"},
    {"id": "chatgpt", "name": "ChatGPT", "hint": "chatgpt.com; captura e în clipboard (Ctrl+V)"},
    {"id": "gemini", "name": "Gemini", "hint": "textul e în clipboard: lipește-l cu Ctrl+V"},
    {"id": "copy", "name": "Clipboard", "hint": "doar copiază textul (și captura), lipești unde vrei"},
]
APP_BY_ID = {a["id"]: a for a in APPS}


def current_ai() -> str:
    ai = settings().get("ai", "")
    return ai if ai in APP_BY_ID else "claude"


def english() -> bool:
    return settings().get("lang") == "en"


def message(c: dict, path: str) -> str:
    """La fel ca commentMessage din hooks/register.tsx (în engleză când editorul e în engleză)."""
    en = english()
    head = "PDF comment (#{n}, page {p}): {t}" if en else "Comentariu în PDF (#{n}, pagina {p}): {t}"
    lines = [head.format(n=c.get("number", "?"), p=c.get("page"), t=str(c.get("text", "")).strip()),
             f"{'File' if en else 'Fișier'}: {path}"]
    ctx = str(c.get("context") or "").strip()
    if c.get("kind") == "region":
        if ctx:
            lines.append(f"Selected area contains: “{ctx}”" if en else f"Zona selectată conține: „{ctx}”")
        if c.get("capture"):
            lines.append(f"{'Area capture' if en else 'Captura zonei'}: {c['capture']}")
    elif ctx:
        lines.append(f"Next to the text: “{ctx}”" if en else f"Lângă textul: „{ctx}”")
    return "\n".join(lines)


def clipboard(text: str = "", image: str = ""):
    """Textul și/sau imaginea în clipboard (o singură copiere, ambele formate)."""
    ps = ("Add-Type -AssemblyName System.Windows.Forms, System.Drawing;"
          "$d = New-Object System.Windows.Forms.DataObject;"
          "if ($env:FX_TEXT) { $d.SetText([IO.File]::ReadAllText($env:FX_TEXT, [Text.Encoding]::UTF8)) };"
          "if ($env:FX_IMAGE) { $d.SetImage([System.Drawing.Image]::FromFile($env:FX_IMAGE)) };"
          "[System.Windows.Forms.Clipboard]::SetDataObject($d, $true)")
    env = {**os.environ, "FX_TEXT": "", "FX_IMAGE": image if image and os.path.isfile(image) else ""}
    if text:
        f = STATE / "ai" / "clipboard.txt"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        env["FX_TEXT"] = str(f)
    subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps], env=env, creationflags=NO_WINDOW,
                   capture_output=True, timeout=30)


def claude_code(text: str, folder: str, cid: str):
    """Claude Code într-un terminal nou, pornit în folderul PDF-ului, cu comentariul ca prim mesaj."""
    work = STATE / "ai"
    work.mkdir(parents=True, exist_ok=True)
    msg = work / f"{cid}.txt"
    # Ghilimelele drepte se pierd la trecerea argumentului spre node în PowerShell 5.1.
    msg.write_text(text.replace('"', "”"), encoding="utf-8")
    script = work / f"{cid}.ps1"
    script.write_text(
        "$Host.UI.RawUI.WindowTitle = 'Claude Code - PDF Sign'\n"
        f"Set-Location -LiteralPath '{folder.replace(chr(39), chr(39) * 2)}'\n"
        f"$m = [IO.File]::ReadAllText('{str(msg).replace(chr(39), chr(39) * 2)}', [Text.Encoding]::UTF8)\n"
        "claude $m\n",
        encoding="utf-8-sig")
    args = ["powershell.exe", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    wt = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "wt.exe"
    if wt.exists():
        subprocess.Popen([str(wt), "-d", folder, *args], close_fds=True)
    else:
        subprocess.Popen(args, cwd=folder, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0), close_fds=True)


def send(app: str, c: dict, path: str) -> dict:
    app = app if app in APP_BY_ID else current_ai()
    text = message(c, path)
    image = c.get("capture") or ""
    if app == "claude-code":
        claude_code(text, str(Path(path).parent), c["id"])
        note = "Am deschis Claude Code în folderul PDF-ului, cu comentariul ca prim mesaj."
    elif app in ("claude", "chatgpt"):
        if image:
            clipboard(image=image)
        q = urllib.parse.quote(text)
        if app == "claude":
            try:  # aplicația desktop deschide linkul claude:// ; fără ea, claude.ai în browser
                os.startfile(f"claude://claude.ai/new?q={q}")
            except OSError:
                os.startfile(f"https://claude.ai/new?q={q}")
        else:
            os.startfile(f"https://chatgpt.com/?q={q}")
        name = APP_BY_ID[app]["name"]
        note = f"Am deschis {name} cu comentariul." + (" Captura e în clipboard: lipește-o cu Ctrl+V." if image else "")
    elif app == "gemini":
        clipboard(text=text)
        os.startfile("https://gemini.google.com/app")
        note = "Am deschis Gemini; comentariul e în clipboard: lipește-l cu Ctrl+V." + (
            f" Captura: {image}" if image else "")
    else:
        clipboard(text=text, image=image)
        note = "Comentariul" + (" și captura sunt" if image else " e") + " în clipboard."
    save_settings(ai=app)
    return {"app": app, "name": APP_BY_ID[app]["name"], "note": note}


# ---------- pornirea aplicației ----------

def running():
    """Serverul pornit deja de altă fereastră, dacă mai răspunde."""
    try:
        info = json.loads(APP_FILE.read_text(encoding="utf-8"))
        url = f"http://127.0.0.1:{info['port']}/api/info?t={urllib.parse.quote(info['token'])}"
        with urllib.request.urlopen(url, timeout=3) as r:
            if json.loads(r.read()).get("standalone"):
                return info
    except Exception:
        pass
    return None


def editor_url(port: int, token: str, path: str) -> str:
    return f"http://127.0.0.1:{port}/?" + urllib.parse.urlencode({"t": token, "path": path})


def main(argv: list):
    STATE.mkdir(parents=True, exist_ok=True)
    # pythonw n-are consolă: ce ar fi mers pe stdout (evenimentele) și erorile merg în jurnal.
    log = open(STATE / "app-log.txt", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log
    print(time.strftime("%Y-%m-%d %H:%M:%S ") + "start " + " | ".join(argv))

    files = [str(Path(a).resolve()) for a in argv if a.strip() and Path(a).is_file()]
    if not files:
        f = pick_pdf()
        if not f:
            return
        files = [f]
    else:
        save_settings(lastDir=str(Path(files[-1]).parent))

    import fx_sign
    info = running()
    if info:
        for f in files:
            fx_sign.window(editor_url(info["port"], info["token"], f))
        return

    import editor_server
    srv = editor_server.make_server(library(), standalone=True)
    port = srv.server_address[1]
    APP_FILE.write_text(json.dumps({"port": port, "token": editor_server.TOKEN, "pid": os.getpid()}), encoding="utf-8")
    try:
        for f in files:
            fx_sign.window(editor_url(port, editor_server.TOKEN, f))
        editor_server.run(srv)
    finally:
        try:
            if json.loads(APP_FILE.read_text(encoding="utf-8")).get("pid") == os.getpid():
                APP_FILE.unlink()
        except (OSError, ValueError):
            pass
        print(time.strftime("%Y-%m-%d %H:%M:%S ") + "stop")


if __name__ == "__main__":
    main(sys.argv[1:])
