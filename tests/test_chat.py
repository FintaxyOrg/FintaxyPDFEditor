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
    done = [e for e in events if e["type"] == "done"][-1]
    check("fișierul scris de Claude apare la finalul turei", any(x.endswith("nota-agent.txt") for x in done.get("files") or []), str(done))
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

    # sesiunea închisă (nefolosită) se reia: aceeași sesiune Claude Code, fără istoric trimis ca text
    sid = chat.session_id
    acp_chat.AGENT.close_session(sid)
    chat.send("Ce număr are contractul?", 1, [], False)
    events, seq = drain(chat, seq, revs)
    text = "".join(e["text"] for e in events if e["type"] == "text")
    check("sesiune închisă: se reia (session/resume), nu se trimite istoricul", chat.session_id == sid and "Istoric: False" in text, text[-90:])

    # modelul și efortul din compozitor
    opts = acp_chat.options({"model": "opus", "effort": "max"})
    check("opțiuni: modelele și efortul vin de la Claude Code", [o["value"] for o in opts["model"]["options"]] == ["default", "opus", "haiku"]
          and opts["model"]["current"] == "opus" and opts["effort"]["current"] == "max", str(opts))
    chat.send("Ce număr are contractul?", 1, [], False, prefs={"model": "opus", "effort": "max"})
    events, seq = drain(chat, seq, revs)
    text = "".join(e["text"] for e in events if e["type"] == "text")
    check("modelul și efortul ales ajung la sesiune", "Model: opus/max" in text, text[-90:])

    # atașamente: imaginea merge ca imagine, orice fișier ca listă de căi
    png = acp_chat.save_upload("captura.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    doc = acp_chat.save_upload("nota.txt", b"salut")
    check("atașament salvat, cu numele curățat", png["kind"] == "image" and doc["kind"] == "file" and png["name"] == "captura.png", str(png))
    chat.send("", 1, [], False, files=[acp_chat.upload_path(png["id"]), acp_chat.upload_path(doc["id"])])
    events, seq = drain(chat, seq, revs)
    text = "".join(e["text"] for e in events if e["type"] == "text")
    user = [e for e in events if e["type"] == "user"][-1]
    check("atașamente: imaginea ajunge ca imagine, fișierele ca listă", "Imagini: 1" in text and "Atașate: 1" in text, text[-90:])
    check("fără text, mesajul cere să se uite la fișier", "atașat" in user["text"] and [x["name"] for x in user["files"]] == ["captura.png", "nota.txt"], str(user))
    try:
        acp_chat.upload_path("../../etc/x")
        check("atașament în afara folderului e refuzat", False)
    except acp_chat.AcpError:
        check("atașament în afara folderului e refuzat", True)

    # stopReason refusal: mesaj pe înțeles
    chat.send("refuz", 1, [], False)
    events, seq = drain(chat, seq, revs)
    check("refuz: tura se încheie cu explicația", events[-1]["type"] == "done" and "refuzat" in events[-1].get("note", ""), str(events[-1]))

    # agentul moare la mijloc
    chat.send("Numără rar.", 1, [], False)
    time.sleep(0.8)
    acp_chat.AGENT.proc.kill()
    events, seq = drain(chat, seq, revs, until=20)
    check("agent oprit pe neașteptate: eroare clară, fără blocaj", not chat.running and events[-1]["type"] == "error", str(events[-1]))
    chat.send("Ce număr are contractul?", 1, [], False)
    events, seq = drain(chat, seq, revs)
    text = "".join(e["text"] for e in events if e["type"] == "text")
    check("după oprire, următorul mesaj repornește agentul", events[-1]["type"] == "done", str(events[-1]))
    check("după oprire, sesiunea nouă primește istoricul (reluarea nu mai e posibilă)", "Istoric: True" in text, text[-90:])

    # Oprește la un agent care nu ascultă: tura se încheie în câteva secunde, celelalte conversații merg mai departe
    other = acp_chat.new_chat(str(f["doc"]))
    chat.send("Fii încăpățânat.", 1, [], False)
    time.sleep(0.5)
    t = time.time()
    chat.cancel()
    events, seq = drain(chat, seq, revs, until=15)
    check("Oprește fără răspuns de la agent: tura se încheie în ~3 s", not chat.running and events[-1].get("stop") == "cancelled"
          and time.time() - t < 6, f"{time.time() - t:.1f}s {events[-1]}")
    check("Oprește nu oprește agentul (celelalte conversații)", acp_chat.AGENT.alive())
    other.send("Ce număr are contractul?", 1, [], False)
    oe, _ = drain(other, 0, {})
    check("altă conversație a aceluiași PDF merge în paralel", oe[-1]["type"] == "done", str(oe[-1]))

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
    again = acp_chat.Chat(chat.id, str(f["doc"]))
    again._load(json.loads(saved.read_text(encoding="utf-8")))
    check("după repornire, conversația e la loc", len(again.events) > 5 and again.events[0]["type"] == "user", len(again.events))
    check("gândirea și cererile de acord nu se salvează", not any(e["type"] in ("thought", "perm") for e in again.events))
    check("«Mereu în acest chat» se păstrează după repornire", "Write" in again.always, str(again.always))
    check("sesiunea Claude Code se ține minte pentru reluare", bool(again.session_sig) and again.session_id == chat.session_id,
          f"{again.session_id} {chat.session_id}")

    # mai multe conversații pe document: listă, titlu automat, redenumire, stea, ștergere
    lst = acp_chat.chats_for(str(f["doc"]))
    check("lista: ambele conversații ale PDF-ului", {c["id"] for c in lst} == {chat.id, other.id}, str(lst))
    end = time.time() + 10
    while other.title != "Titlu de test" and time.time() < end:
        time.sleep(0.2)
    check("titlu automat după primul răspuns (modelul rapid)", other.title == "Titlu de test" and other.title_source == "auto", other.title)
    check("titlul ajunge și în citirea evenimentelor", other.since(0, {}, wait=0)["title"] == "Titlu de test")
    acp_chat.rename(other.id, "  Contractul   de sediu ")
    acp_chat.star(other.id, True)
    lst = acp_chat.chats_for(str(f["doc"]))
    check("redenumire + stea: prima în listă, cu numele dat", lst[0]["id"] == other.id and lst[0]["title"] == "Contractul de sediu" and lst[0]["starred"], str(lst[0]))
    check("titlul pus de om nu e suprascris", other.title_source == "user")
    check("fără id: se deschide cea mai recentă conversație", acp_chat.chat_for(str(f["doc"])).id in (chat.id, other.id))
    ht = acp_chat.heuristic_title("te rog, rezumă contractul de la https://x.ro?")
    check("titlu din întrebare (fără Claude)", ht == "Rezumă contractul de la", ht)
    ofile = other.file
    acp_chat.delete(other.id)
    check("ștergere: dispare din listă și de pe disc", other.id not in {c["id"] for c in acp_chat.chats_for(str(f["doc"]))} and not ofile.exists())
    fresh = acp_chat.new_chat(str(f["doc"]))
    check("Conversație nouă: goală, cea veche rămâne în istoric", fresh.since(0, {}, wait=0.1)["events"] == [] and saved.exists())

    # limitele abonamentului
    u = acp_chat.usage(force=True)
    five = next((x for x in u["limits"] if x["id"] == "five_hour"), {})
    check("utilizare: limitele din /usage", u["available"] and u["plan"] == "Max" and five.get("percent") == 23 and bool(five.get("resetsAt")), str(u))
    check("data de resetare fără an e în viitorul apropiat", acp_chat.parse_reset("Nov 30, 3:59 PM GMT+2", now=1795000000) is not None)
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
