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


def app_version() -> str:
    """Versiunea aplicației (eticheta clientului ACP)."""
    try:
        import desktop
        return desktop.app_version() or "0"
    except Exception:
        return "0"


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
    env.update(CLAUDE_AGENT_SDK_CLIENT_APP=f"fintaxy-pdf-sign/{app_version()}", CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION="false",
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
        self.configs = {}      # model -> configOptions (modelul și efortul pe care le oferă Claude Code)
        self.rate = {}         # tip limită -> ultimul eveniment de limită primit în timpul unei ture
        self.usage_cache = None

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
                    "clientInfo": {"name": "fintaxy-pdf-sign", "title": "PDF Sign (Fintaxy)", "version": app_version()},
                }, timeout=60)
            except Exception as err:
                self.stop()
                raise AcpError(f"Claude Code nu a pornit: {err}") from None
            self.caps = init.get("agentCapabilities") or {}
            threading.Thread(target=self._sweep, args=(self.proc,), daemon=True).start()

    def session_caps(self) -> dict:
        return self.caps.get("sessionCapabilities") or {}

    def close_session(self, sid: str):
        """Închide o sesiune la adaptor (Claude Code își eliberează memoria); transcrierea rămâne pe disc pentru reluare."""
        if not sid:
            return
        self.sessions.pop(sid, None)
        if "close" in self.session_caps() and self.alive():
            try:
                self.request("session/close", {"sessionId": sid}, timeout=10)
            except AcpError:
                pass

    def live_chats(self) -> list:
        return [c for c in set(self.sessions.values()) if isinstance(c, Chat)]

    def make_room(self, keep):
        """Cel mult LIVE_MAX sesiuni deschise deodată: o închidem pe cea folosită cel mai demult (se reia la nevoie)."""
        live = [c for c in self.live_chats() if c is not keep and not c.running]
        while len(live) + 1 > LIVE_MAX and live:
            old = min(live, key=lambda c: c.last_used)
            live.remove(old)
            self.close_session(old.session_id)

    def _sweep(self, p):
        """Sesiunile nefolosite de IDLE_SECONDS se închid (ca în CRM); conversația se reia cu session/resume."""
        while self.proc is p and p.poll() is None:
            time.sleep(60)
            for c in self.live_chats():
                if not c.running and time.time() - c.last_used > IDLE_SECONDS:
                    self.close_session(c.session_id)

    def note_rate(self, info):
        if isinstance(info, dict) and info.get("rateLimitType"):
            self.rate[info["rateLimitType"]] = info

    def note_config(self, options, fresh=False):
        if not isinstance(options, list) or not options:
            return
        model = (select_of(options, "model") or {}).get("currentValue")
        if fresh and "" not in self.configs:
            self.configs[""] = options
        if model:
            self.configs[str(model)] = options

    def complete(self, prompt: str, system: str = "", model: str = "", timeout: float = 180) -> str:
        """O întrebare de-o tură pe o sesiune temporară, fără unelte și fără conexiuni (titluri, /usage)."""
        self.start()
        options = {"settingSources": [], "strictMcpConfig": True, "promptSuggestions": False, "tools": [],
                   "allowDangerouslySkipPermissions": False}
        if model:
            options["model"] = model
        meta = {"systemPrompt": system if system else {"append": ""}, "claudeCode": {"options": options}}
        res = self.request("session/new", {"cwd": str(STATE), "mcpServers": [], "_meta": meta}, timeout=120)
        sid = res["sessionId"]
        if not model:
            self.note_config(res.get("configOptions"), fresh=True)
        temp = _Temp()
        self.sessions[sid] = temp
        try:
            self.request("session/prompt", {"sessionId": sid, "prompt": [{"type": "text", "text": prompt}]}, timeout=timeout)
            return temp.text.strip()
        except AcpError:
            try:
                self.notify("session/cancel", {"sessionId": sid})
            except AcpError:
                pass
            raise
        finally:
            self.close_session(sid)

    def config_for(self, model: str = "") -> list:
        """Opțiunile (model, efort) pentru un model ('' = cele ale unei sesiuni noi), dintr-o sesiune scurtă dacă nu le știm."""
        if model in self.configs:
            return self.configs[model]
        self.start()
        meta = {"systemPrompt": {"append": ""}, "claudeCode": {"options": {"settingSources": [], "strictMcpConfig": True, "tools": []}}}
        res = self.request("session/new", {"cwd": str(STATE), "mcpServers": [], "_meta": meta}, timeout=120)
        try:
            self.note_config(res.get("configOptions"), fresh=True)
            opts = res.get("configOptions") or []
            cur = select_of(opts, "model")
            if model and cur and cur.get("currentValue") != model and any(o["value"] == model for o in flat_options(cur)):
                r = self.request("session/set_config_option", {"sessionId": res["sessionId"], "configId": "model", "value": model}, timeout=30)
                if isinstance(r.get("configOptions"), list):
                    opts = r["configOptions"]
                    self.note_config(opts)
            self.configs.setdefault(model, opts)
            return opts
        finally:
            self.close_session(res["sessionId"])

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
CHAT_DIR = STATE / "chats"
FILES_DIR = STATE / "chat-files"
LIVE_MAX = 4               # sesiuni ACP deschise deodată (ca în CRM)
IDLE_SECONDS = 15 * 60     # o sesiune nefolosită atâta timp se închide (se reia când omul scrie iar)
FORCE_STOP = 3             # secunde după Oprește: dacă agentul nu încheie tura, o încheiem noi
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
MAX_FILE = 20 * 1024 * 1024
STOP_TEXT = {  # (română, engleză)
    "refusal": ("Claude a refuzat această cerere.", "Claude declined this request."),
    "max_tokens": ("Răspunsul a fost prea lung și s-a oprit. Cere-i să continue.", "The answer was too long and stopped. Ask it to continue."),
    "max_turn_requests": ("Claude a făcut prea mulți pași la rând. Cere-i să continue.", "Claude took too many steps in a row. Ask it to continue."),
}


