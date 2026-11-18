"""Chatul cu Claude din editor, prin ACP (Agent Client Protocol), la fel ca „Ask AI” din Fintaxy CRM:
aplicația pornește adaptorul `@agentclientprotocol/claude-agent-acp` (Claude Code, pe abonamentul omului, fără
cheie API) și vorbește cu el JSON-RPC pe stdin/stdout, câte un mesaj pe rând.

  editor  --HTTP-->  editor_server  --acp_chat-->  node claude-agent-acp  -->  Claude Code

Fiecare PDF deschis are conversația lui (o sesiune ACP cu folderul PDF-ului ca folder de lucru). Ce face Claude
ajunge la editor ca evenimente numerotate, citite cu long-poll (/api/chat/events). Orice acțiune care schimbă ceva
(scriere de fișiere, comenzi) cere acordul omului în chat: nimic nu e aprobat din oficiu.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

from fx_sign import STATE

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ADAPTER_PKG = "@agentclientprotocol/claude-agent-acp"
ADAPTER_VERSION = "0.94.0"  # aceeași versiune ca în Fintaxy CRM
ACP_DIR = STATE / "acp"
PROTOCOL_VERSION = 1
APP_VERSION = "0.15.0"  # doar ca etichetă a clientului ACP


# ---------------------------------------------------------------- ce e instalat

def node() -> str:
    """Node.js instalat pe calculator sau cel adus de aplicație în folderul ei (bin/deps.py)."""
    import deps
    return deps.node()


def npm() -> str:
    n = node()
    if n:
        p = Path(n).with_name("npm.cmd")
        if p.is_file():
            return str(p)
    return shutil.which("npm.cmd") or shutil.which("npm") or ""


def adapter_script() -> str:
    """Scriptul adaptorului: cel instalat de aplicație în folderul ei (sau cel dat prin FX_ACP_ADAPTER, la teste)."""
    env = os.environ.get("FX_ACP_ADAPTER", "")
    if env and os.path.isfile(env):
        return env
    pkg = ACP_DIR / "node_modules" / "@agentclientprotocol" / "claude-agent-acp"
    try:
        meta = json.loads((pkg / "package.json").read_text(encoding="utf-8"))
        b = meta.get("bin")
        rel = b if isinstance(b, str) else next(iter((b or {}).values()), "dist/index.js")
        script = pkg / rel
        return str(script) if script.is_file() else ""
    except (OSError, ValueError):
        return ""


def logged_in() -> bool:
    """Claude Code e conectat pe calculatorul ăsta (claude, apoi /login) și conectarea nu a expirat?"""
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return True
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    try:
        o = json.loads((base / ".credentials.json").read_text(encoding="utf-8")).get("claudeAiOauth") or {}
    except (OSError, ValueError):
        return False
    if not (o.get("accessToken") or o.get("refreshToken")):
        return False  # fișierul există, dar conectarea a expirat (jetoanele au fost golite)
    exp = o.get("refreshTokenExpiresAt")
    return not exp or exp > time.time() * 1000 or bool(o.get("accessToken") and (o.get("expiresAt") or 0) > time.time() * 1000)


def agent_command() -> list:
    """Comanda care pornește agentul ACP: node + scriptul adaptorului (sau FX_ACP_CMD, o listă JSON, la teste)."""
    custom = os.environ.get("FX_ACP_CMD", "")
    if custom:
        try:
            return [str(x) for x in json.loads(custom)]
        except ValueError:
            return []
    n, script = node(), adapter_script()
    return [n, script] if n and script else []


def status() -> dict:
    n, a, li = node(), adapter_script(), logged_in()
    if os.environ.get("FX_ACP_CMD"):
        n = a = li = True
    step = "" if (n and a and li) else "node" if not n else "adapter" if not a else "login"
    return {"ok": True, "available": not step, "step": step, "node": bool(n), "adapter": bool(a), "loggedIn": li,
            "setup": SETUP.copy(), "running": AGENT.alive()}


# ---------------------------------------------------------------- instalarea adaptorului (o dată, ~1 minut)

SETUP = {"state": "", "line": ""}
_SETUP_LOCK = threading.Lock()


def _setup_run():
    try:
        ACP_DIR.mkdir(parents=True, exist_ok=True)
        pkg = ACP_DIR / "package.json"
        if not pkg.exists():
            pkg.write_text(json.dumps({"name": "pdf-sign-acp", "private": True, "version": "1.0.0"}), encoding="utf-8")
        cmd = [npm(), "install", "--no-audit", "--no-fund", "--loglevel=error", f"{ADAPTER_PKG}@{ADAPTER_VERSION}"]
        # npm.cmd e un fișier batch: are nevoie de cmd.exe, dar fără fereastră și fără nimic de tastat.
        # Node.js adus de aplicație nu e în PATH: scripturile de instalare ale pachetelor îl caută acolo.
        env = {**os.environ, "PATH": str(Path(node()).parent) + os.pathsep + os.environ.get("PATH", "")}
        p = subprocess.run(cmd, cwd=str(ACP_DIR), stdin=subprocess.DEVNULL, capture_output=True, timeout=900,
                           creationflags=NO_WINDOW, shell=False, env=env)
        if adapter_script():
            SETUP.update(state="done", line="Gata.")
        else:
            err = (p.stderr or p.stdout or b"").decode("utf-8", "replace").strip().splitlines()
            SETUP.update(state="error", line=(err[-1] if err else "Instalarea nu a reușit.")[:300])
    except Exception as err:
        SETUP.update(state="error", line=f"Instalarea nu a pornit: {err}")


def setup() -> dict:
    """Instalează adaptorul ACP în folderul aplicației (npm, fără fereastră)."""
    if adapter_script():
        SETUP.update(state="done", line="Gata.")
        return SETUP.copy()
    if not npm():
        raise RuntimeError("Lipsește Node.js (se instalează singur, în fundal).")
    with _SETUP_LOCK:
        if SETUP["state"] != "running":
            SETUP.update(state="running", line="Instalez legătura cu Claude (o singură dată, ~1 minut)…")
            threading.Thread(target=_setup_run, daemon=True).start()
    return SETUP.copy()


def open_login():
    """Deschide Claude Code într-un terminal, ca omul să se conecteze o dată (/login deschide browserul)."""
    work = STATE / "ai"
    work.mkdir(parents=True, exist_ok=True)
    script = work / "login.ps1"
    script.write_text(
        "$Host.UI.RawUI.WindowTitle = 'Claude - conectare (PDF Sign)'\n"
        "Write-Host 'Conectare Claude pentru PDF Sign' -ForegroundColor Cyan\n"
        "Write-Host 'Scrie /login si apasa Enter, apoi urmeaza pasii din browser. La final inchide fereastra asta.'\n"
        "Write-Host ''\n"
        "if (Get-Command claude -ErrorAction SilentlyContinue) { claude } else { npx -y @anthropic-ai/claude-code@latest }\n",
        encoding="utf-8-sig")
    args = ["powershell.exe", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    subprocess.Popen(args, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0), close_fds=True)


# ---------------------------------------------------------------- mediul adaptorului

KEEP_CLAUDE_ENV = {"CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_GIT_BASH_PATH", "CLAUDE_CODE_EXECUTABLE",
                   "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"}


def child_env() -> dict:
    """Ca în CRM: adaptorul nu vede chei API (ar factura pe ele, nu pe abonament), nici variabilele unei sesiuni
    Claude Code părinte (când aplicația e pornită dintr-una), nici alte secrete din mediu."""
    env = {}
    for k, v in os.environ.items():
        if k in KEEP_CLAUDE_ENV:
            env[k] = v
            continue
        if re.match(r"(?i)^(ANTHROPIC_|CLAUDE|FX_TEST_)", k):
            continue
        if re.search(r"(?i)(SECRET|PASSWORD|PASSWD|API_KEY|APIKEY|_TOKEN$|PRIVATE_KEY)", k):
            continue
        env[k] = v
    env.update(CLAUDE_AGENT_SDK_CLIENT_APP=f"fintaxy-pdf-sign/{APP_VERSION}", CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION="false",
               DISABLE_AUTOUPDATER="1")
    return env


# ---------------------------------------------------------------- legătura JSON-RPC cu adaptorul

class AcpError(RuntimeError):
    pass


class Agent:
    """Un singur proces al adaptorului pentru toată aplicația; fiecare PDF are sesiunea lui."""

    def __init__(self):
        self.proc = None
        self.lock = threading.RLock()
        self.wlock = threading.Lock()
        self.next_id = 0
        self.pending = {}      # id -> {"event", "result", "error"}
        self.sessions = {}     # sessionId -> Chat
        self.caps = {}
        self.stderr_tail = []
        self.last_error = ""

    def alive(self) -> bool:
        return bool(self.proc and self.proc.poll() is None)

    def start(self):
        with self.lock:
            if self.alive():
                return
            cmd = agent_command()
            if not cmd:
                raise AcpError("Legătura cu Claude nu e instalată încă.")
            self.pending.clear()
            self.sessions.clear()
            self.stderr_tail = []
            self.last_error = ""
            STATE.mkdir(parents=True, exist_ok=True)
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         cwd=str(STATE), env=child_env(), creationflags=NO_WINDOW)
            threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()
            threading.Thread(target=self._errors, args=(self.proc,), daemon=True).start()
            try:
                init = self.request("initialize", {
                    "protocolVersion": PROTOCOL_VERSION,
                    "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False},
                    "clientInfo": {"name": "fintaxy-pdf-sign", "title": "PDF Sign (Fintaxy)", "version": APP_VERSION},
                }, timeout=60)
            except Exception as err:
                self.stop()
                raise AcpError(f"Claude Code nu a pornit: {err}") from None
            self.caps = init.get("agentCapabilities") or {}

    def stop(self):
        with self.lock:
            p, self.proc = self.proc, None
            if p and p.poll() is None:
                try:
                    p.stdin.close()
                    p.wait(2)
                except Exception:
                    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
            for chat in list(self.sessions.values()):
                chat.agent_gone("Claude Code s-a oprit.")
            self.sessions.clear()
            self._fail_pending()

    def _fail_pending(self):
        """Cererile care așteaptă un răspuns află imediat că agentul s-a oprit (fără lacăt: îl poate ține cel care așteaptă)."""
        why = "Claude Code s-a oprit." + (f" ({self.last_error})" if self.last_error else "")
        for rid in list(self.pending):
            w = self.pending.pop(rid, None)
            if w:
                w["error"] = {"message": why}
                w["event"].set()

    # ---- scriere / citire
    def _write(self, msg: dict):
        p = self.proc
        if not p or p.poll() is not None:
            raise AcpError("Claude Code nu rulează.")
        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        with self.wlock:
            p.stdin.write(data)
            p.stdin.flush()

    def request(self, method: str, params: dict, timeout: float | None = 120):
        with self.lock:
            self.next_id += 1
            rid = self.next_id
            w = {"event": threading.Event(), "result": None, "error": None}
            self.pending[rid] = w
        self._write({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        if not w["event"].wait(timeout):
            self.pending.pop(rid, None)
            raise AcpError(f"Claude Code nu a răspuns la „{method}” în {int(timeout)} s.")
        if w["error"]:
            e = w["error"]
            detail = e.get("data")
            detail = detail.get("details") if isinstance(detail, dict) else detail
            raise AcpError(str(detail or e.get("message") or e))
        return w["result"] or {}

    def notify(self, method: str, params: dict):
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def respond(self, rid, result=None, error=None):
        msg = {"jsonrpc": "2.0", "id": rid}
        if error:
            msg["error"] = error
        else:
            msg["result"] = result if result is not None else {}
        try:
            self._write(msg)
        except AcpError:
            pass

    def _errors(self, p):
        for raw in iter(p.stderr.readline, b""):
            line = raw.decode("utf-8", "replace").rstrip()
            if line:
                self.stderr_tail = (self.stderr_tail + [line])[-30:]

    def _reader(self, p):
        try:
            for raw in iter(p.stdout.readline, b""):
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("{"):
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                try:
                    self._dispatch(msg)
                except Exception:
                    traceback.print_exc(file=sys.stderr)
        finally:
            if self.proc is p:
                time.sleep(0.15)  # ultimele rânduri de pe stderr (de ce s-a oprit)
                tail = next((ln for ln in reversed(self.stderr_tail) if ln.strip()), "")
                self.last_error = tail[:300]
                self._fail_pending()
                self.stop()

    def _dispatch(self, msg: dict):
        if "method" not in msg:  # răspuns la o cerere a noastră
            w = self.pending.pop(msg.get("id"), None)
            if w:
                w["result"], w["error"] = msg.get("result"), msg.get("error")
                w["event"].set()
            return
        method, params, rid = msg["method"], msg.get("params") or {}, msg.get("id")
        chat = self.sessions.get(params.get("sessionId"))
        if method == "session/update":
            if chat:
                chat.on_update(params.get("update") or {})
        elif method == "session/request_permission":
            if chat:
                chat.on_permission(rid, params)
            else:
                self.respond(rid, {"outcome": {"outcome": "cancelled"}})
        elif rid is not None:
            self.respond(rid, error={"code": -32601, "message": f"Method not found: {method}"})


AGENT = Agent()


# ---------------------------------------------------------------- conversațiile

SYSTEM = """You are Claude, working inside PDF Sign (Fintaxy), a Windows app for signing and editing PDFs.
The person is looking at a PDF in the editor and chats with you in a side panel.

