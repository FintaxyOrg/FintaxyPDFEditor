"""Chatul cu Claude prin ACP, pe viu (folosește abonamentul Claude al calculatorului: un mesaj scurt).
Verifică: pornirea adaptorului, sesiunea în folderul PDF-ului, citirea PDF-ului de către Claude, fluxul de
evenimente, cererea de acord la scriere (refuzată aici) și oprirea.

  python tests/test_chat_live.py [FOLDER]      (FX_ACP_ADAPTER = scriptul adaptorului, dacă nu e instalat în aplicație)
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))
sys.path.insert(0, str(ROOT / "tests"))

import make_fixtures  # noqa: E402

FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""), flush=True)
    if not ok:
        FAILED.append(name)


def drain(chat, seq, revs, until=180, on_perm=None):
    """Citește evenimentele până se termină tura; întoarce toate evenimentele văzute (ultima variantă a fiecăruia)."""
    seen = {}
    end = time.time() + until
    while time.time() < end:
        r = chat.since(seq, revs, wait=5)
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
    import acp_chat
    f = make_fixtures.make(folder)
    st = acp_chat.status()
    print("status:", {k: st[k] for k in ("available", "step", "node", "adapter", "loggedIn")})
    if not st["available"]:
        print("Chatul nu e disponibil pe calculatorul ăsta (pasul lipsă: %s): testul pe viu e sărit." % st["step"])
        return 2
    chat = acp_chat.chat_for(str(f["doc"]))
    revs = {}

    t = time.time()
    chat.send("Citește PDF-ul și spune-mi într-un singur rând: ce număr are contractul și din ce dată e?", 1, [], False)
    events, seq = drain(chat, 0, revs)
    text = "".join(e["text"] for e in events if e["type"] == "text")
    print(f"  ({round(time.time() - t, 1)} s) răspuns: {text.strip()[:300]!r}")
    kinds = [e["type"] for e in events]
    check("mesajul omului apare în conversație", kinds[:1] == ["user"])
    check("Claude a folosit o unealtă ca să citească PDF-ul", "tool" in kinds, str([e.get("title") for e in events if e["type"] == "tool"]))
    check("răspunsul conține numărul contractului (42) și data", "42" in text and "18.11.2026" in text, text[:200])
    check("tura s-a încheiat curat", kinds[-1] == "done" and not chat.running, str(events[-1]))
    check("fără erori", "error" not in kinds, str([e for e in events if e["type"] == "error"]))

    # scrierea de fișiere cere acord: îl refuzăm și verificăm că nu s-a scris nimic
    asked = []

    def deny(e):
        asked.append(e)
        chat.answer(e["id"], "deny")
    target = folder / "nota-claude.txt"
    chat.send(f"Scrie un fișier text „{target.name}” lângă PDF, cu un singur cuvânt în el: test.", 2, [], False)
    events, seq = drain(chat, seq, revs, on_perm=deny)
    kinds = [e["type"] for e in events]
    check("scrierea unui fișier a cerut acordul omului", len(asked) >= 1, str([(e.get("title"), e.get("detail")) for e in asked]))
    check("după refuz, fișierul nu există", not target.exists())
    check("a doua tură s-a încheiat", kinds[-1] in ("done", "error") and not chat.running, str(events[-1]))

    # oprirea la mijloc
    chat.send("Numără rar de la 1 la 200, câte un număr pe rând.", 1, [], False)
    time.sleep(6)
    chat.cancel()
    events, seq = drain(chat, seq, revs, until=60)
    check("Oprește: tura se termină în câteva secunde", not chat.running and events[-1]["type"] == "done", str(events[-1]))

    chat.reset()
    check("Conversație nouă: istoricul e gol", chat.since(0, {}, wait=0.1)["events"] == [])
    acp_chat.shutdown()
    time.sleep(1)
    check("la închidere, procesul adaptorului e oprit", not acp_chat.AGENT.alive())
    print("\n" + ("CHATUL A TRECUT TOATE TESTELE" if not FAILED else f"{len(FAILED)} TESTE PICATE: {FAILED}"))
    return 1 if FAILED else 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="pdfsign-chat-"))
    sys.exit(main(target))
