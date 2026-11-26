"""Fișierele Markdown (.md) și documentele Word (.docx, .doc, .rtf, .odt) deschise în editor.

Editorul lucrează doar cu PDF-uri, deci un astfel de fișier e tipărit întâi într-un PDF de citit, ținut în STATE/md:
  - Markdown: convertorul din localtools (Markdown -> HTML -> Edge fără fereastră);
  - Word: Microsoft Office dacă e instalat, altfel LibreOffice fără fereastră (localtools.office_one).
Fișierul original rămâne neatins și lângă el nu apare nimic până când omul salvează ceva: abia atunci copia
(_editat.pdf, _semnat.pdf) se scrie în folderul originalului (fx_sign.home_dir).
"""
import hashlib
import json
import shutil
import threading
from pathlib import Path

import fx_sign

CACHE = fx_sign.STATE / "md"  # numele rămâne „md” și pentru Word: fx_sign.home_dir îl recunoaște după el
MD_EXT = (".md", ".markdown")
WORD_EXT = (".docx", ".doc", ".docm", ".dotx", ".dot", ".rtf", ".odt")
EXT = MD_EXT + WORD_EXT
KEEP = 40  # câte documente rămân în cache
_lock = threading.Lock()


def is_md(path) -> bool:
    return Path(str(path)).suffix.lower() in MD_EXT


def is_word(path) -> bool:
    return Path(str(path)).suffix.lower() in WORD_EXT


def is_doc(path) -> bool:
    """Fișier care nu e PDF, dar pe care editorul îl deschide (prin PDF-ul lui de citit)."""
    return Path(str(path)).suffix.lower() in EXT


def _key(path: Path) -> str:
    st = path.stat()
    return hashlib.sha1(f"{path.resolve()}|{st.st_mtime_ns}|{st.st_size}".encode("utf-8")).hexdigest()[:16]


def _prune():
    old = sorted((d for d in CACHE.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime, reverse=True)[KEEP:]
    for d in old:
        shutil.rmtree(d, ignore_errors=True)


def _from_md(src: Path, folder: Path, target: Path):
    import localtools
    page = folder / "page.html"
    # imaginile și linkurile relative din .md se caută în folderul lui
    page.write_text(localtools._md_html(src.read_text(encoding="utf-8-sig", errors="replace"), base=src.parent.resolve().as_uri() + "/"),
                    encoding="utf-8")
    try:
        localtools._edge_pdf(page.as_uri(), target)
    finally:
        page.unlink(missing_ok=True)


def _from_word(src: Path, folder: Path, target: Path):
    import localtools
    try:
        localtools.office_one(src, target)
    except localtools.NeedOffice:
        raise RuntimeError("Documentele Word se deschid cu Microsoft Office sau LibreOffice. " + localtools.NEED_OFFICE)
    except Exception as e:
        raise RuntimeError(f"Nu am putut deschide {src.name}: {e}")


def preview(path) -> Path:
    """PDF-ul de citit al unui fișier Markdown sau Word (din cache sau făcut acum). Un fișier schimbat se tipărește din nou."""
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
        try:
            (_from_md if is_md(src) else _from_word)(src, folder, target)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)  # fără PDF: nu lăsăm un folder gol în cache
            raise
        (folder / "origin.json").write_text(json.dumps({"source": str(src.resolve())}), encoding="utf-8")
        _prune()
    return target


def source(pdf):
    """Fișierul (.md, .docx...) din care a fost făcut acest PDF de citit; None pentru orice alt PDF."""
    pdf = Path(str(pdf))
    try:
        if pdf.parent.parent.resolve() == CACHE.resolve():
            return Path(json.loads((pdf.parent / "origin.json").read_text(encoding="utf-8"))["source"])
    except (OSError, ValueError, KeyError):
        pass
    return None