def select_of(options, cid: str):
    return next((o for o in options or [] if isinstance(o, dict) and o.get("id") == cid and o.get("type") == "select"), None)


def flat_options(opt) -> list:
    out = []
    for o in (opt or {}).get("options") or []:
        out += o["options"] if isinstance(o, dict) and isinstance(o.get("options"), list) else [o]
    return [{"value": o["value"], "name": str(o.get("name") or o["value"]), **({"description": str(o["description"])} if o.get("description") else {})}
            for o in out if isinstance(o, dict) and isinstance(o.get("value"), str)]


class _Temp:
    """Sesiunea unei întrebări de-o tură (complete()): contează doar textul."""

    def __init__(self):
        self.text = ""

    def on_update(self, u: dict):
        if u.get("sessionUpdate") == "agent_message_chunk" and (u.get("content") or {}).get("type") == "text":
            self.text += u["content"].get("text", "")
        elif u.get("sessionUpdate") == "usage_update":
            AGENT.note_rate((u.get("_meta") or {}).get("_claude/rateLimit"))

    def on_permission(self, rid, params):
        AGENT.respond(rid, {"outcome": {"outcome": "cancelled"}})

    def agent_gone(self, why):
        pass


def _now() -> int:
    return int(time.time() * 1000)


def _first_title(text: str) -> str:
    return _clip(re.sub(r"\s+", " ", text).strip(), 80)


