"""Aducerea automată a componentelor, ca pe un calculator curat (FX_IGNORE_SYSTEM=1: programele instalate pe
acest calculator sunt ignorate): Node.js, legătura cu Claude, Stirling PDF, LibreOffice. Descarcă ~750 MB și
durează ~8 minute; kiturile deja descărcate pot fi puse în FOLDER/state/components/_downloads ca să nu se reia.

  python tests/test_components.py FOLDER [node claude stirling libreoffice]
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
folder = Path(sys.argv[1]).resolve()
which = [a for a in sys.argv[2:] if not a.startswith("-")] or ["node", "claude", "stirling", "libreoffice"]
os.environ["FX_STATE"] = str(folder / "state")
os.environ["FX_IGNORE_SYSTEM"] = "1"
os.environ.pop("FX_ACP_ADAPTER", None)
sys.path.insert(0, str(ROOT / "bin"))
sys.path.insert(0, str(ROOT / "tests"))
(folder / "state").mkdir(parents=True, exist_ok=True)

import deps  # noqa: E402
import make_fixtures  # noqa: E402

FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  [{str(detail)[:200]}]" if detail and not ok else ""), flush=True)
    if not ok:
        FAILED.append(name)
    return bool(ok)


st = deps.status()
check("calculator „curat”: nimic nu apare ca instalat la început", not any(st["items"][c]["installed"] for c in which),
      {c: st["items"][c]["installed"] for c in which})
for cid in which:
    t = time.time()
    seen = []
    import threading
    box = {}
    th = threading.Thread(target=lambda: box.update(r=deps.provision(cid)))
    th.start()
    while th.is_alive():
        j = deps.job(cid) or {}
        if j.get("line") and (not seen or seen[-1] != j["line"][:14]):
            seen.append(j["line"][:14])
        th.join(1.0)
    r = box.get("r") or {}
    check(f"{cid}: adus în {round(time.time() - t)} s", r.get("state") == "done" and deps.PRESENT[cid](), r)
    print("        etape:", " → ".join(dict.fromkeys(seen)))

NW = subprocess.CREATE_NO_WINDOW
if "node" in which:
    v = subprocess.run([deps.node(), "--version"], capture_output=True, text=True, creationflags=NW).stdout.strip()
    check("Node.js adus pornește", v.startswith("v"), v)
    check("Node.js e cel din folderul aplicației", str(folder) in deps.node(), deps.node())
if "claude" in which:
    import acp_chat
    check("legătura cu Claude e instalată în folderul aplicației", str(folder) in acp_chat.adapter_script(), acp_chat.adapter_script())
    acp_chat.AGENT.start()
    check("adaptorul ACP pornește cu Node.js-ul adus și răspunde la initialize", acp_chat.AGENT.alive() and "promptCapabilities" in str(acp_chat.AGENT.caps) or bool(acp_chat.AGENT.caps),
          acp_chat.AGENT.caps)
    acp_chat.shutdown()
if "libreoffice" in which:
    f = make_fixtures.make(folder / "docs")
    dst = folder / "docs" / "din-libreoffice.pdf"
    t = time.time()
    deps.office_to_pdf(f["docx"], dst, folder / "state")
    import fitz
    with fitz.open(str(dst)) as d:
        check(f"LibreOffice adus convertește Word → PDF ({round(time.time() - t)} s)", len(d) == 1 and "diacritice" in d[0].get_text())
    size = sum(p.stat().st_size for p in (deps.COMP / "libreoffice").rglob("*") if p.is_file()) // 1048576
    check(f"LibreOffice curățat: {size} MB pe disc", size < 1000, size)
if "stirling" in which:
    inst = deps.stirling_dir()
    java = Path(inst) / "runtime" / "jre" / "bin" / "java.exe"
    v = subprocess.run([str(java), "-version"], capture_output=True, text=True, creationflags=NW)
    check("Stirling adus: Java din pachet pornește", v.returncode == 0, v.stderr[:100])
    os.environ["FX_NO_COMPONENTS"] = "1"
    import editor_server
    t = time.time()
    port = editor_server.Stirling.ensure(wait=240)
    check(f"Stirling adus pornește și răspunde ({round(time.time() - t)} s)", editor_server.Stirling.ok(port))
    try:
        import json
        pid = json.loads(editor_server.Stirling.FILE.read_text(encoding="utf-8"))["pid"]
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=NW)
    except Exception:
        pass
left = [p.name for p in (deps.COMP / "_downloads").glob("*")] if (deps.COMP / "_downloads").exists() else []
check("kiturile descărcate sunt șterse după despachetare", not left, left)
print("\n" + ("COMPONENTELE SE ADUC SINGURE: TOATE TESTELE AU TRECUT" if not FAILED else f"{len(FAILED)} TESTE PICATE: {FAILED}"))
sys.exit(1 if FAILED else 0)
