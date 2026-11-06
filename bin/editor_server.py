"""Serverul local al editorului PDF din panoul lui Claude (mod-ul pdf-sign).

Pornit de mod cu `python fx_sign.py serve LIBRARY`, ține cât ține sesiunea. Ascultă doar pe 127.0.0.1,
pe un port liber, și cere la fiecare apel API un token generat la pornire (pagina îl primește în URL).
Ce face omul în editor ajunge la mod ca evenimente JSON, câte unul pe rând, pe stdout:

  {"event": "ready", "port": 51234, "token": "..."}
  {"event": "saved", "source": PDF, "out": PDF, "sigs": [...], "texts": n, "edits": n}
  {"event": "comment", "path": PDF, "page": n, "text": "...", "context": "...", "capture": PNG|null}
  {"event": "tool", "source": PDF, "out": FIȘIER, "tool": "Comprimă", "kind": "pdf|file|folder|json"}

Uneltele Stirling PDF merg prin API-ul local al aplicației Stirling PDF (pornită dacă nu rulează).
"""
import base64
import hashlib
import http.server
import io
import json
import mimetypes
import os
import re
import secrets
import socketserver
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import zipfile
from pathlib import Path

import fitz

import fx_sign
from fx_sign import MM, STATE, label_of, library, out, stamp, undo_file

# În aplicația portabilă (PyInstaller) folderul editor/ e despachetat în sys._MEIPASS.
EDITOR_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "editor"
LOCK = threading.RLock()  # PyMuPDF nu e sigur pe mai multe fire
TOKEN = secrets.token_urlsafe(18)
LIB = ""
STANDALONE = False  # pornit de desktop.py (aplicația separată), nu de mod
CLIENTS: dict = {}  # ferestrele deschise (doar în aplicația separată): id -> ultimul semn de viață


def event(_name: str, **data):
    out({"event": _name, **data})


# ---------- documente ----------

_docs: dict = {}


def open_doc(path: str) -> fitz.Document:
    p = str(Path(path))
    mtime = os.path.getmtime(p)
    hit = _docs.get(p.lower())
    if hit and hit[0] == mtime:
        return hit[1]
    # Din memorie, nu din fișier: Windows nu lasă suprascrierea unui fișier ținut deschis.
    doc = fitz.open(stream=Path(p).read_bytes(), filetype="pdf")
    _docs[p.lower()] = (mtime, doc)
    if len(_docs) > 6:  # păstrăm doar câteva deschise
        for k in list(_docs)[:-6]:
            _docs.pop(k, None)
    return doc


def doc_info(path: str) -> dict:
    with LOCK:
        doc = open_doc(path)
        xfa = fx_sign.is_xfa(doc)
        return {
            "path": str(Path(path)), "name": Path(path).name, "dir": str(Path(path).parent),
            "pages": [{"w": p.rect.width, "h": p.rect.height, "rot": p.rotation} for p in doc],
            "signed": fx_sign.is_signed(doc),
            "sigfields": fx_sign.signature_fields(doc),
            # Formularele XFA (ANAF) se completează în programul lor: Adobe citește datele din XFA, nu din câmpuri.
            "xfa": xfa, "fields": 0 if xfa else sum(1 for p in doc for w in p.widgets()
                                                    if w.field_type in fx_sign.FIELD_KINDS and not w.field_flags & 1),
            "attachments": attachments(doc),
        }


def attachments(doc) -> list:
    """Fișierele atașate PDF-ului (ex. XML-ul declarației ANAF): la nivelul documentului și pe pagini."""
    items = []
    for i, name in enumerate(doc.embfile_names()):
        info = doc.embfile_info(name)
        items.append({"key": f"e{i}", "name": info.get("filename") or name, "size": info.get("size") or info.get("length") or 0})
    for page in doc:
        for a in page.annots(types=[fitz.PDF_ANNOT_FILE_ATTACHMENT]):
            info = a.file_info
            items.append({"key": f"a{a.xref}", "name": info.get("filename") or f"atasament-{a.xref}", "size": info.get("size") or 0,
                          "page": page.number + 1})
    return items


def save_attachment(path: str, key: str) -> str:
    """Scoate atașamentul lângă PDF, în „<nume> - atasamente”, și dă calea lui."""
    with LOCK:
        doc = open_doc(path)
        if key.startswith("e"):
            name = doc.embfile_names()[int(key[1:])]
            fname = doc.embfile_info(name).get("filename") or name
            data = doc.embfile_get(name)
        else:  # atașament pus pe o pagină (adnotare)
            data, fname = None, ""
            for page in doc:
                for a in page.annots(types=[fitz.PDF_ANNOT_FILE_ATTACHMENT]):
                    if f"a{a.xref}" == key:
                        data, fname = a.get_file(), a.file_info.get("filename") or f"atasament-{a.xref}"
            if data is None:
                raise RuntimeError("Nu găsesc atașamentul.")
    folder = Path(path).parent / f"{Path(path).stem} - atasamente"
    folder.mkdir(exist_ok=True)
    fname = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", Path(fname).name) or "atasament"
    target = folder / fname
    target.write_bytes(data)
    return str(target)


def page_png(path: str, n: int, width: int) -> bytes:
    with LOCK:
        page = open_doc(path)[n - 1]
        z = max(200, min(width, 3000)) / page.rect.width
        return page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False).tobytes("png")


def color_hex(c: int) -> str:
    return "#%06x" % (c & 0xFFFFFF)