class Chat:
    def __init__(self, cid: str, path: str):
        self.id = cid
        self.path = str(Path(path))
        self.title, self.title_source, self.starred = "", "", False
        self.created = self.updated = _now()
        self.session_id = None
        self.session_sig = None
        self.no_resume = False
        self.replaying = False
        self.events = []          # tot ce s-a întâmplat, numerotat: editorul cere „ce e nou după N”
        self.cond = threading.Condition()
        self.running = False
        self.cancelled = False
        self.turn_id = 0
        self.perms = {}           # id din chat -> {"rid", "options", "event", "tool"}
        self.tools = {}           # toolCallId -> {"ev", "name", "raw", "title"}
        self.written = set()      # fișierele scrise de Claude în tura asta
        self.plan_ev = None
        self.always = set()       # „Mereu în acest chat”, pe unealtă (păstrat în fișier)
        self.modes = []
        self.mode_id = "default"
        self.config = []          # ce oferă sesiunea: model, efort
        self.last_used = time.time()
        self.file = CHAT_DIR / f"{cid}.json"

    # ---- istoricul, păstrat între porniri
    def _load(self, saved: dict):
        self.title = str(saved.get("title") or "")
        self.title_source = str(saved.get("titleSource") or "")
        self.starred = bool(saved.get("starred"))
        self.created = int(saved.get("created") or 0) or _now()
        self.session_id = saved.get("sessionId") or None
        self.session_sig = saved.get("sessionSig")
        self.always = set(saved.get("always") or [])
        for e in saved.get("events") or []:
            if e.get("type") in KEEP:
                e = {**e, "seq": len(self.events) + 1, "closed": True}
                e.pop("rev", None)
                if e["type"] == "tool" and e.get("status") not in ("completed", "failed"):
                    e["status"] = "stopped"
                self.events.append(e)
        try:
            mtime = int(self.file.stat().st_mtime * 1000)
        except OSError:
            mtime = self.created
        self.updated = int(saved.get("updated") or 0) or mtime
        if not self.title:
            first = next((e.get("text", "") for e in self.events if e["type"] == "user"), "")
            self.title, self.title_source = _first_title(first), "first"

    def _save(self):
        if not any(e["type"] == "user" for e in self.events):
            return
        try:
            CHAT_DIR.mkdir(parents=True, exist_ok=True)
            keep = [{k: v for k, v in e.items() if k not in ("rev", "closed")} for e in self.events if e["type"] in KEEP][-400:]
            data = {"id": self.id, "path": self.path, "title": self.title, "titleSource": self.title_source, "starred": self.starred,
                    "created": self.created, "updated": self.updated, "sessionId": self.session_id, "sessionSig": self.session_sig,
                    "always": sorted(self.always), "events": keep}
            tmp = self.file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.file)
        except OSError:
            pass

    def meta(self) -> dict:
        return {"id": self.id, "title": self.title or ("New chat" if _english() else "Conversație nouă"), "starred": self.starred,
                "updated": self.updated, "created": self.created, "running": self.running,
                "questions": sum(1 for e in self.events if e["type"] == "user")}

    def _history_text(self) -> str:
        """Ultimele schimburi, ca text, pentru o sesiune nouă (când Claude Code nu o mai poate relua)."""
        turns, q, a = [], None, ""
        for e in self.events[:-1]:  # fără mesajul tocmai trimis
            if e["type"] == "user":
                if q is not None:
                    turns.append((q, a))
                q, a = e.get("text", ""), ""
            elif e["type"] == "text":
                a += e.get("text", "")
            elif e["type"] == "error":
                a += " (failed)"
        if q is not None:
            turns.append((q, a))
        if not turns:
            return ""
        lines = ["Earlier in this conversation (for context):"]
        for q, a in turns[-12:]:
            lines.append(f"Person: {_clip(q, 4000)}")
            lines.append(f"You: {_clip(FOLLOWUPS.sub('', a), 6000)}")
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

    def since(self, seq: int, revs: dict, wait: float = 25.0, running=None, title=None) -> dict:
        """Evenimentele noi (și cele care s-au schimbat între timp); așteaptă până apare ceva.
        running / title = ce crede editorul: dacă tura s-a terminat (sau a început) ori titlul s-a schimbat între timp,
        răspundem imediat, altfel butonul ar rămâne pe „Oprește” până la următorul eveniment."""
        end = time.time() + wait
        with self.cond:
            while True:
                out = [e for e in self.events if e["seq"] > seq or e.get("rev", 0) > int(revs.get(str(e["seq"]), 0))]
                if (out or time.time() >= end or (running is not None and running != self.running)
                        or (title is not None and title != self.title)):
                    return {"ok": True, "events": out, "running": self.running, "last": len(self.events), "chat": self.id,
                            "title": self.title}
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
        else:
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
        if t["ev"].get("status") == "completed" and t["name"] in ("Write", "Edit", "MultiEdit") and isinstance(t["raw"], dict):
            f = t["raw"].get("file_path") or t["raw"].get("path")
            if f:
                self.written.add(str(Path(f)))
        return t

    def on_update(self, u: dict):
        kind = u.get("sessionUpdate")
        if kind == "config_option_update":
            if isinstance(u.get("configOptions"), list):
                self.config = u["configOptions"]
                AGENT.note_config(self.config)
            return
        if kind == "usage_update":
            AGENT.note_rate((u.get("_meta") or {}).get("_claude/rateLimit"))
            return
        if kind == "current_mode_update":
            self.mode_id = u.get("currentModeId") or self.mode_id
            return
        if not self.running or self.replaying:
            return  # istoric redat sau un rest după oprire
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
        if not self.running or self.cancelled or self.replaying:
            return AGENT.respond(rid, {"outcome": {"outcome": "cancelled"}})
        t = self._tool(tc) if tc.get("toolCallId") else {"name": tool_name(tc), "raw": tc.get("rawInput"), "title": tc.get("title") or ""}
        name = t["name"] or t["title"] or "tool"
        allow = next((o for o in options if o.get("kind") == "allow_once"), None) or next(
            (o for o in options if o.get("kind") == "allow_always"), None)
        if name in self.always and allow and name not in TERMINAL:
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
            if choice == "always" and p["tool"] not in TERMINAL:
                self.always.add(p["tool"])
        else:
            o = pick("reject_once", "reject_always")
        AGENT.respond(p["rid"], {"outcome": {"outcome": "selected", "optionId": o["optionId"]}} if o
                      else {"outcome": {"outcome": "cancelled"}})
        self.touch(p["event"], state={"allow": "allowed", "always": "allowed", "timeout": "timeout"}.get(choice, "denied"))
        return True

    def agent_gone(self, why: str):
        # sesiunea rămâne în fișier: la următorul mesaj se reia (session/resume), dacă Claude Code o mai are
        if self.running:
            self.turn_id += 1
            self.emit("error", text=why)
            self._finish()

    def _finish(self):
        for pid in list(self.perms):
            p = self.perms.pop(pid)
            self.touch(p["event"], state="cancelled")
        self.close_text()
        self.tools.clear()
        self.plan_ev = None
        self.last_used = time.time()
        self._save()
        with self.cond:
            self.running = False
            self.cond.notify_all()

    # ---- către adaptor
    def ensure_session(self, mcp: list, user_settings: bool) -> bool:
        """Sesiunea ACP a conversației; True dacă e nouă (atunci Claude nu știe ce s-a vorbit înainte)."""
        AGENT.start()
        self.last_used = time.time()
        sig = json.dumps([mcp, user_settings], sort_keys=True)
        if self.session_id and AGENT.sessions.get(self.session_id) is self:
            if sig == self.session_sig:
                return False
            AGENT.close_session(self.session_id)  # conexiunile s-au schimbat: sesiune nouă, cu istoricul ca text
        AGENT.make_room(self)
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
        params = {"cwd": str(Path(self.path).parent), "mcpServers": servers, "_meta": meta}
        sc = AGENT.session_caps()
        if self.session_id and sig == self.session_sig and not self.no_resume and ("resume" in sc or AGENT.caps.get("loadSession")):
            # aceeași conversație în Claude Code, fără s-o mai trimitem ca text (resume nu o redă; load o redă și o ignorăm)
            self.replaying = True
            try:
                method = "session/resume" if "resume" in sc else "session/load"
                AGENT.sessions[self.session_id] = self
                res = AGENT.request(method, {"sessionId": self.session_id, **params}, timeout=120)
                self._note(res)
                return False
            except AcpError:
                AGENT.sessions.pop(self.session_id, None)
            finally:
                self.replaying = False
        self.no_resume = False
        res = AGENT.request("session/new", params, timeout=120)
        self.session_id = res["sessionId"]
        self.session_sig = sig
        AGENT.sessions[self.session_id] = self
        self._note(res, fresh=True)
        return True

    def _note(self, res: dict, fresh=False):
        if isinstance(res.get("configOptions"), list):
            self.config = res["configOptions"]
            AGENT.note_config(self.config, fresh=fresh)
        modes = res.get("modes") or {}
        if modes.get("availableModes"):
            self.modes = [m.get("id") for m in modes["availableModes"]]
        self.mode_id = modes.get("currentModeId") or self.mode_id

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

    def apply_prefs(self, prefs: dict):
        """Modelul și efortul alese în compozitor (ținute minte în setări), dacă Claude Code le oferă. Întâi modelul:
        nivelurile de efort depind de el."""
        for cid in ("model", "effort"):
            want = (prefs or {}).get(cid)
            opt = select_of(self.config, cid)
            if not want or not opt or opt.get("currentValue") == want or not any(o["value"] == want for o in flat_options(opt)):
                continue
            try:
                r = AGENT.request("session/set_config_option", {"sessionId": self.session_id, "configId": cid, "value": want}, timeout=30)
                if isinstance(r.get("configOptions"), list):
                    self.config = r["configOptions"]
                    AGENT.note_config(self.config)
                else:
                    self.config = [{**o, "currentValue": want} if o.get("id") == cid else o for o in self.config]
            except AcpError:
                pass

    def send(self, text: str, page: int, mcp: list, user_settings: bool, files: list | None = None, mode: str = "ask",
             prefs: dict | None = None):
        files = files or []
        if not text and files:
            text = "Look at the attached file." if _english() else "Uită-te la fișierul atașat."
        if not text:
            raise AcpError("Write a message." if _english() else "Scrie un mesaj.")
        with self.cond:
            if self.running:
                raise AcpError("Claude încă răspunde la mesajul dinainte. Așteaptă sau apasă Oprește.")
            self.running, self.cancelled = True, False
            self.turn_id += 1
            my = self.turn_id
        if not self.title:
            self.title, self.title_source = _first_title(text), "first"
        self.updated = _now()
        self.emit("user", text=text, page=page, files=[{"name": f["name"], "kind": f["kind"]} for f in files])
        threading.Thread(target=self._turn, args=(my, text, page, mcp, user_settings, files, mode, prefs or {}), daemon=True).start()

    def _blocks(self, body: str, files: list) -> list:
        blocks = [{"type": "text", "text": body}]
        can_image = (AGENT.caps.get("promptCapabilities") or {}).get("image")
        for f in files:
            mime = IMAGE_TYPES.get(Path(f["path"]).suffix.lower())
            if mime and can_image:
                try:
                    import base64
                    data = Path(f["path"]).read_bytes()
                    if len(data) <= 5 * 1024 * 1024:
                        blocks.append({"type": "image", "mimeType": mime, "data": base64.b64encode(data).decode("ascii")})
                except OSError:
                    pass
        return blocks

    def _turn(self, my, text, page, mcp, user_settings, files, mode, prefs):
        ok = False
        try:
            before = self._mtime()
            self.written = set()
            fresh = self.ensure_session(mcp, user_settings)
            self.apply_mode(mode)
            self.apply_prefs(prefs)
            context = self._history_text() if fresh and len(self.events) > 1 else ""
            body = f"{context}[PDF: {self.path} · current page: {page}]\n\n{text}"
            if files:
                body += "\n\nAttached files (on disk; read them if needed):\n" + "\n".join(f"- {f['path']}" for f in files)
            res = AGENT.request("session/prompt", {"sessionId": self.session_id, "prompt": self._blocks(body, files)}, timeout=None)
            if my != self.turn_id:
                return
            self.close_text()
            stop = res.get("stopReason") or "end_turn"
            if self.cancelled:
                stop = "cancelled"
            note = STOP_TEXT.get(stop)
            made = sorted(f for f in self.written if os.path.isfile(f) and not _same(f, self.path))
            self.emit("done", stop=stop, docChanged=self._mtime() != before, files=made,
                      note=(note[1] if _english() else note[0]) if note else "")
            ok = stop == "end_turn"
        except Exception as err:
            if my != self.turn_id:
                return
            if self.cancelled:
                self.emit("done", stop="cancelled", docChanged=False)
            else:
                msg = str(err)
                if re.search(r"(?i)authenticat|oauth|/login|not logged in|credential", msg):
                    # Claude Code nu e conectat (sau conectarea a expirat): editorul arată butonul „Conectează Claude”.
                    self.session_id = None
                    self.emit("error", needLogin=True,
                              text="Claude nu e conectat pe acest calculator (sau conectarea a expirat). Apasă „Conectează Claude”, "
                                   "scrie /login în fereastra care se deschide, apoi trimite din nou mesajul.")
                else:
                    if AGENT.last_error and "s-a oprit" in msg:
                        msg += f" ({AGENT.last_error})"
                    self.emit("error", text=msg)
        finally:
            if my == self.turn_id:
                self._finish()
                if ok and self.title_source in ("", "first") and sum(1 for e in self.events if e["type"] == "user") == 1:
                    threading.Thread(target=self._auto_title, daemon=True).start()

    def _auto_title(self):
        q = next((e.get("text", "") for e in self.events if e["type"] == "user"), "")
        a = FOLLOWUPS.sub("", " ".join(e.get("text", "") for e in self.events if e["type"] == "text"))
        title = make_title(q, a)
        if title and self.title_source != "user":
            self.title, self.title_source = title, "auto"
            self._save()
            with self.cond:
                self.cond.notify_all()

    def _mtime(self):
        try:
            return os.path.getmtime(self.path)
        except OSError:
            return 0

    def cancel(self):
        if not self.running:
            return
        self.cancelled = True
        my = self.turn_id
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
            # Agentul nu a încheiat tura: o încheiem noi (editorul nu rămâne blocat), fără să oprim celelalte
            # conversații; următorul mesaj merge pe o sesiune nouă, cu istoricul ca text.
            time.sleep(FORCE_STOP)
            if self.running and self.cancelled and self.turn_id == my:
                self.turn_id += 1
                sid = self.session_id
                self.session_id, self.no_resume = None, True
                AGENT.sessions.pop(sid, None)
                self.emit("done", stop="cancelled", docChanged=False)
                self._finish()
                threading.Thread(target=AGENT.close_session, args=(sid,), daemon=True).start()
        threading.Thread(target=force, daemon=True).start()

    def close(self):
        """Conversația iese din memorie (ștearsă): oprim tura și închidem sesiunea."""
        self.cancel()
        self.turn_id += 1
        if self.running:
            self._finish()
        if self.session_id:
            threading.Thread(target=AGENT.close_session, args=(self.session_id,), daemon=True).start()
        self.session_id = None


