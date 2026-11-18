"""Serverul editorului pentru teste: stare separată (FX_STATE), port și token fixe, fără să deschidă ferestre.
Nu atinge setările, semnăturile sau aplicația instalată a omului.

  python tests/dev_server.py FOLDER [PORT] [--fake-claude]     -> http://127.0.0.1:PORT/?t=test&path=...
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
folder = Path(sys.argv[1]).resolve()
port = next((a for a in sys.argv[2:] if a.isdigit()), "8765")
os.environ.setdefault("FX_STATE", str(folder / "state"))
os.environ.setdefault("FX_TOKEN", "test")
os.environ["FX_PORT"] = port
if "--fake-claude" in sys.argv:  # chatul vorbește cu agentul simulat, nu cu Claude
    import json
    os.environ["FX_ACP_CMD"] = json.dumps([sys.executable, str(ROOT / "tests" / "fake_acp_agent.py")])
sys.path.insert(0, str(ROOT / "bin"))
sys.path.insert(0, str(ROOT / "tests"))

import make_fixtures  # noqa: E402

docs = folder / "docs"
f = make_fixtures.make(docs)
lib = folder / "semnaturi"
lib.mkdir(parents=True, exist_ok=True)
Path(os.environ["FX_STATE"]).mkdir(parents=True, exist_ok=True)

import editor_server  # noqa: E402

srv = editor_server.make_server(str(lib), standalone=True)
editor_server.CLIENTS["dev"] = 9e12  # o „fereastră” care nu se închide: serverul nu se oprește singur
print(f"http://127.0.0.1:{port}/?t={os.environ['FX_TOKEN']}&path={f['doc']}", flush=True)
editor_server.run(srv)