- Open document: {path} ({pages} pages). Its folder is your working directory.
- Read the PDF with the Read tool (use the `pages` parameter for long files). Each message starts with a line in square
  brackets (never shown to the person) that says which page they are on; "this page", "here" mean that page.
- Answer in the person's language, briefly, from your very first answer. This team works in Romanian: when the message is
  short, mixed or unclear (a name, "ok"), answer in Romanian. This prompt and tool results are in English, but that is
  never the person's language. Markdown is rendered (lists, tables, bold, links).
- The person is not a programmer: plain words, no internal ids, no code unless they ask for it.
- Before you create or change a file or run a command, say in one line what you are about to do and why. The person
  approves each such action in the chat. Prefer reading over changing.
- Never change the original PDF. When asked to produce or change a file, write the result next to the original with a
  clear suffix in the name, and say where it is. Never delete files, send messages or publish anything unless the person
  asked for exactly that in this chat.
- The app itself can sign (handwritten image or certificate), fill forms, edit text, OCR, redact, merge, split, compress,
  convert: when that is what the person needs, tell them which button or tool to use (Ctrl+K searches every tool) instead
  of scripting it yourself.
- Messages that start with "Comentariu în PDF" / "PDF comment" are notes the person pinned on a page: the page number,
  the nearby text and sometimes a screenshot path come with them.