# ---------------------------------------------------------------- titlurile, ca în CRM

TITLE_SYSTEM = ("You name chat conversations. Reply with only a short title of 3 to 6 words for the conversation, in the "
                "language of the person's question (Romanian when unsure). No quotes, no final period, no emoji.")
FILLER = re.compile(r"(?i)\b(te rog|vă rog|va rog|please|poți|poti|can you|could you|aș vrea|as vrea|i want to|vreau să|vreau sa)\b[,:]?\s*")


def heuristic_title(q: str) -> str:
    t = re.sub(r"https?://\S+|\S+@\S+", "", q)
    t = FILLER.sub("", t)
    t = re.sub(r"\s+", " ", t).strip(" ?!.,:;")
    return _clip(t[:1].upper() + t[1:], 60) if t else ""


def make_title(q: str, a: str) -> str:
    """Un titlu de 3-6 cuvinte (Claude Code, modelul rapid); altfel primele cuvinte ale întrebării, curățate."""
    try:
        out = AGENT.complete(f"Question: {_clip(q, 1500)}\n\nAnswer: {_clip(a, 1500)}\n\nTitle:", system=TITLE_SYSTEM,
                             model="haiku", timeout=60)
        line = next((ln for ln in out.splitlines() if ln.strip()), "")
        line = re.sub(r"(?i)^title\s*:\s*", "", line).strip().strip('"„”“*#').rstrip(".")
        if 1 <= len(line.split()) <= 10:
            return _clip(line, 60)
    except Exception:
        pass
    return heuristic_title(q)


