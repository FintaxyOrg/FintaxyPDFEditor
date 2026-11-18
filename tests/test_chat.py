"""Chatul cu Claude, fără Claude: aplicația vorbește ACP cu un agent simulat (tests/fake_acp_agent.py).
Verifică tot drumul din aplicație: pornirea agentului, sesiunea în folderul PDF-ului, textul în bucăți, uneltele,
acordul la scriere (refuz, o dată, mereu), Oprește, conexiunile MCP (CRM), conectarea expirată, conversația nouă.

  python tests/test_chat.py [FOLDER]
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Stare separată: limba și conversațiile aplicației de pe acest calculator nu intră în test și nu sunt atinse.
os.environ["FX_STATE"] = tempfile.mkdtemp(prefix="pdfsign-chat-state-")
sys.path.insert(0, str(ROOT / "bin"))
sys.path.insert(0, str(ROOT / "tests"))

import make_fixtures  # noqa: E402

FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""), flush=True)
    if not ok:
        FAILED.append(name)


def drain(chat, seq, revs, until=60, on_perm=None):
    seen = {}
    end = time.time() + until
    while time.time() < end:
        r = chat.since(seq, revs, wait=2)
        for e in r["events"]:
            seen[e["seq"]] = dict(e)
            revs[str(e["seq"])] = e.get("rev", 0)
            seq = max(seq, e["seq"])
            if e["type"] == "perm" and e.get("state") == "ask" and on_perm:
                on_perm(e)
        if not r["running"] and not chat.since(seq, revs, wait=0.2)["events"]:
            break
    return [seen[k] for k in sorted(seen)], seq


def main(folder: Path):
    os.environ["FX_ACP_CMD"] = json.dumps([sys.executable, str(ROOT / "tests" / "fake_acp_agent.py")])
    import acp_chat
    f = make_fixtures.make(folder)
    check("stare: chat disponibil", acp_chat.status()["available"])
    chat = acp_chat.chat_for(str(f["doc"]))
    revs = {}

    crm = [{"name": "fintaxy-crm", "url": "https://crm.example/mcp", "token": "fxc_test"}]
    chat.send("Ce număr are contractul?", 2, crm, False)
    events, seq = drain(chat, 0, revs)
    kinds = [e["type"] for e in events]
    text = "".join(e["text"] for e in events if e["type"] == "text")
    check("ordinea evenimentelor: om, gândire, unealtă, text, gata", kinds == ["user", "thought", "tool", "text", "done"], str(kinds))
    check("bucățile de text sunt lipite într-un singur mesaj", "numărul **42** și e din 18.11.2026" in text, text[:120])
    check("sesiunea lucrează în folderul PDF-ului", f"Folder de lucru: {folder}" in text, text)
    check("conexiunea CRM (MCP) ajunge la agent", "MCP: fintaxy-crm" in text, text)
    check("agentul primește contextul PDF Sign", "Sistem: True" in text)
    check("prima sesiune: fără istoric în față", "Istoric: False" in text, text[-60:])
    tool = next(e for e in events if e["type"] == "tool")
    check("unealta apare terminată", tool["status"] == "completed" and "Read" in tool["title"], str(tool))
    check("pagina curentă e trimisă cu mesajul", events[0].get("page") == 2)

    # acord la scriere: refuz
    target = folder / "nota-agent.txt"
    asked = []

    def deny(e):
        asked.append(e)
        chat.answer(e["id"], "deny")
    chat.send("Scrie un fișier.", 1, crm, False)
    events, seq = drain(chat, seq, revs, on_perm=deny)
    perm = [e for e in events if e["type"] == "perm"]
    check("scrierea cere acordul omului, cu fișierul arătat", len(asked) == 1 and "nota-agent.txt" in asked[0].get("detail", ""), str(asked))
    check("refuz: nu se scrie nimic", not target.exists() and perm and perm[-1]["state"] == "denied", str(perm))

    # acord o dată
    chat.send("Scrie un fișier.", 1, crm, False)
    events, seq = drain(chat, seq, revs, on_perm=lambda e: chat.answer(e["id"], "allow"))
    check("acord: fișierul e scris", target.exists() and target.read_text() == "test")
    target.unlink()

    # „mereu în conversația asta”: a doua oară nu mai întreabă
    chat.send("Scrie un fișier.", 1, crm, False)
    drained, seq = drain(chat, seq, revs, on_perm=lambda e: chat.answer(e["id"], "always"))
    target.unlink()
    asked2 = []
    chat.send("Scrie un fișier.", 1, crm, False)
    events, seq = drain(chat, seq, revs, on_perm=lambda e: asked2.append(e))
    check("„Permite mereu”: a doua scriere nu mai întreabă", not asked2 and target.exists(), str(asked2))

    # un singur mesaj o dată
    chat.send("Numără rar.", 1, crm, False)
    try:
        chat.send("alt mesaj", 1, crm, False)
        check("al doilea mesaj în timpul răspunsului e refuzat", False)
    except acp_chat.AcpError as err:
        check("al doilea mesaj în timpul răspunsului e refuzat", "încă răspunde" in str(err))
    time.sleep(1.0)
    t = time.time()
    chat.cancel()
    events, seq = drain(chat, seq, revs, until=20)
    check("Oprește: răspunsul se oprește imediat", not chat.running and events[-1]["type"] == "done" and events[-1]["stop"] == "cancelled"
          and time.time() - t < 5, str(events[-1]))

    # conectare expirată
    chat.send("login", 1, crm, False)
    events, seq = drain(chat, seq, revs)
    err = next((e for e in events if e["type"] == "error"), {})
    check("conectare expirată: mesaj clar + butonul de conectare", err.get("needLogin") is True and "Conectează Claude" in err.get("text", ""), str(err))

    # altă conexiune MCP = sesiune nouă
    sid = chat.session_id
    chat.send("Ce număr are contractul?", 1, [], False)
    events, seq = drain(chat, seq, revs)
    text = "".join(e["text"] for e in events if e["type"] == "text")
    check("conexiunile schimbate pornesc o sesiune nouă", chat.session_id != sid and "MCP: niciunul" in text, text[-80:])
    check("sesiunea nouă primește ce s-a vorbit înainte", "Istoric: True" in text, text[-60:])

    # agentul moare la mijloc
    chat.send("Numără rar.", 1, [], False)
    time.sleep(0.8)
    acp_chat.AGENT.proc.kill()
    events, seq = drain(chat, seq, revs, until=20)
    check("agent oprit pe neașteptate: eroare clară, fără blocaj", not chat.running and events[-1]["type"] == "error", str(events[-1]))
    chat.send("Ce număr are contractul?", 1, [], False)
    events, seq = drain(chat, seq, revs)
    check("după oprire, următorul mesaj repornește agentul", events[-1]["type"] == "done", str(events[-1]))

    # titluri pe înțelesul omului și detaliul cererii de acord
    check("titlu unealtă: comandă", acp_chat.describe_tool("Bash", "x", {"command": "mkdir a\npython b.py", "description": "Face folderul"}) == "Rulează o comandă: Face folderul")
    check("titlu unealtă: fișier", acp_chat.describe_tool("Read", "Read C:/x/contract.pdf", {"file_path": "C:/x/contract.pdf"}) == "Citește contract.pdf")
    check("titlu unealtă: MCP cu argumente", acp_chat.describe_tool("mcp__fintaxy-crm__search_records", "", {"object": "deals", "query": "Popescu"}) == "Search records (fintaxy-crm): object=deals Popescu")
    check("titlu unealtă: script lipit în comandă = doar primul rând", "\n" not in acp_chat.describe_tool("Bash", "", {"command": "cat > f <<EOF\n" + "x\n" * 50}))
    check("detaliu acord: modificare (vechi / nou)", acp_chat.permission_detail("Edit", {"file_path": "a.txt", "old_string": "unu", "new_string": "doi"}) == "a.txt\n− unu\n+ doi")
    check("cardul de acord al unei comenzi nu are «Mereu»", perm[-1].get("noAlways") is False and "nota-agent.txt" in perm[-1].get("detail", ""), str(perm[-1]))

    # istoricul rămâne după repornirea aplicației
    saved = chat.file
    check("istoricul e salvat pe disc", saved.is_file())
    again = acp_chat.Chat(str(f["doc"]))
    check("după repornire, conversația e la loc", len(again.events) > 5 and again.events[0]["type"] == "user" and again.needs_context,
          len(again.events))
    check("gândirea și cererile de acord nu se salvează", not any(e["type"] in ("thought", "perm") for e in again.events))

    chat.reset()
    check("Conversație nouă: istoricul e gol", chat.since(0, {}, wait=0.1)["events"] == [] and not saved.exists())
    acp_chat.shutdown()
    time.sleep(0.5)
    check("la închidere, agentul e oprit", not acp_chat.AGENT.alive())

    # conectarea: fișier de credențiale golit = neconectat
    home = folder / "cfg"
    home.mkdir(exist_ok=True)
    os.environ["CLAUDE_CONFIG_DIR"] = str(home)
    os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    check("fără fișier de conectare = neconectat", acp_chat.logged_in() is False)
    (home / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {"accessToken": "", "refreshToken": "", "expiresAt": 0}}))
    check("conectare golită (expirată) = neconectat", acp_chat.logged_in() is False)
    (home / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {"accessToken": "a", "refreshToken": "r",
                                                                         "refreshTokenExpiresAt": (time.time() + 86400) * 1000}}))
    check("conectare validă = conectat", acp_chat.logged_in() is True)

    print("\n" + ("CHATUL (SIMULAT) A TRECUT TOATE TESTELE" if not FAILED else f"{len(FAILED)} TESTE PICATE: {FAILED}"))
    return 1 if FAILED else 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="pdfsign-chat-"))
    sys.exit(main(target))