def page_runs(path: str, n: int) -> list:
    """Rândurile de text de pe pagină pentru „Editează text”. Un rând se editează întreg, ca bucățile lui să se poată
    lungi fără să intre una peste alta; fiecare bucată (segment) își păstrează stilul și fontul."""
    with LOCK:
        doc = open_doc(path)
        page = doc[n - 1]
        rot = page.rotation_matrix
        embedded = fx_sign.embedded_fonts(page)
        lines = []
        for b in page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]:
            for line in b.get("lines", []):
                if line.get("dir", (1, 0)) != (1, 0) and abs(line["dir"][1]) > 0.01:
                    continue  # text rotit: îl lăsăm
                segs = []
                for s in line["spans"]:
                    style = (s["font"], round(s["size"], 1), s["flags"] & (2 | 16), s["color"])
                    cur = segs[-1] if segs else None
                    if cur and cur["style"] == style:
                        cur["text"] += s["text"]
                        cur["raw"] = [min(cur["raw"][0], s["bbox"][0]), min(cur["raw"][1], s["bbox"][1]),
                                      max(cur["raw"][2], s["bbox"][2]), max(cur["raw"][3], s["bbox"][3])]
                        continue
                    if not s["text"].strip() and not segs:
                        continue
                    segs.append({
                        "style": style, "text": s["text"], "raw": list(s["bbox"]), "origin": list(s["origin"]),
                        "size": round(s["size"], 2), "fontName": s["font"], "font": fx_sign.font_key(s["font"]),
                        "bold": bool(s["flags"] & 16) or "bold" in s["font"].lower(),
                        "italic": bool(s["flags"] & 2) or "italic" in s["font"].lower() or "oblique" in s["font"].lower(),
                        "color": color_hex(s["color"]), "fonts": fx_sign.font_refs(doc, s["font"], embedded),
                    })
                while segs and not segs[-1]["text"].strip():
                    segs.pop()
                if not segs:
                    continue
                segs[-1]["text"] = segs[-1]["text"].rstrip()
                for sg in segs:
                    sg.pop("style")
                raw = [min(sg["raw"][0] for sg in segs), min(sg["raw"][1] for sg in segs),
                       max(sg["raw"][2] for sg in segs), max(sg["raw"][3] for sg in segs)]
                box = fitz.Rect(raw) * rot  # cum se vede pagina
                lines.append({"text": "".join(sg["text"] for sg in segs), "raw": raw,
                              "bbox": [box.x0, box.y0, box.x1, box.y1], "segments": segs})
        return lines


def font_bytes(path: str, ref: str):
    """Fontul unui segment pentru browser (ca textul din caseta de editare să arate ca în PDF)."""
    if ref.startswith("x:"):
        with LOCK:
            name, ext, _type, buf = open_doc(path).extract_font(int(ref[2:]))
        return (buf, f"font/{ext}") if buf and ext in ("ttf", "otf") else (None, "")
    if ref in fx_sign.font_index().values() and Path(ref).suffix.lower() in (".ttf", ".otf"):
        return Path(ref).read_bytes(), f"font/{Path(ref).suffix.lower()[1:]}"
    return None, ""


def near_text(path: str, n: int, x: float, y: float) -> str:
    """Textul de lângă un punct (pt, pagina cum se vede): rândul cel mai apropiat."""
    with LOCK:
        page = open_doc(path)[n - 1]
        rot = page.rotation_matrix
        best, dist = "", 1e9
        for b in page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]:
            for line in b.get("lines", []):
                text = "".join(s["text"] for s in line["spans"]).strip()
                if not text:
                    continue
                r = fitz.Rect(line["bbox"]) * rot
                dx = 0 if r.x0 <= x <= r.x1 else min(abs(x - r.x0), abs(x - r.x1))
                dy = 0 if r.y0 <= y <= r.y1 else min(abs(y - r.y0), abs(y - r.y1))
                d = dx + dy * 1.5
                if d < dist:
                    best, dist = text, d
        return best[:160] if dist < 120 else ""


def region_text(path: str, n: int, rect: list) -> str:
    with LOCK:
        page = open_doc(path)[n - 1]
        r = fitz.Rect(rect) * page.derotation_matrix
        return re.sub(r"\s+", " ", page.get_textbox(r)).strip()[:600]


def capture(path: str, n: int, rect: list) -> str:
    with LOCK:
        page = open_doc(path)[n - 1]
        r = (fitz.Rect(rect) * page.derotation_matrix) & page.cropbox
        folder = STATE / "captures"
        folder.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^\w.-]+", "_", Path(path).stem)[:60]
        dest = folder / f"{name}_p{n}_{time.strftime('%Y%m%d-%H%M%S')}.png"
        page.get_pixmap(clip=r, dpi=200, alpha=False).save(str(dest))
        return str(dest)


# ---------- comentarii ----------

def comments_file(path: str) -> Path:
    (STATE / "comments").mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(str(Path(path)).lower().encode("utf-8")).hexdigest()[:16]
    return STATE / "comments" / f"{key}.json"


def load_comments(path: str) -> list:
    f = comments_file(path)
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("comments", [])
    except (OSError, ValueError):
        return []


def save_comments(path: str, items: list):
    comments_file(path).write_text(json.dumps({"path": str(Path(path)), "comments": items}, ensure_ascii=False, indent=1),
                                   encoding="utf-8")


# ---------- Stirling PDF ----------