# ---------------------------------------------------------------- limitele abonamentului (inelul din chat)

LIMIT_ID = {"5-hour limit": "five_hour", "weekly · all models": "seven_day"}
EVENT_LABEL = {"five_hour": "5-hour limit", "seven_day": "Weekly · all models", "seven_day_opus": "Weekly · Opus",
               "seven_day_sonnet": "Weekly · Sonnet"}
MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def parse_reset(s: str, now: float | None = None):
    """„Nov 11, 3:59 PM GMT+2” (fără an, cum scrie /usage) → momentul în ms, următorul după acum."""
    import datetime as dt
    m = re.match(r"(?i)\s*([a-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{1,2})(?::(\d{2}))?\s*([ap]m)?\s*\(?(?:(?:GMT|UTC)([+-]\d{1,2})(?::?(\d{2}))?)?",
                 s or "")
    if not m or m.group(1).lower() not in MONTHS:
        return None
    hour = int(m.group(3))
    if m.group(5):
        hour = hour % 12 + (12 if m.group(5).lower() == "pm" else 0)
    if m.group(6):
        sign = -1 if m.group(6).startswith("-") else 1
        tz = dt.timezone(dt.timedelta(hours=int(m.group(6)), minutes=sign * int(m.group(7) or 0)))
    else:
        tz = dt.datetime.now().astimezone().tzinfo
    now_dt = dt.datetime.fromtimestamp(now if now is not None else time.time(), tz)
    for y in (now_dt.year, now_dt.year + 1):
        try:
            d = dt.datetime(y, MONTHS[m.group(1).lower()], int(m.group(2)), hour, int(m.group(4) or 0), tzinfo=tz)
        except ValueError:
            continue
        if d.timestamp() > now_dt.timestamp() - 24 * 3600:
            return int(d.timestamp() * 1000)
    return None


