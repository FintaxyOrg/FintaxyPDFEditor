"""Un agent ACP simulat (JSON-RPC pe stdin/stdout, câte un mesaj pe rând), pentru testele chatului fără Claude:
răspunde la initialize / session/new / session/prompt cu aceleași feluri de mesaje ca adaptorul adevărat
(text în bucăți, gândire, unelte, cerere de acord, anulare).

Ce face depinde de textul mesajului:
  „scrie”   -> cere acordul pentru scrierea unui fișier; îl scrie doar dacă e aprobat
  „numără”  -> răspuns lung, în multe bucăți (pentru Oprește)
  „login”   -> eroare de autentificare, ca atunci când Claude Code nu e conectat
  „refuz”   -> tură încheiată cu stopReason „refusal”
  „încăpățânat” -> ignoră Oprește (aplicația trebuie să încheie singură tura)
  „/usage”  -> limitele abonamentului, ca Claude Code
  un prompt de sistem care cere un titlu -> „Titlu de test”
  altfel    -> „citește” PDF-ul (o unealtă) și răspunde cu calea folderului de lucru
"""
import json
import sys
import threading
import time
from pathlib import Path

SESSIONS = {}
CANCEL = set()
PENDING = {}
LOCK = threading.Lock()
NEXT = [1000]


def send(msg):
    with LOCK:
        sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def update(sid, u):
    send({"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": sid, "update": u}})