class Stirling:
    """Serverul Stirling PDF. Îl pornim noi, fără fereastră, direct cu Java-ul și jar-ul aplicației, pe un port
    ales de noi: gata în ~15 s (aplicația Stirling-PDF.exe are nevoie de ~50 s și alege un port oarecare).
    Rămâne pornit după ce se închide editorul și e refolosit (portul în stirling.json)."""
    port = None
    spec = None
    version = ""
    LOCK = threading.Lock()
    FILE = STATE / "stirling.json"
    SPEC_FILE = STATE / "stirling-spec.json"

    @staticmethod
    def install_dir():
        for p in (r"C:\Program Files\Stirling PDF", os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Stirling PDF")):
            if os.path.exists(os.path.join(p, "Stirling-PDF.exe")):
                return p
        return None

    @classmethod
    def ok(cls, port) -> bool:
        import requests
        try:
            return requests.get(f"http://127.0.0.1:{port}/api/v1/info/status", timeout=2).ok
        except Exception:
            return False

    @classmethod
    def find_port(cls):
        """Stirling-ul nostru din stirling.json, dacă mai răspunde și vede aceleași programe externe.
        Aplicația Stirling-PDF.exe nu e folosită: pornește cu PATH-ul ei și cu căi de Linux pentru LibreOffice & co.,
        deci are dezactivate conversiile."""
        try:
            info = json.loads(cls.FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not cls.ok(info.get("port")):
            return None
        if info.get("deps") != cls.deps()[2]:  # s-a instalat ceva între timp: îl repornim ca să-l vadă
            subprocess.run(["taskkill", "/PID", str(info.get("pid")), "/T", "/F"], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return None
        return info["port"]

    @staticmethod
    def deps():
        """Programele externe ale lui Stirling (LibreOffice, Ghostscript, OCR...): PATH, căi și semnătura lor."""
        import sysconfig
        import winreg
        pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        tools = STATE / "tools"
        local = Path(os.environ.get("LOCALAPPDATA", ""))

        def glob1(base: Path, pattern: str):
            hit = sorted(base.glob(pattern), reverse=True) if base.exists() else []
            return hit[0] if hit else None

        scripts = Path(sysconfig.get_path("scripts", f"{os.name}_user"))
        paths = {
            "soffice": pf / "LibreOffice" / "program" / "soffice.exe",
            "calibre": pf / "Calibre2" / "ebook-convert.exe",
            "ocrmypdf": scripts / "ocrmypdf.exe",
            "weasyprint": glob1(tools / "weasyprint", "**/weasyprint.exe"),
        }
        paths = {k: str(v) for k, v in paths.items() if v and Path(v).exists()}
        # Ghostscript pe Windows e gswin64c.exe; Stirling cheamă „gs”, deci îi facem o copie cu numele ăsta.
        gs = glob1(pf / "gs", "gs*/bin/gswin64c.exe")
        bin_dir = tools / "bin"
        if gs:
            bin_dir.mkdir(parents=True, exist_ok=True)
            for src, dst in ((gs, "gs.exe"), (gs.with_name("gsdll64.dll"), "gsdll64.dll")):
                target = bin_dir / dst
                if src.exists() and (not target.exists() or target.stat().st_size != src.stat().st_size):
                    fx_sign.shutil.copy2(src, target)
        extra = [bin_dir, scripts, glob1(pf, "qpdf*/bin"), pf / "Tesseract-OCR", glob1(pf, "ImageMagick-*"),
                 glob1(local / "Microsoft" / "WinGet" / "Packages", "oschwartz10612.Poppler*/poppler-*/Library/bin"),
                 local / "Microsoft" / "WinGet" / "Links"]
        # LibreOffice și Calibre au căile lor (paths), nu stau în PATH: LibreOffice are un python.exe al lui (fără
        # OpenCV), pe care Stirling l-ar lua înaintea celui instalat. unoconvert lipsește intenționat: fără un unoserver
        # pornit, Stirling îl așteaptă 50 s la fiecare conversie înainte să treacă la soffice.
        # PATH-ul proaspăt din registru (programele instalate după pornirea serverului), fără WindowsApps:
        # acolo „python3” e doar scurtătura spre Microsoft Store, iar Stirling îl încearcă înaintea lui „python”.
        reg = []
        for root, key in ((winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                          (winreg.HKEY_CURRENT_USER, "Environment")):
            try:
                with winreg.OpenKey(root, key) as k:
                    reg += os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]).split(";")
            except OSError:
                pass
        path = [str(p) for p in extra if p and Path(p).exists()] + [p for p in reg if p and "WindowsApps" not in p]
        sig = sorted(list(paths.values()) + [p for p in map(str, extra) if p and Path(p).exists()])
        return ";".join(dict.fromkeys(path)), paths, sig

    @classmethod
    def start(cls, inst: str) -> int:
        import socket
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        jar = next(Path(inst, "libs").glob("stirling-pdf-*.jar"))
        logs = STATE / "stirling-logs"
        logs.mkdir(parents=True, exist_ok=True)
        home = Path(os.environ.get("APPDATA", str(STATE))) / "Stirling-PDF"  # aceleași setări ca aplicația
        home.mkdir(parents=True, exist_ok=True)
        path, paths, sig = cls.deps()
        env = {**os.environ, "PATH": path}
        props = [f"-Dsystem.customPaths.operations.{k}={v}" for k, v in paths.items()]
        tessdata = STATE / "tools" / "tessdata"
        tess = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR" / "tessdata"
        if tessdata.exists() and tess.exists():
            # Pe lângă limbi, Tesseract vrea în același folder pdf.ttf și configs/ (pentru PDF-ul cu text).
            for f in tess.iterdir():
                dst = tessdata / f.name
                if f.is_dir() and not dst.exists():
                    fx_sign.shutil.copytree(f, dst)
                elif f.is_file() and not dst.exists():
                    fx_sign.shutil.copy2(f, dst)
        if tessdata.exists():
            env["TESSDATA_PREFIX"] = str(tessdata)
            props.append(f"-Dsystem.tessdataDir={tessdata}")
        # Aceiași parametri ca Stirling-PDF.exe; TieredStopAtLevel=1 aproape înjumătățește pornirea.
        cmd = [str(Path(inst, "runtime", "jre", "bin", "java.exe")), "-Xmx1g", "-XX:TieredStopAtLevel=1",
               "-DBROWSER_OPEN=false", "-DSTIRLING_PDF_TAURI_MODE=true", f"-Dlogging.file.path={logs}",
               "-Dlogging.file.name=stirling-pdf.log", f"-Dserver.port={port}", "-Dserver.forward-headers-strategy=none",
               "-Dsecurity.enableLogin=false", "-Dsecurity.csrfDisabled=true", "-Dsystem.enableUrlToPDF=true", *props,
               "-jar", str(jar)]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        p = subprocess.Popen(cmd, cwd=str(home), env=env, creationflags=flags, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        cls.FILE.write_text(json.dumps({"port": port, "pid": p.pid, "deps": sig}), encoding="utf-8")
        return port

    @classmethod
    def ensure(cls, wait=300) -> int:
        if cls.port and cls.ok(cls.port):
            return cls.port
        with cls.LOCK:  # pornirea din timp și o cerere din editor nu pornesc două
            if cls.port and cls.ok(cls.port):
                return cls.port
            cls.port = cls.find_port()
            if cls.port:
                return cls.port
            inst = cls.install_dir()
            if not inst:
                raise RuntimeError("Stirling PDF nu e instalat pe calculator (winget install --id StirlingTools.StirlingPDF -e).")
            port = cls.start(inst)
            t = time.time()
            while time.time() - t < wait:
                time.sleep(0.5)
                if cls.ok(port):
                    cls.port = port
                    return port
            raise RuntimeError("Am pornit Stirling PDF, dar nu a răspuns în timp util.")

    @classmethod
    def warm(cls):
        """Pornește Stirling în fundal când se deschide editorul, ca semnarea cu certificat să nu mai aștepte."""
        def go():
            try:
                cls.ensure()
                cls.tools(fresh=True)
            except Exception:
                traceback.print_exc(file=sys.stderr)
        threading.Thread(target=go, daemon=True).start()

    @classmethod
    def tools(cls, fresh=False) -> dict:
        """Uneltele din API-ul Stirling, simplificate pentru formularele din editor (ținute și pe disc)."""
        if cls.spec is None and not fresh:
            try:
                saved = json.loads(cls.SPEC_FILE.read_text(encoding="utf-8"))
                cls.version, cls.spec = saved["version"], saved["tools"]
            except (OSError, ValueError, KeyError):
                pass
        if cls.spec is None or fresh:
            import requests
            port = cls.ensure()
            raw = requests.get(f"http://127.0.0.1:{port}/v1/api-docs", timeout=60).json()
            cls.version = raw.get("info", {}).get("version", "")
            cls.spec = simplify_spec(raw)
            cls.SPEC_FILE.write_text(json.dumps({"version": cls.version, "tools": cls.spec}, ensure_ascii=False), encoding="utf-8")
        return {"version": cls.version, "tools": cls.spec}

    @classmethod
    def run(cls, endpoint: str, fields: dict, files: list, timeout=900):
        import requests
        port = cls.ensure()
        if not files:  # Stirling primește doar multipart, chiar și fără fișier (ex. pagină web → PDF)
            files = [(k, (None, x)) for k, v in fields.items() for x in (v if isinstance(v, list) else [v])]
            fields = {}
        r = requests.post(f"http://127.0.0.1:{port}{endpoint}", data=fields, files=files, timeout=timeout)
        return r


def simplify_spec(raw: dict) -> dict:
    schemas = raw.get("components", {}).get("schemas", {})

    def resolve(s):
        for _ in range(12):
            if "$ref" not in s:
                break
            s = schemas.get(s["$ref"].split("/")[-1], {})
        return s

    def props(s):
        s = resolve(s)
        res, req = {}, set(s.get("required", []))
        # allOf: toate părțile; oneOf/anyOf (fișier încărcat sau id de pe server): prima variantă.
        for part in s.get("allOf", []) + s.get("oneOf", [])[:1] + s.get("anyOf", [])[:1]:
            p2, r2 = props(part)
            res.update(p2)
            req |= r2
        res.update(s.get("properties", {}))
        return res, req

    tools = {}
    for path, ops in raw.get("paths", {}).items():
        op = ops.get("post")
        if not op:
            continue
        content = op.get("requestBody", {}).get("content", {})
        schema = (content.get("multipart/form-data") or {}).get("schema")
        if not schema:
            continue
        pr, req = props(schema)
        fields = []
        for name, v in pr.items():
            v = resolve(v) if "$ref" in v else v
            t, fmt = v.get("type", "string"), v.get("format", "")
            item = {}
            if t == "array":
                item = v.get("items", {})
                item = resolve(item) if "$ref" in item else item
            fields.append({
                "name": name, "type": t, "format": fmt,
                "itemType": item.get("type", ""), "itemFormat": item.get("format", ""),
                "enum": list(dict.fromkeys(v.get("enum") or item.get("enum") or [])) or None,
                "default": v.get("default"), "example": v.get("example"),
                "required": name in req, "description": (v.get("description") or "")[:400],
            })
        tools[path] = {
            "summary": op.get("summary", ""), "description": (op.get("description") or "")[:600],
            "tag": (op.get("tags") or [""])[0], "fields": fields,
            "responses": list(op.get("responses", {}).get("200", {}).get("content", {}).keys()),
        }
    return tools


EXT = {"application/pdf": ".pdf", "application/zip": ".zip", "text/csv": ".csv", "text/markdown": ".md",
       "text/plain": ".txt", "text/html": ".html", "image/png": ".png", "image/jpeg": ".jpg", "application/json": ".json",
       "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
       "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
       "application/epub+zip": ".epub", "application/javascript": ".js", "text/javascript": ".js", "application/xml": ".xml"}


def free_name(folder: Path, stem: str, ext: str) -> Path:
    p = folder / f"{stem}{ext}"
    k = 2
    while p.exists():
        p = folder / f"{stem}-{k}{ext}"
        k += 1
    return p


class Reply:
    """Un răspuns făcut de noi, în locul unuia de la Stirling, pentru conversiile pe care Stirling nu le duce la capăt."""
    def __init__(self, content: bytes, ctype: str, name: str):
        self.ok, self.status_code, self.content, self.text = True, 200, content, ""
        self.headers = {"Content-Type": ctype, "Content-Disposition": f'attachment; filename="{name}"'}


def workaround(endpoint: str, fields: dict, files: list, src: Path):
    """Ocolișuri pentru convertoarele care nu merg în Stirling pe Windows; None = merge Stirling cum e."""
    quiet = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if endpoint == "/api/v1/convert/url/pdf":
        # Stirling 3.0.2: „No current ServletRequestAttributes”. Pagina o tipărește Edge, fără fereastră.
        url = str(fields.get("urlInput") or "").strip()
        if not re.match(r"(?i)^https?://", url):
            raise ValueError("Scrie adresa completă a paginii (cu https://).")
        work = STATE / "url2pdf"
        work.mkdir(parents=True, exist_ok=True)
        out = work / "page.pdf"
        out.unlink(missing_ok=True)
        subprocess.run([fx_sign.browser(), "--headless=new", "--disable-gpu", f"--user-data-dir={work / 'profile'}",
                        "--no-pdf-header-footer", "--virtual-time-budget=10000", f"--print-to-pdf={out}", url],
                       capture_output=True, timeout=180, creationflags=quiet)
        if not out.exists():
            raise RuntimeError("Edge nu a putut tipări pagina.")
        host = re.sub(r"[^\w.-]+", "_", urllib.parse.urlparse(url).netloc) or "pagina"
        return Reply(out.read_bytes(), "application/pdf", f"{host}.pdf")
    if endpoint == "/api/v1/convert/ebook/pdf":
        # Calibre nu poate randa direct în PDF aici (Qt WebEngine se blochează); trece prin Word, apoi LibreOffice.
        calibre = Stirling.deps()[1].get("calibre")
        book = next((f for name, f in files if name == "fileInput"), None)
        if not calibre or not book:
            return None
        work = STATE / "ebook2pdf"
        fx_sign.shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        inp = work / ("carte" + (Path(book[0]).suffix or ".epub"))
        inp.write_bytes(book[1])
        docx = work / "carte.docx"
        subprocess.run([calibre, str(inp), str(docx)], capture_output=True, timeout=600, creationflags=quiet)
        if not docx.exists():
            raise RuntimeError("Calibre nu a putut citi cartea.")
        r = Stirling.run("/api/v1/convert/file/pdf", {}, [("fileInput", (Path(book[0]).stem + ".docx", docx.read_bytes(),
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))])
        return r
    if endpoint == "/api/v1/convert/pdf/vector" and fields.get("outputFormat", "eps") == "eps":
        # EPS ține o singură pagină: un PDF cu mai multe pagini devine câte un .eps pe pagină (într-un folder).
        with LOCK:
            doc = fitz.open(stream=src.read_bytes(), filetype="pdf")
        if len(doc) < 2:
            return None
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for i in range(len(doc)):
                one = fitz.open()
                one.insert_pdf(doc, from_page=i, to_page=i)
                r = Stirling.run("/api/v1/convert/pdf/vector", fields, [("fileInput", (f"p{i + 1}.pdf", one.tobytes(), "application/pdf"))])
                if not r.ok:
                    raise RuntimeError(f"Stirling a răspuns {r.status_code} la pagina {i + 1}: {r.text[:300]}")
                z.writestr(f"{src.stem}_p{i + 1}.eps", r.content)
        return Reply(buf.getvalue(), "application/zip", f"{src.stem}_eps.zip")
    return None


def run_tool(body: dict) -> dict:
    src = Path(body["path"])
    endpoint = body["endpoint"]
    spec = Stirling.tools()["tools"].get(endpoint)
    if not spec:
        raise ValueError(f"Unealta {endpoint} nu există în Stirling.")
    def val(v):
        return "true" if v is True else "false" if v is False else str(v)

    # O listă pleacă drept câmp repetat (ex. limbile la OCR).
    fields = {k: ([val(x) for x in v] if isinstance(v, list) else val(v))
              for k, v in (body.get("fields") or {}).items() if v is not None and v != ""}
    files = []
    # Unele endpoint-uri (analysis/*) nu-și descriu câmpurile în specificație, dar primesc tot `fileInput`.
    main = next((f["name"] for f in spec["fields"] if f["name"] in ("fileInput", "file")), "fileInput")
    extra = body.get("files") or {}
    if main and body.get("usesDocument", True):
        files.append((main, (src.name, src.read_bytes(), "application/pdf")))
    for name, items in extra.items():
        for it in items:
            data = base64.b64decode(it["b64"].split(",")[-1])
            files.append((name, (it["name"], data, it.get("type") or "application/octet-stream")))
    if endpoint == "/api/v1/security/cert-sign":
        fields.setdefault("certType", "WINDOWS_STORE")
    r = workaround(endpoint, fields, files, src) or Stirling.run(endpoint, fields, files)
    ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if not r.ok:
        msg = r.text[:600]
        try:
            j = r.json()
            msg = j.get("detail") or j.get("message") or j.get("error") or msg
        except ValueError:
            pass
        if r.status_code == 403 and "disabled" in str(msg):
            raise RuntimeError(f"Unealta e dezactivată în Stirling: îi lipsește un program extern ({missing_program(endpoint)}).")
        raise RuntimeError(f"Stirling a răspuns {r.status_code}: {msg}")
    if ctype == "application/json":
        try:
            return {"ok": True, "kind": "json", "json": r.json()}
        except ValueError:
            pass
    disp = r.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", disp)
    remote = urllib.parse.unquote(m.group(1)) if m else ""
    ext = Path(remote).suffix.lower() or EXT.get(ctype) or mimetypes.guess_extension(ctype) or ".bin"
    suffix = re.sub(r"[^\w-]+", "-", body.get("suffix") or "rezultat").strip("-")
    folder = src.parent
    stem = src.stem
    if not body.get("usesDocument", True):
        # Conversie din alt fișier: rezultatul ia numele fișierului convertit, în folderul PDF-ului deschis.
        stem = re.sub(r'[<>:"/\\|?*]+', "_", body.get("outStem") or Path(remote).stem or "convertit")
        suffix = ""
    if suffix == "semnat" and stem.lower().endswith("_semnat"):
        target = src  # semnătura digitală peste copia cu semnătura olografă
        bak = fx_sign.backup_path(target)
        fx_sign.shutil.copy2(target, bak)
    elif ext == ".zip" and body.get("unzip", True):
        dest = free_name(folder, (f"{stem}_{suffix}" if suffix else stem), "")
        dest.mkdir(parents=True)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            z.extractall(dest)
        return {"ok": True, "kind": "folder", "out": str(dest), "files": sorted(p.name for p in dest.iterdir())[:50]}
    else:
        target = free_name(folder, (f"{stem}_{suffix}" if suffix else stem), ext)
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_bytes(r.content)
    os.replace(tmp, target)
    return {"ok": True, "kind": "pdf" if ext == ".pdf" else "file", "out": str(target)}


def missing_program(endpoint: str) -> str:
    """Programul extern de care are nevoie o unealtă Stirling dezactivată (după adresa ei)."""
    for pattern, prog in ((r"cbr", "PDF → CBR cere WinRAR"), (r"ocr", "OCR cere Tesseract și OCRmyPDF"),
                          (r"ebook|epub", "eBook cere Calibre"), (r"html/pdf|url/pdf|markdown/pdf", "HTML → PDF cere WeasyPrint"),
                          (r"pdf/(word|presentation|text|xlsx|html|xml)|file/pdf|pdfa", "conversia cere LibreOffice"),
                          (r"compress|vector", "cere Ghostscript și qpdf"), (r"svg|img", "cere ImageMagick")):
        if re.search(pattern, endpoint):
            return prog
    return "vezi Stirling → Setări → programe externe"


def store_certs() -> list:
    """Certificatele din Windows citite direct (instant), în forma în care le dă Stirling; alias = cum le numește Java."""
    ps = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8;"
          "@(Get-ChildItem Cert:\\CurrentUser\\My | Where-Object HasPrivateKey | ForEach-Object {"
          " $cn = $_.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false);"
          " [pscustomobject]@{ alias = $(if ($_.FriendlyName) { $_.FriendlyName } else { $cn }); subjectCommonName = $cn;"
          " notAfter = $_.NotAfter.ToUniversalTime().ToString('s') + 'Z'; expired = $_.NotAfter -lt (Get-Date) } }) | ConvertTo-Json -Compress")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=30,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    data = json.loads(r.stdout.decode("utf-8", "replace") or "[]")
    return data if isinstance(data, list) else [data]


def windows_certs() -> list:
    import requests
    port = Stirling.ensure()
    r = requests.get(f"http://127.0.0.1:{port}/api/v1/security/cert-sign/hardware/windows-certificates", timeout=60)
    r.raise_for_status()
    return r.json()


# ---------- semnături noi în bibliotecă ----------

def lib_file(f: str):
    """Fișierul de semnătură cerut, doar dacă e chiar în bibliotecă."""
    want = str(Path(f)).lower()
    return next((p for p in library(LIB) if str(p).lower() == want), None)


UPLOADS: dict = {}  # id -> {"orig": bytes, "ext": ".jpg", "png": Path}


def transparent_module():
    """Scriptul care face fundalul transparent (ca Adobe Fill & Sign): copia din skill-ul semnare-pdf, în bin/."""
    import signature_transparent
    return signature_transparent


def suggest_name(filename: str) -> str:
    stem = Path(filename or "").stem
    # Pozele din telefon / WhatsApp n-au în nume al cui e semnătura.
    if re.match(r"(?i)^(img|dsc|pxl|photo|image|screenshot|whatsapp|scan|captur)", stem):
        return ""
    stem = re.sub(r"(?i)^(semn[aă]tur[aă]|signature)[\s_-]*", "", stem)
    while True:
        shorter = re.sub(r"(?i)[\s_-]*(bg[\s_-]*removed|transparent|semn[aă]tur[aă]|signature|\.png)$", "", stem)
        if shorter == stem:
            break
        stem = shorter
    return re.sub(r"[_]+", " ", stem).strip()


def clean_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", name or "")
    name = re.sub(r"\s+", " ", name).strip().strip(".")
    return name[:80]


def process_upload(b: dict) -> dict:
    up = UPLOADS.get(b.get("id") or "")
    if not up:
        data = base64.b64decode(str(b["b64"]).split(",")[-1])
        ext = (Path(b.get("filename") or "").suffix or ".png").lower()
        up = {"orig": data, "ext": ext}
        uid = secrets.token_hex(6)
        UPLOADS[uid] = up
    else:
        uid = b["id"]
    folder = STATE / "upload"
    folder.mkdir(parents=True, exist_ok=True)
    src = folder / f"{uid}_src.png"
    dst = folder / f"{uid}.png"
    color = b.get("color") if b.get("color") in ("original", "blue", "black") else "original"
    strength = min(3.0, max(0.3, float(b.get("strength") or 1.0)))
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(up["orig"])))
    alpha = im.convert("RGBA").getchannel("A") if im.mode in ("RGBA", "LA", "P") else None
    if alpha is not None and alpha.getextrema()[0] < 200 and sum(alpha.histogram()[:64]) > 0.2 * im.width * im.height:
        # Poza are deja fundal transparent: doar o decupăm (și o recolorăm), fără scriptul lent.
        img = im.convert("RGBA")
        img = img.crop(alpha.getbbox() or (0, 0, img.width, img.height))
        if color != "original":
            ink = Image.new("RGBA", img.size, (26, 46, 140, 255) if color == "blue" else (0, 0, 0, 255))
            ink.putalpha(img.getchannel("A"))
            img = ink
        img.save(dst, optimize=True)
    else:
        # Scriptul skill-ului lucrează pixel cu pixel: o poză de telefon (12 MP) ar dura minute.
        # 1400 px pe latura lungă ajung pentru o semnătură de 4-5 cm tipărită la 300 dpi.
        im = im.convert("RGB")
        im.thumbnail((1400, 1400))
        im.save(src)
        try:
            img = transparent_module().process(str(src), str(dst), color, strength)
        except SystemExit:
            raise RuntimeError("Nu am găsit cerneală în poză. Mută „Curățare” spre „păstrează mai mult”.")
    up["png"] = dst
    return {"ok": True, "id": uid, "png": "data:image/png;base64," + fx_sign.b64(dst.read_bytes()),
            "w": img.size[0], "h": img.size[1], "name": suggest_name(b.get("filename") or "")}