def parse_usage(md: str) -> tuple:
    text = str(md or "")
    pm = re.search(r"Claude (.+?) subscription usage", text)
    plan = re.sub(r"\\(.)", r"\1", pm.group(1)) if pm else None
    limits = []
    for m in re.finditer(r"\*\*([^*\n]+?)\*\*\s*\S\s*\*\*(\d+(?:\.\d+)?)%\*\*(?:\s*·\s*Resets\s+([^\n]+))?", text):
        label = re.sub(r"\\(.)", r"\1", m.group(1)).strip()
        key = label.lower()
        lid = LIMIT_ID.get(key) or "seven_day:" + re.sub(r"^weekly\s*·\s*", "", key)
        rt = (m.group(3) or "").strip() or None
        limits.append({"id": lid, "label": label, "percent": max(0.0, min(100.0, float(m.group(2)))),
                       "resetsAt": parse_reset(rt) if rt else None, "resetsText": rt})
    return plan, limits


def limits_from_events() -> list:
    out = []
    for kind, info in AGENT.rate.items():
        u = info.get("utilization")
        if kind not in EVENT_LABEL or not isinstance(u, (int, float)):
            continue
        pct = u * 100 if u <= 1 else u
        r = info.get("resetsAt")
        out.append({"id": kind, "label": EVENT_LABEL[kind], "percent": round(max(0, min(100, pct))),
                    "resetsAt": int(r * 1000 if r < 1e12 else r) if isinstance(r, (int, float)) else None, "resetsText": None})
    return sorted(out, key=lambda x: x["id"] != "five_hour")


