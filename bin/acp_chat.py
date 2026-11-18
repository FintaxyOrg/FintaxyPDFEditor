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
    hit = shutil.which("node")
    if hit:
        return hit
    p = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs" / "node.exe"
    return str(p) if p.is_file() else ""


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
        p = subprocess.run(cmd, cwd=str(ACP_DIR), stdin=subprocess.DEVNULL, capture_output=True, timeout=900,
                           creationflags=NO_WINDOW, shell=False)
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
        raise RuntimeError("Lipsește Node.js. Instalează-l întâi (butonul de mai sus).")
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
- Read the PDF with the Read tool (use the `pages` parameter for long files). Each message says which page the person is on.
- Answer in the person's language (usually Romanian), briefly and concretely. Markdown is rendered.
- Never change the original PDF. When asked to produce or change a file, write the result next to the original with a
  clear suffix in the name, and say where it is.
- The app itself can sign (handwritten image or certificate), fill forms, edit text, merge, split, compress, convert:
  when that is what the person needs, tell them which button or tool to use (Ctrl+K searches every tool).
- Messages that start with "Comentariu în PDF" / "PDF comment" are notes the person pinned on a page: the page number,
  the nearby text and sometimes a screenshot path come with them.
- You cannot enter a PIN or sign with a certificate yourself: that always happens in the Windows PIN window."""


def tool_title(u: dict) -> str:
    title = (u.get("title") or "").strip()
    name = ((u.get("_meta") or {}).get("claudeCode") or {}).get("toolName") or ""
    if name.startswith("mcp__"):
        parts = name.split("__")
        title = f"{parts[-1].replace('_', ' ').capitalize()} ({parts[1]})"
    return title or name or "Unealtă"


class Chat:
    def __init__(self, path: str):
        self.path = str(Path(path))
        self.session_id = None
        self.events = []          # tot ce s-a întâmplat, numerotat: editorul cere „ce e nou după N”
        self.cond = threading.Condition()
        self.running = False
        self.cancelled = False
        self.perms = {}           # id din chat -> {"rid", "options"}
        self.tools = {}
        self.always = set()       # „Permite mereu în conversația asta”, pe tip de unealtă
        self.mcp_sig = None

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

    def since(self, seq: int, revs: dict, wait: float = 25.0) -> dict:
        """Evenimentele noi (și cele de text care au mai crescut); așteaptă până apare ceva."""
        end = time.time() + wait
        with self.cond:
            while True:
                # noi de tot, plus cele deja trimise care s-au schimbat între timp (text mai lung, unealtă terminată)
                out = [e for e in self.events if e["seq"] > seq or e.get("rev", 0) > int(revs.get(str(e["seq"]), 0))]
                if out or time.time() >= end:
                    return {"ok": True, "events": out, "running": self.running, "last": len(self.events)}
                self.cond.wait(max(0.05, min(1.0, end - time.time())))

    def touch(self, ev: dict, **changes):
        with self.cond:
            ev.update(changes)
            ev["rev"] = ev.get("rev", 0) + 1
            self.cond.notify_all()

    # ---- de la adaptor
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
        elif kind == "tool_call":
            self.close_text()
            ev = self.emit("tool", id=u.get("toolCallId"), title=tool_title(u), status=u.get("status") or "pending",
                           kind=u.get("kind") or "other")
            self.tools[u.get("toolCallId")] = ev
        elif kind == "tool_call_update":
            ev = self.tools.get(u.get("toolCallId"))
            if not ev:
                self.close_text()
                ev = self.emit("tool", id=u.get("toolCallId"), title=tool_title(u), status=u.get("status") or "pending",
                               kind=u.get("kind") or "other")
                self.tools[u.get("toolCallId")] = ev
            changes = {}
            if u.get("status"):
                changes["status"] = u["status"]
            if u.get("title"):
                changes["title"] = tool_title(u)
            if changes:
                self.touch(ev, **changes)

    def on_permission(self, rid, params: dict):
        options = params.get("options") or []
        tc = params.get("toolCall") or {}
        known = self.tools.get(tc.get("toolCallId")) or {}
        title = tool_title(tc) if (tc.get("title") or tc.get("_meta")) else known.get("title", "Acțiune")
        name = ((tc.get("_meta") or {}).get("claudeCode") or {}).get("toolName") or title
        allow = next((o for o in options if o.get("kind") == "allow_once"), None) or next(
            (o for o in options if o.get("kind") == "allow_always"), None)
        if not self.running or self.cancelled:
            return AGENT.respond(rid, {"outcome": {"outcome": "cancelled"}})
        if name in self.always and allow:
            return AGENT.respond(rid, {"outcome": {"outcome": "selected", "optionId": allow["optionId"]}})
        detail = ""
        raw = tc.get("rawInput")
        if isinstance(raw, dict):
            detail = str(raw.get("command") or raw.get("file_path") or raw.get("path") or raw.get("url") or "")[:400]
        self.close_text()
        ev = self.emit("perm", id=f"p{len(self.events) + 1}", title=title, detail=detail, state="ask", tool=name)
        self.perms[ev["id"]] = {"rid": rid, "options": options, "event": ev, "tool": name}

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
        self.touch(p["event"], state="allowed" if choice in ("allow", "always") else "denied")
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
        with self.cond:
            self.running = False
            self.cond.notify_all()

    # ---- către adaptor
    def ensure_session(self, mcp: list, user_settings: bool):
        AGENT.start()
        sig = json.dumps([mcp, user_settings], sort_keys=True)
        if self.session_id and self.session_id in AGENT.sessions and sig == self.mcp_sig:
            return
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
        if modes.get("currentModeId") not in (None, "default") and any(m.get("id") == "default" for m in modes.get("availableModes") or []):
            try:  # orice acțiune trece prin acordul omului, oricum ar porni adaptorul
                AGENT.request("session/set_mode", {"sessionId": self.session_id, "modeId": "default"}, timeout=30)
            except AcpError:
                pass

    def send(self, text: str, page: int, mcp: list, user_settings: bool, images: list | None = None):
        with self.cond:
            if self.running:
                raise AcpError("Claude încă răspunde la mesajul dinainte. Așteaptă sau apasă Oprește.")
            self.running, self.cancelled = True, False
        self.emit("user", text=text, page=page)
        threading.Thread(target=self._turn, args=(text, page, mcp, user_settings, images or []), daemon=True).start()

    def _turn(self, text, page, mcp, user_settings, images):
        try:
            before = self._mtime()
            self.ensure_session(mcp, user_settings)
            body = f"[PDF: {self.path} · pagina curentă: {page}]\n\n{text}"
            prompt = [{"type": "text", "text": body}]
            for img in images:  # capturile de zonă: Claude le citește de pe disc
                prompt[0]["text"] += f"\nCaptură: {img}"
            res = AGENT.request("session/prompt", {"sessionId": self.session_id, "prompt": prompt}, timeout=None)
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
            self.cond.notify_all()


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