def save_upload(b: dict) -> dict:
    up = UPLOADS.get(b.get("id") or "")
    if not up or not up.get("png"):
        raise RuntimeError("Încarcă întâi poza semnăturii.")
    name = clean_name(b.get("name") or "")
    if not name:
        raise RuntimeError("Scrie numele semnăturii (al cui e).")
    lib = Path(LIB)
    lib.mkdir(parents=True, exist_ok=True)
    target = lib / f"Semnatura {name}.png"
    if target.exists():
        if not b.get("replace"):
            return {"ok": False, "exists": True, "error": f"Există deja o semnătură „{name}”."}
        archive = lib / "_Arhiva"
        archive.mkdir(exist_ok=True)
        fx_sign.shutil.move(str(target), str(free_name(archive, f"Semnatura {name} (inlocuita {time.strftime('%Y-%m-%d')})", ".png")))
    fx_sign.shutil.copy2(up["png"], target)
    originals = lib / "Originale"
    originals.mkdir(exist_ok=True)
    free_name(originals, f"Semnatura {name}", up["ext"]).write_bytes(up["orig"])
    UPLOADS.pop(b["id"], None)
    i = next((k for k, s in enumerate(library(LIB)) if s.name.lower() == target.name.lower()), -1)
    event("library", file=str(target), name=name)
    return {"ok": True, "file": str(target), "name": name, "i": i}