_USAGE_LOCK = threading.Lock()


def usage(force: bool = False) -> dict:
    """Limitele abonamentului: /usage din Claude Code (o comandă locală, fără model) pe o sesiune scurtă, ținut un minut."""
    c = AGENT.usage_cache
    if not force and c and time.time() - c[0] < 60:
        return c[1]
    with _USAGE_LOCK:
        c = AGENT.usage_cache
        if not force and c and time.time() - c[0] < 60:
            return c[1]
        plan, limits = None, []
        try:
            plan, limits = parse_usage(AGENT.complete("/usage", timeout=30))
        except Exception:
            pass
        if not limits:
            limits = limits_from_events()
        data = {"ok": True, "available": bool(limits), "plan": plan, "limits": limits}
        AGENT.usage_cache = (time.time(), data)
        return data


def options(prefs: dict) -> dict:
    """Ce poate alege omul în compozitor: modelele și nivelurile de efort oferite de Claude Code, cu alegerea lui."""
    base = AGENT.config_for("")
    m = select_of(base, "model")
    model_opts = flat_options(m)
    model = prefs.get("model") if any(o["value"] == prefs.get("model") for o in model_opts) else (m or {}).get("currentValue")
    cfg = AGENT.config_for(str(model)) if model and m and model != m.get("currentValue") else base
    e = select_of(cfg, "effort")
    effort_opts = flat_options(e)
    effort = prefs.get("effort") if any(o["value"] == prefs.get("effort") for o in effort_opts) else (e or {}).get("currentValue")
    return {"ok": True, "model": {"current": model, "options": model_opts} if m else None,
            "effort": {"current": effort, "options": effort_opts} if e else None}


# ---------------------------------------------------------------- conversațiile, câte mai multe pe document

