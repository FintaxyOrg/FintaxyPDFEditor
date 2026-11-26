"""Fișierele Markdown (.md) deschise în editor.

Editorul lucrează doar cu PDF-uri, deci un .md e tipărit întâi într-un PDF de citit, ținut în STATE/md (convertorul
din localtools: Markdown -> HTML -> Edge fără fereastră). Fișierul .md rămâne neatins și lângă el nu apare nimic până
când omul salvează ceva: abia atunci copia (_editat.pdf, _semnat.pdf) se scrie în folderul .md-ului (fx_sign.home_dir).
"""
import hashlib
import json
import shutil
import threading
from pathlib import Path

import fx_sign

CACHE = fx_sign.STATE / "md"
EXT = (".md", ".markdown")
KEEP = 40  # câte documente rămân în cache
_lock = threading.Lock()


def is_md(path) -> bool:
    return Path(str(path)).suffix.lower() in EXT


def _key(path: Path) -> str:
    st = path.stat()
    return hashlib.sha1(f"{path.resolve()}|{st.st_mtime_ns}|{st.st_size}".encode("utf-8")).hexdigest()[:16]


def _prune():
    old = sorted((d for d in CACHE.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime, reverse=True)[KEEP:]
    for d in old:
        shutil.rmtree(d, ignore_errors=True)


def preview(path) -> Path:
    """PDF-ul de citit al unui fișier Markdown (din cache sau făcut acum). Un .md schimbat se tipărește din nou."""
    import localtools
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(f"Fișierul nu mai există: {src.name}")
    folder = CACHE / _key(src)
    target = folder / f"{src.stem}.pdf"
    if target.exists():
        return target
    with _lock:
        if target.exists():
            return target
        folder.mkdir(parents=True, exist_ok=True)
        page = folder / "page.html"
        # imaginile și linkurile relative din .md se caută în folderul lui
        page.write_text(localtools._md_html(src.read_text(encoding="utf-8-sig", errors="replace"), base=src.parent.resolve().as_uri() + "/"),
                        encoding="utf-8")
        try:
            localtools._edge_pdf(page.as_uri(), target)
        finally:
            page.unlink(missing_ok=True)
        (folder / "origin.json").write_text(json.dumps({"source": str(src.resolve())}), encoding="utf-8")
        _prune()
    return target


def source(pdf):
    """Fișierul .md din care a fost făcut acest PDF de citit; None pentru orice alt PDF."""
    pdf = Path(str(pdf))
    try:
        if pdf.parent.parent.resolve() == CACHE.resolve():
            return Path(json.loads((pdf.parent / "origin.json").read_text(encoding="utf-8"))["source"])
    except (OSError, ValueError, KeyError):
        pass
    return None