# ---------- HTTP ----------

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def send(self, code, ctype, body: bytes, cache=False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=3600" if cache else "no-store")
        self.end_headers()
        self.wfile.write(body)

    def json(self, obj, code=200):
        self.send(code, "application/json; charset=utf-8", json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def query(self):
        u = urllib.parse.urlparse(self.path)
        return u.path, {k: v[-1] for k, v in urllib.parse.parse_qs(u.query).items()}

    def authorized(self, q) -> bool:
        if q.get("t") == TOKEN or self.headers.get("X-Token") == TOKEN:
            return True
        self.json({"ok": False, "error": "token greșit"}, 403)
        return False

    def body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        path, q = self.query()
        try:
            if path in ("/", "/index.html"):
                return self.send(200, "text/html; charset=utf-8", (EDITOR_DIR / "index.html").read_bytes())
            if path.startswith("/editor/"):
                f = (EDITOR_DIR / path[len("/editor/"):]).resolve()
                if EDITOR_DIR.resolve() in f.parents and f.is_file():
                    ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
                    if ctype.startswith("text/") or ctype.endswith("javascript"):
                        ctype += "; charset=utf-8"
                    return self.send(200, ctype, f.read_bytes())
                return self.send(404, "text/plain", b"")
            if not path.startswith("/api/") or not self.authorized(q):
                return None if path.startswith("/api/") else self.send(404, "text/plain", b"")
            if path == "/api/doc":
                return self.json(doc_info(q["path"]))
            if path == "/api/page":
                return self.send(200, "image/png", page_png(q["path"], int(q["n"]), int(q.get("w", 1600))), cache=True)
            if path == "/api/runs":
                return self.json(page_runs(q["path"], int(q["n"])))
            if path == "/api/fields":
                with LOCK:
                    return self.json(fx_sign.form_fields(open_doc(q["path"])[int(q["n"]) - 1]))
            if path == "/api/certs":
                import certsign
                return self.json(certsign.list_certs())
            if path == "/api/font":
                data, ctype = font_bytes(q["path"], q["ref"])
                return self.send(200, ctype, data, cache=True) if data else self.send(404, "text/plain", b"")
            if path == "/api/lib":
                items = []
                for i, s in enumerate(library(LIB)):
                    try:
                        px = fitz.Pixmap(str(s))
                        ratio = px.height / px.width
                    except Exception:
                        ratio = 0.4
                    items.append({"i": i, "name": label_of(s), "file": str(s), "ratio": ratio})
                return self.json(items)
            if path == "/api/sig":
                lib = library(LIB)
                f = lib_file(q["f"]) if "f" in q else lib[int(q["i"])]
                return self.send(200, "image/png", f.read_bytes(), cache=True) if f else self.send(404, "text/plain", b"")
            if path == "/api/comments":
                return self.json(load_comments(q["path"]))
            if path == "/api/capture":
                c = next((c for c in load_comments(q["path"]) if c["id"] == q["id"]), None)
                f = Path(c["capture"]) if c and c.get("capture") else None
                if f and f.is_file() and (STATE / "captures").resolve() in f.resolve().parents:
                    return self.send(200, "image/png", f.read_bytes(), cache=True)
                return self.send(404, "text/plain", b"")
            if path == "/api/stirling/tools":
                return self.json(Stirling.tools())
            if path == "/api/stirling/certs":
                return self.json(store_certs() if q.get("quick") else windows_certs())
            if path == "/api/info":
                import desktop
                info = {"ok": True, "standalone": STANDALONE, "lang": desktop.settings().get("lang", "ro"), "library": LIB,
                        "stirling": bool(Stirling.install_dir())}
                if STANDALONE:
                    info.update(apps=desktop.APPS, ai=desktop.current_ai())
                return self.json(info)
            return self.json({"ok": False, "error": "necunoscut"}, 404)
        except Exception as err:
            traceback.print_exc(file=sys.stderr)
            return self.json({"ok": False, "error": f"{type(err).__name__}: {err}"}, 500)

    def do_POST(self):
        global LIB
        path, q = self.query()
        if not self.authorized(q):
            return None
        try:
            b = self.body()
            if path == "/api/save":
                with LOCK:
                    src = Path(b["path"])
                    items = b.get("items") or []
                    lib = library(LIB)
                    for it in items:  # semnătura vine ca fișier din bibliotecă; stamp vrea poziția ei
                        if it.get("type") == "sig" and not isinstance(it.get("sig"), int):
                            f = lib_file(str(it["sig"]))
                            if not f:
                                raise ValueError(f"Semnătura nu mai e în bibliotecă: {it['sig']}")
                            it["sig"] = lib.index(f)
                    rot = b.get("rotate")  # {pages, angle}: se aplică după elemente
                    target = stamp(src, items, lib, rotate=rot)
                    _docs.pop(str(target).lower(), None)
                sigs = list(dict.fromkeys(label_of(library(LIB)[int(it["sig"])]) for it in items if it.get("type") == "sig"))
                res = {"ok": True, "out": str(target), "sigs": sigs,
                       "texts": sum(1 for it in items if it.get("type") == "text"),
                       "edits": sum(1 for it in items if it.get("type") == "edit"),
                       "rotated": len(rot["pages"]) if rot else 0,
                       "page": int(items[0]["page"]) if items else int(rot["pages"][0]) if rot else 1}
                event("saved", source=str(src), **{k: v for k, v in res.items() if k != "ok"})
                return self.json(res)
            if path == "/api/organize":
                # Ecranul „Organizează paginile”: ordinea nouă, paginile șterse și rotite, scrise o dată.
                with LOCK:
                    src = Path(b["path"])
                    target = fx_sign.organize(src, b.get("pages") or [])
                    _docs.pop(str(target).lower(), None)
                res = {"ok": True, "out": str(target), "sigs": [], "texts": 0, "edits": 0, "rotated": 0, "page": 1,
                       "pages": len(b["pages"])}
                event("saved", source=str(src), **{k: v for k, v in res.items() if k != "ok"})
                return self.json(res)
            if path == "/api/undo":
                with LOCK:
                    res = undo_file(b["path"])
                    _docs.pop(str(Path(b["path"])).lower(), None)
                if res.get("ok"):
                    event("undone", path=b["path"], **{k: v for k, v in res.items() if k != "ok"})
                return self.json(res)
            if path == "/api/comment":
                src = b["path"]
                n = int(b["page"])
                c = {"id": secrets.token_hex(4), "page": n, "kind": b.get("kind", "point"), "text": b.get("text", "").strip(),
                     "send": bool(b.get("send", True)), "created": time.strftime("%Y-%m-%d %H:%M")}
                if c["kind"] == "region":
                    c["rect"] = [float(v) for v in b["rect"]]
                    c["context"] = region_text(src, n, c["rect"])
                    c["capture"] = capture(src, n, c["rect"])
                else:
                    c["x"], c["y"] = float(b["x"]), float(b["y"])
                    c["context"] = near_text(src, n, c["x"], c["y"])
                items = load_comments(src)
                c["number"] = max([it.get("number", 0) for it in items] + [0]) + 1
                items.append(c)
                save_comments(src, items)
                res = {"ok": True, "comment": c}
                if c["send"]:
                    event("comment", path=str(Path(src)), **c)
                    res.update(send_ai(b.get("ai"), c, src, items))
                return self.json(res)
            if path == "/api/comment/delete":
                items = [c for c in load_comments(b["path"]) if c["id"] != b["id"]]
                save_comments(b["path"], items)
                return self.json({"ok": True})
            if path == "/api/comment/send":
                items = load_comments(b["path"])
                res = {"ok": True}
                for c in items:
                    if c["id"] == b["id"]:
                        c["send"] = True
                        event("comment", path=str(Path(b["path"])), **c)
                        res.update(send_ai(b.get("ai"), c, b["path"], items))
                        res["comment"] = c
                save_comments(b["path"], items)
                return self.json(res)
            if path == "/api/pick":
                import desktop
                p = desktop.pick_pdf(str(Path(b["dir"])) if b.get("dir") else "")
                return self.json({"ok": True, "path": p})
            if path == "/api/pickmany":
                import desktop
                return self.json({"ok": True, "paths": desktop.pick_pdfs(str(Path(b["dir"])) if b.get("dir") else "", b.get("kind") or "pdf")})
            if path == "/api/local":
                # Uneltele făcute în aplicație (bin/localtools.py), fără Stirling.
                import localtools
                with LOCK:
                    res = localtools.run(b["tool"], b.get("path") or "", b.get("fields") or {})
                if res.get("out") and res.get("kind") in ("pdf", "file", "folder"):
                    event("tool", source=b.get("path") or "", out=res["out"], tool=b.get("label") or b["tool"], kind=res["kind"])
                return self.json(res)
            if path == "/api/certsign":
                # Un fișier sau mai multe (semnarea în bloc), cu o singură deschidere a cheii: PIN-ul o dată.
                import certsign
                certsign.FITZ_LOCK = LOCK
                items = b.get("items") or [{"path": b["path"], "place": b.get("place")}]
                results = certsign.sign_many(b["thumb"], items, b.get("reason") or "", b.get("location") or "")
                for r in results:
                    if r.get("ok"):
                        event("tool", source=r["path"], out=r["out"], tool="Semnătură electronică", kind="pdf")
                return self.json({"ok": True, "results": results})
            if path == "/api/attachment":
                out_path = save_attachment(b["path"], b["key"])
                if b.get("how") == "open":
                    os.startfile(out_path)  # noqa: S606 - XML-ul se deschide cu aplicația lui
                else:
                    subprocess.Popen(["explorer.exe", f"/select,{out_path}"])
                return self.json({"ok": True, "out": out_path})
            if path == "/api/library":
                import desktop
                folder = os.path.expandvars(str(b.get("path", "")).strip().strip('"'))
                if not folder or not os.path.isdir(folder):
                    return self.json({"ok": False, "error": "Folderul nu există."}, 400)
                desktop.save_settings(library=folder)
                LIB = folder
                return self.json({"ok": True, "library": LIB, "count": len(library(LIB))})
            if path == "/api/settings":
                import desktop
                desktop.save_settings(**{k: v for k, v in b.items() if k in ("ai", "lang")})
                return self.json({"ok": True})
            if path == "/api/ping":
                if STANDALONE:
                    CLIENTS[str(b.get("id"))] = time.time()
                return self.json({"ok": True})
            if path == "/api/bye":
                CLIENTS.pop(str(b.get("id")), None)
                return self.json({"ok": True})
            if path == "/api/stirling/run":
                res = run_tool(b)
                if res.get("out"):
                    event("tool", source=b["path"], out=res["out"], tool=b.get("label", b["endpoint"]), kind=res["kind"])
                return self.json(res)
            if path == "/api/lib/process":
                return self.json(process_upload(b))
            if path == "/api/lib/save":
                res = save_upload(b)
                return self.json(res, 200 if res.get("ok") else 409)
            if path == "/api/open":
                p = b["path"]
                if b.get("how") == "explorer":
                    subprocess.Popen(["explorer.exe", f"/select,{p}"] if os.path.isfile(p) else ["explorer.exe", p])
                else:
                    os.startfile(p)  # noqa: S606 - deschide fișierul cu aplicația lui
                return self.json({"ok": True})
            return self.json({"ok": False, "error": "necunoscut"}, 404)
        except Exception as err:
            traceback.print_exc(file=sys.stderr)
            return self.json({"ok": False, "error": f"{err}"}, 500)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def send_ai(app, c: dict, path: str, items: list) -> dict:
    """În aplicația separată comentariul pleacă la aplicația AI aleasă; în mod îl preia mod-ul (evenimentul)."""
    if not STANDALONE:
        return {}
    import desktop
    try:
        sent = desktop.send(app, c, str(Path(path)))
    except Exception as err:
        traceback.print_exc(file=sys.stderr)
        return {"sendError": f"Nu am putut trimite: {err}"}
    c["sentTo"] = sent["name"]
    save_comments(path, items)
    return {"sent": sent}


def watchdog(srv):
    """Aplicația separată se oprește când nu mai e deschisă nicio fereastră a editorului."""
    seen = False
    empty_since = None
    last = time.time()
    while True:
        time.sleep(2)
        now = time.time()
        if now - last > 30:  # calculatorul a dormit: ferestrele n-au avut cum să dea semn
            for k in list(CLIENTS):
                CLIENTS[k] = now
        last = now
        # Ferestrele minimizate primesc timere o dată pe minut, de aici marja mare.
        for k, t in list(CLIENTS.items()):
            if now - t > 150:
                CLIENTS.pop(k, None)
        if CLIENTS:
            seen, empty_since = True, None
            continue
        empty_since = empty_since or now
        # Prima fereastră are timp să se încarce; după închidere, câteva secunde pentru un reload.
        if now - empty_since > (6 if seen else 90):
            srv.shutdown()
            return


def make_server(lib: str, standalone: bool = False):
    global LIB, STANDALONE
    LIB = lib
    STANDALONE = standalone
    return Server(("127.0.0.1", int(os.environ.get("FX_PORT", "0"))), Handler)


def run(srv):
    if STANDALONE:
        threading.Thread(target=watchdog, args=(srv,), daemon=True).start()
    Stirling.warm()
    try:
        srv.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass


def serve(lib: str):
    srv = make_server(lib)
    event("ready", port=srv.server_address[1], token=TOKEN)
    run(srv)