CHATS: dict = {}            # id -> Chat
_CHATS_LOCK = threading.Lock()
_LOADED = [False]


def _load_all():
    if _LOADED[0]:
        return
    _LOADED[0] = True
    for f in sorted(CHAT_DIR.glob("*.json")) if CHAT_DIR.is_dir() else []:
        try:
            saved = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not saved.get("path"):
            continue
        cid = str(saved.get("id") or f.stem)  # fișierele vechi (o conversație pe PDF) nu au id: e numele fișierului
        c = Chat(cid, saved["path"])
        c.file = f
        c._load(saved)
        CHATS[cid] = c


def _same(a: str, b: str) -> bool:
    return os.path.normcase(str(Path(a))) == os.path.normcase(str(Path(b)))


def chats_for(path: str) -> list:
    with _CHATS_LOCK:
        _load_all()
        mine = [c for c in CHATS.values() if _same(c.path, path) and (c.events or c.running)]
    mine.sort(key=lambda c: (not c.starred, -c.updated))
    return [c.meta() for c in mine]


def new_chat(path: str) -> Chat:
    import uuid
    with _CHATS_LOCK:
        _load_all()
        c = Chat(uuid.uuid4().hex[:16], path)
        CHATS[c.id] = c
        return c


def chat_for(path: str, cid: str | None = None) -> Chat:
    """Conversația cerută (după id) sau, fără id, cea mai recentă a documentului (una nouă dacă nu are)."""
    with _CHATS_LOCK:
        _load_all()
        if cid:
            c = CHATS.get(cid)
            if c and _same(c.path, path):
                return c
            if c:
                raise AcpError("Conversația e a altui document.")
        mine = [c for c in CHATS.values() if _same(c.path, path)]
    if not cid and mine:
        return max(mine, key=lambda c: (bool(c.events), c.updated))
    return new_chat(path)


def get_chat(cid: str) -> Chat:
    with _CHATS_LOCK:
        _load_all()
        c = CHATS.get(cid)
    if not c:
        raise AcpError("Conversația nu mai există.")
    return c


def rename(cid: str, title: str):
    c = get_chat(cid)
    title = re.sub(r"\s+", " ", str(title or "")).strip()[:80]
    if not title:
        raise AcpError("Scrie un nume.")
    c.title, c.title_source = title, "user"
    c._save()
    with c.cond:
        c.cond.notify_all()


def star(cid: str, on: bool):
    c = get_chat(cid)
    c.starred = bool(on)
    c._save()


def delete(cid: str):
    c = get_chat(cid)
    c.close()
    with _CHATS_LOCK:
        CHATS.pop(cid, None)
    try:
        c.file.unlink(missing_ok=True)
    except OSError:
        pass


def save_upload(name: str, data: bytes) -> dict:
    """Un fișier atașat în chat (lipit, tras sau ales): stă în folderul aplicației până îl citește Claude."""
    import uuid
    if len(data) > MAX_FILE:
        raise AcpError("The file is too big (20 MB at most)." if _english() else "Fișierul e prea mare (cel mult 20 MB).")
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", Path(str(name or "fisier")).name).strip(" .") or "fisier"
    fid = uuid.uuid4().hex[:12]
    d = FILES_DIR / fid
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(data)
    kind = "image" if Path(name).suffix.lower() in IMAGE_TYPES else "file"
    return {"id": f"{fid}/{name}", "name": name, "kind": kind}


def upload_path(fid: str) -> dict:
    p = (FILES_DIR / str(fid)).resolve()
    if FILES_DIR.resolve() not in p.parents or not p.is_file():
        raise AcpError("Fișierul atașat nu mai există.")
    return {"path": str(p), "name": p.name, "kind": "image" if p.suffix.lower() in IMAGE_TYPES else "file"}


def written_file(cid: str, f: str) -> str:
    """Un fișier pe care Claude l-a scris în conversația asta (doar pe acestea le deschidem din chat)."""
    c = get_chat(cid)
    for e in c.events:
        if e["type"] == "done" and any(_same(x, f) for x in e.get("files") or []):
            if os.path.isfile(f):
                return str(Path(f))
    raise AcpError("Fișierul nu mai există.")


def shutdown():
    AGENT.stop()