def text(sid, t):
    update(sid, {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": t}})


def ask(method, params):
    with LOCK:
        NEXT[0] += 1
        rid = NEXT[0]
    ev = threading.Event()
    PENDING[rid] = {"event": ev, "result": None}
    send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
    ev.wait(120)
    return PENDING.pop(rid)["result"] or {}


MODELS = [{"value": "default", "name": "Default"}, {"value": "opus", "name": "Opus"}, {"value": "haiku", "name": "Haiku"}]
EFFORTS = [{"value": "low", "name": "Low"}, {"value": "high", "name": "High"}, {"value": "max", "name": "Max"}]


def config(sid):
    s = SESSIONS[sid]
    return [{"id": "model", "type": "select", "name": "Model", "currentValue": s["model"], "options": MODELS},
            {"id": "effort", "type": "select", "name": "Effort", "currentValue": s["effort"], "options": EFFORTS}]


def prompt(rid, p):
    sid = p["sessionId"]
    if SESSIONS[sid].get("closed"):
        return send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32000, "message": "Session closed"}})
    body = " ".join(b.get("text", "") for b in p.get("prompt") or [])
    images = sum(1 for b in p.get("prompt") or [] if b.get("type") == "image")
    if isinstance(SESSIONS[sid]["system"], str) and "name chat conversations" in SESSIONS[sid]["system"]:
        text(sid, "Titlu de test")
        return send({"jsonrpc": "2.0", "id": rid, "result": {"stopReason": "end_turn"}})
    if body.strip() == "/usage":
        text(sid, "## Claude Max subscription usage\n\n**5-hour limit** — **23%** · Resets Nov 30, 3:59 PM GMT+2\n"
                  "**Weekly · all models** — **61%** · Resets Dec 2, 9:00 AM GMT+2\n")
        return send({"jsonrpc": "2.0", "id": rid, "result": {"stopReason": "end_turn"}})
    # doar mesajul omului hotărăște scenariul, nu și istoricul pus în față la o sesiune nouă
    low = body.rsplit("]\n\n", 1)[-1].lower()
    SESSIONS[sid]["context"] = "Earlier in this conversation" in body
    cwd = SESSIONS[sid]["cwd"]
    if "login" in low:
        text(sid, "Failed to authenticate: OAuth session expired and could not be refreshed")
        return send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32000, "message": "Authentication required"}})
    if "refuz" in low:
        text(sid, "Nu pot face asta.")
        return send({"jsonrpc": "2.0", "id": rid, "result": {"stopReason": "refusal"}})
    if "încăpățânat" in low:
        for i in range(400):  # nu se uită la anulare
            text(sid, f"{i} ")
            time.sleep(0.05)
        return send({"jsonrpc": "2.0", "id": rid, "result": {"stopReason": "end_turn"}})
    update(sid, {"sessionUpdate": "agent_thought_chunk", "content": {"type": "text", "text": "Mă uit la document."}})
    if "scrie" in low:
        target = Path(cwd) / "nota-agent.txt"
        tc = {"toolCallId": "t-write", "title": f"Write {target.name}", "kind": "edit", "status": "pending",
              "rawInput": {"file_path": str(target), "content": "test"}, "_meta": {"claudeCode": {"toolName": "Write"}}}
        update(sid, {"sessionUpdate": "tool_call", **tc})
        res = ask("session/request_permission", {"sessionId": sid, "toolCall": tc, "options": [
            {"optionId": "allow", "kind": "allow_once", "name": "Allow"},
            {"optionId": "allow_always", "kind": "allow_always", "name": "Always allow"},
            {"optionId": "reject", "kind": "reject_once", "name": "Reject"}]})
        out = res.get("outcome") or {}
        if out.get("outcome") == "selected" and out.get("optionId", "").startswith("allow"):
            target.write_text("test", encoding="utf-8")
            update(sid, {"sessionUpdate": "tool_call_update", "toolCallId": "t-write", "status": "completed"})
            text(sid, f"Am scris {target.name}.")
        else:
            update(sid, {"sessionUpdate": "tool_call_update", "toolCallId": "t-write", "status": "failed"})
            text(sid, "Nu am scris nimic: nu mi-ai dat acordul.")
        return send({"jsonrpc": "2.0", "id": rid, "result": {"stopReason": "end_turn"}})
    if "lung" in low:
        # ca o tură adevărată cu script lipit în comandă: titlu uriaș, comandă lungă la acord, răspuns lung cu cod și tabel
        script = "import sys\n" + "\n".join(f"print('rand {i} cu text destul de lung ca sa se rupa pe mai multe randuri in panou')" for i in range(60))
        cmd = 'mkdir -p "$TEMP/oferta" && cat > "$TEMP/oferta/build.py" <<EOF\n' + script + "\nEOF\npython build.py && echo OK"
        tc = {"toolCallId": "t-long", "title": cmd, "kind": "execute", "status": "pending", "rawInput": {"command": cmd},
              "_meta": {"claudeCode": {"toolName": "Bash"}}}
        update(sid, {"sessionUpdate": "tool_call", **tc})
        ask("session/request_permission", {"sessionId": sid, "toolCall": tc, "options": [
            {"optionId": "allow", "kind": "allow_once", "name": "Allow"}, {"optionId": "reject", "kind": "reject_once", "name": "Reject"}]})
        update(sid, {"sessionUpdate": "tool_call_update", "toolCallId": "t-long", "status": "completed"})
        text(sid, "## Rezultat\n\nUn paragraf **lung** " + "cu multe cuvinte " * 30 + "\n\n")
        text(sid, "| Coloana A | Coloana B | Coloana C cu nume lung |\n|---|---|---|\n| 1 | doi | " + "x" * 80 + " |\n\n")
        text(sid, "```python\n" + script[:900] + "\n```\n\n")
        for i in range(1, 80):
            if sid in CANCEL:
                CANCEL.discard(sid)
                return send({"jsonrpc": "2.0", "id": rid, "result": {"stopReason": "cancelled"}})
            text(sid, f"- punctul {i} din listă, cu un text care se întinde pe rând\n")
            time.sleep(0.08)
        return send({"jsonrpc": "2.0", "id": rid, "result": {"stopReason": "end_turn"}})
    if "numără" in low or "numara" in low:
        for i in range(1, 400):
            if sid in CANCEL:
                CANCEL.discard(sid)
                return send({"jsonrpc": "2.0", "id": rid, "result": {"stopReason": "cancelled"}})
            text(sid, f"{i}\n")
            time.sleep(0.05)
        return send({"jsonrpc": "2.0", "id": rid, "result": {"stopReason": "end_turn"}})
    update(sid, {"sessionUpdate": "tool_call", "toolCallId": "t-read", "title": "Read contract.pdf", "kind": "read",
                 "status": "pending", "_meta": {"claudeCode": {"toolName": "Read"}}})
    time.sleep(0.2)
    update(sid, {"sessionUpdate": "tool_call_update", "toolCallId": "t-read", "status": "completed"})
    for part in ("Contractul are numărul **42** ", "și e din 18.11.2026. ", f"Folder de lucru: {cwd}. ",
                 f"MCP: {','.join(m['name'] for m in SESSIONS[sid]['mcp']) or 'niciunul'}. ",
                 f"Sistem: {'PDF Sign' in SESSIONS[sid]['system']}. ", f"Istoric: {SESSIONS[sid].get('context')}. ",
                 f"Model: {SESSIONS[sid]['model']}/{SESSIONS[sid]['effort']}. ", f"Imagini: {images}. ",
                 f"Atașate: {body.count('Attached files')}. ", f"Sesiune: {sid}."):
        text(sid, part)
        time.sleep(0.05)
    # sugestiile de continuare, în bucăți (ca să se vadă că eticheta nu clipește în pagină cât se scrie)
    for part in ("\n<follo", "wups>\nCine semnează contractul?\n- Când expiră?\n", "</followups>"):
        text(sid, part)
        time.sleep(0.05)
    send({"jsonrpc": "2.0", "id": rid, "result": {"stopReason": "end_turn"}})


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        m = json.loads(raw)
        if "method" not in m:
            w = PENDING.get(m.get("id"))
            if w:
                w["result"] = m.get("result")
                w["event"].set()
            continue
        method, p, rid = m["method"], m.get("params") or {}, m.get("id")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": 1, "agentCapabilities": {
                "loadSession": True, "promptCapabilities": {"image": True}, "sessionCapabilities": {"resume": {}, "close": {}}},
                                                             "agentInfo": {"name": "fake", "version": "0"}}})
        elif method == "session/new":
            sid = f"s{len(SESSIONS) + 1}"
            meta = p.get("_meta") or {}
            sysp = meta.get("systemPrompt")
            opts = (meta.get("claudeCode") or {}).get("options") or {}
            SESSIONS[sid] = {"cwd": p.get("cwd"), "mcp": p.get("mcpServers") or [],
                             "system": sysp if isinstance(sysp, str) else (sysp or {}).get("append", ""),
                             "model": opts.get("model") or "default", "effort": "high"}
            send({"jsonrpc": "2.0", "id": rid, "result": {"sessionId": sid, "configOptions": config(sid),
                                                           "modes": {"currentModeId": "default", "availableModes": [{"id": "default"}]}}})
        elif method in ("session/resume", "session/load"):
            sid = p.get("sessionId")
            if sid not in SESSIONS:
                send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32002, "message": "Resource not found"}})
            else:
                SESSIONS[sid]["closed"] = False
                SESSIONS[sid]["resumed"] = SESSIONS[sid].get("resumed", 0) + 1
                send({"jsonrpc": "2.0", "id": rid, "result": {"configOptions": config(sid)}})
        elif method == "session/close":
            if p.get("sessionId") in SESSIONS:
                SESSIONS[p["sessionId"]]["closed"] = True
            send({"jsonrpc": "2.0", "id": rid, "result": {}})
        elif method == "session/set_config_option":
            sid = p["sessionId"]
            SESSIONS[sid][p["configId"]] = p["value"]
            send({"jsonrpc": "2.0", "id": rid, "result": {"configOptions": config(sid)}})
        elif method == "session/prompt":
            threading.Thread(target=prompt, args=(rid, p), daemon=True).start()
        elif method == "session/cancel":
            CANCEL.add(p.get("sessionId"))
        elif rid is not None:
            send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}})


if __name__ == "__main__":
    main()