- You cannot enter a PIN or sign with a certificate yourself: that always happens in the Windows PIN window.
- End every answer with up to three short questions the person might ask next, in their language, one per line inside
  <followups></followups> on its own lines at the very end (the app shows them as buttons; never mention this block)."""

TERMINAL = {"Bash", "PowerShell", "BashOutput", "KillShell"}
# Titlurile uneltelor lui Claude Code, pe înțelesul omului (ca în Ask AI din CRM): (română, engleză)
BUILTIN = {
    "Bash": ("Rulează o comandă: {a}", "Run a command: {a}"), "PowerShell": ("Rulează o comandă: {a}", "Run a command: {a}"),
    "Read": ("Citește {a}", "Read {a}"), "Write": ("Creează sau înlocuiește {a}", "Create or replace {a}"),
    "Edit": ("Modifică {a}", "Edit {a}"), "MultiEdit": ("Modifică {a}", "Edit {a}"),
    "Glob": ("Caută fișiere: {a}", "Find files: {a}"), "Grep": ("Caută în fișiere: {a}", "Search in files: {a}"),
    "WebSearch": ("Caută pe web: {a}", "Search the web: {a}"), "WebFetch": ("Deschide {a}", "Open {a}"),
    "TodoWrite": ("Își face planul", "Makes its plan"),
}
PERMISSION_TIMEOUT = 180  # secunde: o cerere de acord fără răspuns e refuzată


def _english() -> bool:
    try:
        import desktop
        return desktop.english()
    except Exception:
        return False


def _clip(text: str, n: int = 110) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _humanize(name: str) -> str:
    t = re.sub(r"[_-]+", " ", str(name)).strip()
    return t[:1].upper() + t[1:]


def _args_summary(raw: dict) -> str:
    parts = []
    for k, v in (raw or {}).items():
        if v is None or v == "":
            continue
        if isinstance(v, dict):
            parts += [f"{k2}={v2}" for k2, v2 in v.items() if v2 is not None and not isinstance(v2, (dict, list))]
        elif isinstance(v, list):
            if all(not isinstance(x, (dict, list)) for x in v):
                parts.append(f"{k}={','.join(map(str, v))}")
        else:
            parts.append(str(v) if k in ("query", "q", "text", "url") else f"{k}={v}")
    return _clip(" ".join(parts), 90)


def tool_name(u: dict) -> str:
    return ((u.get("_meta") or {}).get("claudeCode") or {}).get("toolName") or ""


def describe_tool(name: str, title: str, raw) -> str:
    """Un rând scurt pentru un apel de unealtă: „Citește contract.pdf”, „Rulează o comandă: …”."""
    raw = raw if isinstance(raw, dict) else {}
    if name.startswith("mcp__"):
        parts = name.split("__")
        label = f"{_humanize('__'.join(parts[2:]))} ({parts[1]})"
        args = _args_summary(raw)
        return f"{label}: {args}" if args else label
    if name in BUILTIN:
        tpl = BUILTIN[name][1 if _english() else 0]
        if "{a}" not in tpl:
            return tpl
        if name in TERMINAL:
            arg = raw.get("description") or (str(raw.get("command") or "").strip().splitlines() or [""])[0]
        elif name in ("Read", "Write", "Edit", "MultiEdit"):
            arg = Path(str(raw.get("file_path") or raw.get("path") or "")).name
        elif name in ("Glob", "Grep"):
            arg = raw.get("pattern") or ""
        else:
            arg = raw.get("query") or raw.get("url") or ""
        if arg:
            return tpl.format(a=_clip(arg))
    first = (str(title or "").strip().splitlines() or [""])[0]
    return _clip(first or _humanize(name) or "Unealtă", 140)


def permission_detail(name: str, raw) -> str:
    """Ce aprobă omul, pe larg: comanda, fișierul și conținutul, sau modificarea (vechi / nou)."""
    raw = raw if isinstance(raw, dict) else {}
    if name in TERMINAL:
        return str(raw.get("command") or "")[:2000]
    f = str(raw.get("file_path") or raw.get("path") or "")
    if name == "Write":
        return f"{f}\n\n{str(raw.get('content') or '')[:1200]}"
    if name in ("Edit", "MultiEdit"):
        return f"{f}\n− {str(raw.get('old_string') or '')[:500]}\n+ {str(raw.get('new_string') or '')[:500]}"
    if not raw:
        return ""
    try:
        return json.dumps(raw, ensure_ascii=False, indent=2)[:600]
    except (TypeError, ValueError):
        return str(raw)[:600]


FOLLOWUPS = re.compile(r"<followups>.*", re.S)
KEEP = ("user", "text", "tool", "plan", "error", "done")  # ce rămâne în istoricul salvat


class Chat:
    def __init__(self, path: str):
        self.path = str(Path(path))
        self.session_id = None
        self.events = []          # tot ce s-a întâmplat, numerotat: editorul cere „ce e nou după N”
        self.cond = threading.Condition()
        self.running = False
        self.cancelled = False
        self.perms = {}           # id din chat -> {"rid", "options", "event", "tool"}
        self.tools = {}           # toolCallId -> {"ev", "name", "raw", "title"}
        self.plan_ev = None
        self.always = set()       # „Mereu în acest chat”, pe unealtă
        self.mcp_sig = None
        self.modes = []
        self.mode_id = "default"
        self.needs_context = False  # sesiune nouă peste un istoric vechi: îi spunem lui Claude ce s-a vorbit
        import hashlib
        self.file = STATE / "chats" / (hashlib.sha1(self.path.lower().encode("utf-8")).hexdigest()[:20] + ".json")
        self._load()

    # ---- istoricul, păstrat între porniri
    def _load(self):
        try:
            saved = json.loads(self.file.read_text(encoding="utf-8"))
            for e in saved.get("events") or []:
                if e.get("type") in KEEP:
                    e = {**e, "seq": len(self.events) + 1, "closed": True}
                    e.pop("rev", None)
                    if e["type"] == "tool" and e.get("status") not in ("completed", "failed"):
                        e["status"] = "stopped"
                    self.events.append(e)
            self.needs_context = bool(self.events)
        except (OSError, ValueError):
            pass

    def _save(self):
        try:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            keep = [{k: v for k, v in e.items() if k not in ("rev", "closed")} for e in self.events if e["type"] in KEEP][-400:]
            self.file.write_text(json.dumps({"path": self.path, "events": keep}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _history_text(self) -> str:
        """Ultimele schimburi, ca text, pentru o sesiune nouă (după repornire sau schimbarea conexiunilor)."""
        turns, q, a = [], None, ""
        for e in self.events[:-1]:  # fără mesajul tocmai trimis
            if e["type"] == "user":
                if q is not None:
                    turns.append((q, a))
                q, a = e.get("text", ""), ""
            elif e["type"] == "text":
                a += e.get("text", "")
        if q is not None:
            turns.append((q, a))
        if not turns:
            return ""
        lines = ["Earlier in this conversation (for context):"]
        for q, a in turns[-12:]:
            lines.append(f"Person: {_clip(q, 800)}")
            lines.append(f"You: {_clip(FOLLOWUPS.sub('', a), 1500)}")
        return "\n".join(lines) + "\n\n"

    # ---- evenimente către editor
    def emit(self, _type: str, **data) -> dict:
        with self.cond:
            ev = {"seq": len(self.events) + 1, "type": _type, **data}
            # bucățile de text consecutive se lipesc într-un singur eveniment (mai puține de trimis și de desenat)
            last = self.events[-1] if self.events else None
            if _type in ("text", "thought") and last and last["type"] == _type and not last.get("closed"):
                last["text"] += data.get("text", "")
                last["rev"] = last.get("rev", 0) + 1
                ev = last
            else:
                self.events.append(ev)
            self.cond.notify_all()
            return ev

    def close_text(self):
        with self.cond:
            for ev in reversed(self.events):
                if ev["type"] in ("text", "thought"):
                    ev["closed"] = True
                    break

    def since(self, seq: int, revs: dict, wait: float = 25.0, running=None) -> dict:
        """Evenimentele noi (și cele care s-au schimbat între timp); așteaptă până apare ceva.
        running = ce crede editorul că se întâmplă: dacă tura s-a terminat (sau a început) între timp, răspundem
        imediat, altfel butonul ar rămâne pe „Oprește” până la următorul eveniment."""
        end = time.time() + wait
        with self.cond:
            while True:
                out = [e for e in self.events if e["seq"] > seq or e.get("rev", 0) > int(revs.get(str(e["seq"]), 0))]
                if out or time.time() >= end or (running is not None and running != self.running):
                    return {"ok": True, "events": out, "running": self.running, "last": len(self.events)}
                self.cond.wait(max(0.05, min(1.0, end - time.time())))

    def touch(self, ev: dict, **changes):
        with self.cond:
            ev.update(changes)
            ev["rev"] = ev.get("rev", 0) + 1
            self.cond.notify_all()

    # ---- de la adaptor
    def _tool(self, u: dict) -> dict:
        tid = u.get("toolCallId")
        t = self.tools.get(tid)
        name, raw = tool_name(u), u.get("rawInput")
        if not t:
            self.close_text()
            t = {"name": name, "raw": raw, "title": u.get("title") or ""}
            t["ev"] = self.emit("tool", id=tid, title=describe_tool(name, t["title"], raw), status=u.get("status") or "pending",
                                kind=u.get("kind") or "other")
            self.tools[tid] = t
            return t
        changes = {}
        if name:
            t["name"] = name
        if raw:
            t["raw"] = raw
        if u.get("title"):
            t["title"] = u["title"]
        title = describe_tool(t["name"], t["title"], t["raw"])
        if title != t["ev"].get("title"):
            changes["title"] = title
        if u.get("status") and u["status"] != t["ev"].get("status"):
            changes["status"] = u["status"]
        if changes:
            self.touch(t["ev"], **changes)
        return t

    def on_update(self, u: dict):
        if not self.running:
            return  # istoric redat sau un rest după oprire
        kind = u.get("sessionUpdate")
        content = u.get("content") or {}
        if kind == "agent_message_chunk":
            if content.get("type") == "text" and content.get("text"):
                self.emit("text", text=content["text"])
        elif kind == "agent_thought_chunk":
            if content.get("type") == "text" and content.get("text"):
                self.emit("thought", text=content["text"])
        elif kind in ("tool_call", "tool_call_update"):
            self._tool(u)
        elif kind == "plan":
            entries = [{"content": e.get("content", ""), "status": e.get("status", "pending")} for e in u.get("entries") or []]
            if self.plan_ev is None:
                self.close_text()
                self.plan_ev = self.emit("plan", entries=entries)
            else:
                self.touch(self.plan_ev, entries=entries)

    def on_permission(self, rid, params: dict):
        options = params.get("options") or []
        tc = params.get("toolCall") or {}
        t = self._tool(tc) if tc.get("toolCallId") else {"name": tool_name(tc), "raw": tc.get("rawInput"), "title": tc.get("title") or ""}
        name = t["name"] or t["title"] or "tool"
        allow = next((o for o in options if o.get("kind") == "allow_once"), None) or next(
            (o for o in options if o.get("kind") == "allow_always"), None)
        if not self.running or self.cancelled:
            return AGENT.respond(rid, {"outcome": {"outcome": "cancelled"}})
        if name in self.always and allow:
            return AGENT.respond(rid, {"outcome": {"outcome": "selected", "optionId": allow["optionId"]}})
        self.close_text()
        ev = self.emit("perm", id=f"p{len(self.events) + 1}", title=describe_tool(t["name"], t["title"], t["raw"]),
                       detail=permission_detail(t["name"], t["raw"]), state="ask", noAlways=name in TERMINAL)
        self.perms[ev["id"]] = {"rid": rid, "options": options, "event": ev, "tool": name}
        timer = threading.Timer(PERMISSION_TIMEOUT, lambda: self.answer(ev["id"], "timeout"))
        timer.daemon = True
        timer.start()

    def answer(self, pid: str, choice: str) -> bool:
        p = self.perms.pop(pid, None)
        if not p:
            return False
        opts = p["options"]

        def pick(*kinds):
            return next((o for k in kinds for o in opts if o.get("kind") == k), None)
        if choice in ("allow", "always"):
            o = pick("allow_once", "allow_always")
            if choice == "always":
                self.always.add(p["tool"])
        else:
            o = pick("reject_once", "reject_always")
        AGENT.respond(p["rid"], {"outcome": {"outcome": "selected", "optionId": o["optionId"]}} if o
                      else {"outcome": {"outcome": "cancelled"}})
        self.touch(p["event"], state={"allow": "allowed", "always": "allowed", "timeout": "timeout"}.get(choice, "denied"))
        return True

    def agent_gone(self, why: str):
        self.session_id = None
        if self.running:
            self.emit("error", text=why)
            self._finish()

    def _finish(self):
        for pid in list(self.perms):
            p = self.perms.pop(pid)
            self.touch(p["event"], state="cancelled")
        self.close_text()
        self.tools.clear()
        self.plan_ev = None
        self._save()
        with self.cond:
            self.running = False
            self.cond.notify_all()

    # ---- către adaptor
    def ensure_session(self, mcp: list, user_settings: bool) -> bool:
        """Sesiunea ACP a documentului; True dacă a fost creată acum (atunci Claude nu știe ce s-a vorbit înainte)."""
        AGENT.start()
        sig = json.dumps([mcp, user_settings], sort_keys=True)
        if self.session_id and self.session_id in AGENT.sessions and sig == self.mcp_sig:
            return False
        pages = 0
        try:
            import fitz
            with fitz.open(self.path) as d:
                pages = len(d)
        except Exception:
            pass
        options = {"promptSuggestions": False, "allowDangerouslySkipPermissions": False}
        if not user_settings:
            # Izolat, ca în CRM: fără setările, plugin-urile și serverele MCP ale omului din Claude Code;
            # doar conexiunile puse în PDF Sign (de ex. CRM-ul).
            options.update(settingSources=[], strictMcpConfig=True)
        meta = {"systemPrompt": {"append": SYSTEM.format(path=self.path, pages=pages or "?")}, "claudeCode": {"options": options}}
        servers = [{"type": "http", "name": m["name"], "url": m["url"],
                    "headers": ([{"name": "Authorization", "value": f"Bearer {m['token']}"}] if m.get("token") else [])}
                   for m in mcp if m.get("name") and m.get("url")]
        res = AGENT.request("session/new", {"cwd": str(Path(self.path).parent), "mcpServers": servers, "_meta": meta}, timeout=120)
        self.session_id = res["sessionId"]
        self.mcp_sig = sig
        AGENT.sessions[self.session_id] = self
        modes = res.get("modes") or {}
        self.modes = [m.get("id") for m in modes.get("availableModes") or []]
        self.mode_id = modes.get("currentModeId") or "default"
        return True

    def apply_mode(self, mode: str):
        """Manual = fiecare schimbare cere acord (modul „default” al lui Claude Code). Auto = Claude decide singur la
        acțiunile de rutină și întreabă doar la cele riscante („auto”; pe adaptoare mai vechi, „acceptEdits”)."""
        want = "default"
        if mode == "auto":
            want = next((m for m in ("auto", "acceptEdits") if m in self.modes), "default")
        if want != self.mode_id and want in (self.modes or ["default"]):
            try:
                AGENT.request("session/set_mode", {"sessionId": self.session_id, "modeId": want}, timeout=30)
                self.mode_id = want
            except AcpError:
                pass

    def send(self, text: str, page: int, mcp: list, user_settings: bool, images: list | None = None, mode: str = "ask"):
        with self.cond:
            if self.running:
                raise AcpError("Claude încă răspunde la mesajul dinainte. Așteaptă sau apasă Oprește.")
            self.running, self.cancelled = True, False
        self.emit("user", text=text, page=page)
        threading.Thread(target=self._turn, args=(text, page, mcp, user_settings, images or [], mode), daemon=True).start()

    def _turn(self, text, page, mcp, user_settings, images, mode):
        try:
            before = self._mtime()
            fresh = self.ensure_session(mcp, user_settings)
            self.apply_mode(mode)
            context = self._history_text() if (fresh and self.needs_context) or (fresh and len(self.events) > 1) else ""
            self.needs_context = False
            body = f"{context}[PDF: {self.path} · pagina curentă: {page}]\n\n{text}"
            for img in images:  # capturile de zonă: Claude le citește de pe disc
                body += f"\nCaptură: {img}"
            res = AGENT.request("session/prompt", {"sessionId": self.session_id, "prompt": [{"type": "text", "text": body}]}, timeout=None)
            self.close_text()
            self.emit("done", stop=res.get("stopReason") or "end_turn", docChanged=self._mtime() != before)
        except Exception as err:
            if not self.cancelled:
                msg = str(err)
                said = " ".join(e.get("text", "") for e in self.events[-3:] if e["type"] == "text")
                if re.search(r"(?i)authenticat|oauth|/login|not logged in|credential", msg + " " + said):
                    # Claude Code nu e conectat (sau conectarea a expirat): editorul arată butonul „Conectează Claude”.
                    self.session_id = None
                    self.emit("error", needLogin=True,
                              text="Claude nu e conectat pe acest calculator (sau conectarea a expirat). Apasă „Conectează Claude”, "
                                   "scrie /login în fereastra care se deschide, apoi trimite din nou mesajul.")
                else:
                    if AGENT.last_error and "s-a oprit" in msg:
                        msg += f" ({AGENT.last_error})"
                    self.emit("error", text=msg)
            else:
                self.emit("done", stop="cancelled", docChanged=False)
        finally:
            self._finish()

    def _mtime(self):
        try:
            return os.path.getmtime(self.path)
        except OSError:
            return 0

    def cancel(self):
        if not self.running:
            return
        self.cancelled = True
        for pid in list(self.perms):
            p = self.perms.pop(pid)
            AGENT.respond(p["rid"], {"outcome": {"outcome": "cancelled"}})
            self.touch(p["event"], state="cancelled")
        if self.session_id:
            try:
                AGENT.notify("session/cancel", {"sessionId": self.session_id})
            except AcpError:
                pass

        def force():
            # Dacă agentul nu se oprește singur în câteva secunde, îl oprim noi: editorul nu rămâne niciodată blocat.
            time.sleep(8)
            if self.running and self.cancelled:
                AGENT.stop()
        threading.Thread(target=force, daemon=True).start()

    def reset(self):
        self.cancel()
        sid, self.session_id = self.session_id, None
        AGENT.sessions.pop(sid, None)
        with self.cond:
            self.events.clear()
            self.tools.clear()
            self.always.clear()
            self.plan_ev = None
            self.needs_context = False
            self.cond.notify_all()
        try:
            self.file.unlink(missing_ok=True)
        except OSError:
            pass


CHATS: dict = {}
_CHATS_LOCK = threading.Lock()


def chat_for(path: str) -> Chat:
    key = str(Path(path)).lower()
    with _CHATS_LOCK:
        if key not in CHATS:
            CHATS[key] = Chat(path)
        return CHATS[key]


def shutdown():
    AGENT.stop()
