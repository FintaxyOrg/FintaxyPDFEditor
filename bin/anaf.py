"""Validare și semnare declarații ANAF (D100, D112, D300, D390, D394...), cu validatoarele oficiale ale ANAF.

ANAF publică DUKIntegrator („soft J”, sursele sub AGPL-3.0): un program Java care validează XML-ul unei declarații și
face PDF-ul cu XML-ul atașat. Pentru fiecare declarație are două fișiere: `DnnnValidator.jar` și `DnnnPdf.jar`, iar
lista lor, cu versiuni și adrese, e în `versiuni.xml` de pe static.anaf.ro.

Aici:
- validatoarele se aduc singure, de la ANAF, în folderul aplicației (`components/anaf`), fără administrator și fără
  terminal; noi nu le redistribuim. La folosire, cel mult o dată pe zi, aplicația citește `versiuni.xml` și își
  actualizează singură ce s-a schimbat;
- Java e cel din Stirling PDF (adus oricum de aplicație); dacă lipsește, se aduce un Java mic (vezi deps.py);
- DUKIntegrator rulează în linie de comandă, fără interfață, pe o copie a fișierului (scrie fișiere lângă intrare);
- semnătura o pune `certsign.py`, cu certificatul din Windows; PDF-ul semnat e verificat din nou cu DUKIntegrator.

La teste: FX_ANAF_URL = alt `versiuni.xml` (un server local), FX_ANAF_JAVA = comanda care ține loc de Java (JSON).
"""
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import fitz

import deps

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
HOME = deps.COMP / "anaf"
VERSIONS_URL = os.environ.get("FX_ANAF_URL") or "https://static.anaf.ro/static/10/Anaf/update5/versiuni.xml"
HOSTS = {"static.anaf.ro", urlparse(VERSIONS_URL).hostname}
CHECK_EVERY = 24 * 3600
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._\-]{0,80}")  # nume de fișier din lista ANAF
SAFE_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_]{1,15}")  # cod de declarație: D300, D112, A4200…
RETRY_WAIT = (1, 3)  # secunde între încercările unei descărcări (trei încercări în total)

# Numele celor mai folosite declarații; restul apar doar cu codul.
NAMES = {
    "D100": "Obligații de plată la bugetul de stat", "D101": "Impozit pe profit", "D112": "Contribuții sociale și impozit pe salarii",
    "D205": "Impozit reținut la sursă", "D207": "Impozit reținut nerezidenților", "D300": "Decont de TVA", "D301": "Decont special de TVA",
    "D390": "Recapitulativă intracomunitară", "D394": "Livrări și achiziții pe teritoriul național", "D406": "SAF-T",
    "D710": "Declarație rectificativă", "D212": "Declarația unică",
}
# Spațiul de nume din XML care nu poartă codul declarației.
SPECIAL = {"declaratie_unica": "D112", "declaratieunica": "D112"}

JOB = {"state": "", "line": ""}  # ce face acum, pentru editor
_LOCK = threading.Lock()  # o singură rulare o dată: Java ține jar-urile deschise cât rulează


class AnafError(RuntimeError):
    pass


def _say(line: str):
    JOB.update(state="running", line=line)


# ---------------------------------------------------------------- versiunile publicate de ANAF

def _state() -> dict:
    try:
        return json.loads((HOME / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(st: dict):
    HOME.mkdir(parents=True, exist_ok=True)
    tmp = HOME / "state.json.tmp"
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, HOME / "state.json")


def _url(u: str) -> str:
    """Adresele din versiuni.xml sunt http://; le luăm prin https și doar de la ANAF."""
    u = u.strip()
    host = urlparse(u).hostname
    if host not in HOSTS:
        raise AnafError(f"Adresă neașteptată în lista ANAF: {u[:80]}")
    return "https://" + u[7:] if u.startswith("http://") and host == "static.anaf.ro" else u


def parse_versions(text: str) -> dict:
    """versiuni.xml -> {"integrator": versiune, "base": [(adresă, loc în folder)], "decl": {cod: {J, P, jurl, purl}}}."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    m = re.search(r"<integrator>(.*?)</integrator>", text, re.S)
    if not m:
        raise AnafError("Lista de versiuni de la ANAF nu are forma așteptată.")
    head = m.group(1)
    ver = re.search(r"<versiune>\s*(.*?)\s*</versiune>", head, re.S)
    base = []
    for tag, where in (("iJars", "lib"), ("sJars", "lib"), ("zJars", ""), ("cFisiere", "config")):
        block = re.search(rf"<{tag}>(.*?)</{tag}>", head, re.S)
        for u in re.findall(r"<(?:jarURL|fisierURL)>\s*(.*?)\s*</(?:jarURL|fisierURL)>", block.group(1) if block else "", re.S):
            name = u.rsplit("/", 1)[-1]
            if where == "" and not name.lower().endswith(".jar"):
                continue  # ajutor.chm: doar pentru interfața lor
            if not SAFE_NAME.fullmatch(name):  # numele ajunge nume de fișier în folderul aplicației
                raise AnafError(f"Nume de fișier neașteptat în lista ANAF: {name[:60]}")
            base.append([_url(u), f"{where}/{name}" if where else name])
    decl = {}
    for code, j, p, jurl, purl in re.findall(
            r"<(\w+)>\s*<versiuneJ>\s*(.*?)\s*</versiuneJ>\s*<versiuneP>\s*(.*?)\s*</versiuneP>\s*<JURL>\s*(.*?)\s*</JURL>\s*<PURL>\s*(.*?)\s*</PURL>",
            text, re.S):
        decl[code] = {"J": j, "P": p, "jurl": _url(jurl), "purl": _url(purl)}
    if not base or not decl:
        raise AnafError("Lista de versiuni de la ANAF nu are forma așteptată.")
    return {"integrator": ver.group(1) if ver else "", "base": base, "decl": decl}


def versions(force: bool = False) -> dict:
    """Lista ANAF, citită de pe site cel mult o dată pe zi; între timp (sau fără internet), copia ținută în folder."""
    st = _state()
    cache = HOME / "versiuni.xml"
    fresh = cache.is_file() and time.time() - float(st.get("checked") or 0) < CHECK_EVERY
    if fresh and not force:
        try:
            return {**parse_versions(cache.read_text(encoding="utf-8", errors="replace")), "checked": st.get("checked"), "online": True}
        except AnafError:
            pass
    import requests
    _say("Verific versiunile publicate de ANAF…")
    try:
        r = requests.get(VERSIONS_URL, timeout=(15, 40))
        r.raise_for_status()
        if urlparse(r.url).hostname not in HOSTS:
            raise AnafError("Lista de versiuni a fost trimisă în afara site-ului ANAF.")
        v = parse_versions(r.content.decode("utf-8", "replace"))
    except Exception as err:
        if cache.is_file():  # fără internet: mergem cu ce avem
            v = parse_versions(cache.read_text(encoding="utf-8", errors="replace"))
            return {**v, "checked": st.get("checked"), "online": False}
        if isinstance(err, AnafError):
            raise
        raise AnafError("Nu am putut lua lista validatoarelor de la ANAF (fără internet?). Încearcă din nou.") from None
    HOME.mkdir(parents=True, exist_ok=True)
    tmp = HOME / "versiuni.xml.tmp"
    tmp.write_bytes(r.content)
    os.replace(tmp, cache)
    st = _state()
    st["checked"] = time.time()
    _save_state(st)
    return {**v, "checked": st["checked"], "online": True}


def _fetch(url: str, target: Path, label: str):
    """Descarcă un fișier de la ANAF. O întrerupere de moment nu oprește validarea: încearcă de trei ori."""
    for n, wait in enumerate((*RETRY_WAIT, None)):
        try:
            return _fetch_once(url, target, label)
        except AnafError:
            if wait is None:
                raise
            _say(f"Descărcarea s-a întrerupt ({label}); încerc din nou ({n + 2} din {len(RETRY_WAIT) + 1})…")
            time.sleep(wait)


def _fetch_once(url: str, target: Path, label: str):
    import requests
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    try:
        # fără comprimare pe drum: mărimea primită trebuie să fie cea anunțată
        with requests.get(url, stream=True, timeout=(20, 60), headers={"Accept-Encoding": "identity"}) as r:
            r.raise_for_status()
            if urlparse(r.url).hostname not in HOSTS:  # o redirecționare ne-a scos de pe site-ul ANAF
                raise AnafError(f"Descărcarea a fost trimisă în afara site-ului ANAF ({label}).")
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            with open(part, "wb") as f:
                for chunk in r.iter_content(1 << 17):
                    f.write(chunk)
                    done += len(chunk)
                    if total > (1 << 20):
                        _say(f"Se descarcă {label}… {done // 1048576} din {total // 1048576} MB")
        size = part.stat().st_size
        if not size or (total and size != total):
            raise AnafError(f"Descărcarea s-a întrerupt ({label}). Încearcă din nou.")
        if target.suffix.lower() == ".jar" and part.read_bytes()[:2] != b"PK":
            raise AnafError(f"Fișierul primit de la ANAF nu e cel așteptat ({label}).")
        os.replace(part, target)
    except AnafError:
        part.unlink(missing_ok=True)
        raise
    except Exception:
        part.unlink(missing_ok=True)
        raise AnafError(f"Nu am putut descărca de la ANAF ({label}). Verifică internetul și încearcă din nou.") from None


def ensure(code: str, v: dict | None = None) -> list:
    """Aduce sau actualizează programul de bază și validatorul unei declarații. Întoarce ce s-a schimbat, pe scurt."""
    v = v or versions()
    if code not in v["decl"] or not SAFE_CODE.fullmatch(code):
        raise AnafError(f"ANAF nu are validator pentru „{code[:20]}”.")
    st = _state()
    changed = []
    base_ok = st.get("integrator") == v["integrator"] and st.get("base") == v["base"] and all((HOME / rel).is_file() for _u, rel in v["base"])
    if not base_ok:
        if not v.get("online", True) and not st.get("integrator"):
            raise AnafError("Validatoarele ANAF nu sunt încă aduse și nu am internet. Încearcă din nou când ai internet.")
        _say("Se aduce programul de validare al ANAF…")
        for u, rel in v["base"]:
            _fetch(u, HOME / rel, "programul de validare")
        changed.append(f"program {st.get('integrator') or 'nou'} → {v['integrator']}" if st.get("integrator") != v["integrator"] else "program")
        st.update(integrator=v["integrator"], base=v["base"])
        _save_state(st)
    want = v["decl"][code]
    have = (st.get("decl") or {}).get(code) or {}
    files_ok = (HOME / "lib" / f"{code}Validator.jar").is_file() and (HOME / "lib" / f"{code}Pdf.jar").is_file()
    if not files_ok or any(have.get(k) != want[k] for k in ("J", "P", "jurl", "purl")):
        _say(f"Se aduce validatorul {code} de la ANAF…")
        _fetch(want["jurl"], HOME / "lib" / f"{code}Validator.jar", f"validatorul {code}")
        _fetch(want["purl"], HOME / "lib" / f"{code}Pdf.jar", f"validatorul {code}")
        changed.append(f"{code} {have['J']} → {want['J']}" if have.get("J") and have["J"] != want["J"] else f"{code} {want['J']}")
        st = _state()
        st.setdefault("decl", {})[code] = {**want, "at": time.time()}
        _save_state(st)
    return changed


# ---------------------------------------------------------------- Java

def java_cmd() -> list:
    fake = os.environ.get("FX_ANAF_JAVA")
    if fake:
        return json.loads(fake)
    exe = deps.java()
    if exe:
        return [exe]
    # Stirling (cu Java în pachet) încă se descarcă? Atunci îl așteptăm pe el; altfel aducem un Java mic.
    j = deps.job("stirling") or {}
    if j.get("state") in ("running", "waiting"):
        raise AnafError("Java, de care au nevoie validatoarele ANAF, se aduce acum împreună cu Stirling PDF. Încearcă din nou în câteva minute.")
    _say("Se aduce Java (o singură dată, ~50 MB)…")
    r = deps.provision("java")
    exe = deps.java()
    if not exe:
        raise AnafError(r.get("line") or "Nu am putut aduce Java. Încearcă din nou.")
    return [exe]


def _duk(args: list, timeout: int = 900) -> str:
    cmd = java_cmd() + ["-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dsun.stdout.encoding=UTF-8", "-Djava.awt.headless=true",
                        "-jar", "DUKIntegrator.jar"] + args
    try:
        r = subprocess.run(cmd, cwd=HOME, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise AnafError("Validatorul ANAF nu a răspuns la timp.") from None
    except OSError as err:
        raise AnafError(f"Java nu a pornit: {err}") from None
    out = r.stdout.decode("utf-8", "replace").replace("\r", "")
    if not out.strip():
        err = r.stderr.decode("utf-8", "replace").strip().splitlines()
        raise AnafError("Validatorul ANAF nu a răspuns" + (f": {err[-1][:200]}" if err else "."))
    return out


# ---------------------------------------------------------------- ce declarație e

def _xml_root(data: bytes):
    """(spațiul de nume, numele elementului rădăcină), chiar dacă fișierul e stricat mai jos."""
    try:
        import io
        for _ev, el in ET.iterparse(io.BytesIO(data), events=("start",)):
            m = re.match(r"\{(.*?)\}(.*)", el.tag)
            return (m.group(1), m.group(2)) if m else ("", el.tag)
    except ET.ParseError:
        pass
    head = data[:4000].decode("utf-8", "replace")
    m = re.search(r"<([A-Za-z_][\w.\-]*)[\s>]", re.sub(r"<\?.*?\?>|<!--.*?-->", "", head, flags=re.S))
    ns = re.search(r'xmlns="([^"]*)"', head)
    return (ns.group(1) if ns else "", m.group(1) if m else "")


def detect(data: bytes, filename: str = "", known=()) -> str:
    """Codul declarației (D300, D112...) după XML: spațiul de nume, elementul rădăcină, apoi numele fișierului."""
    by_low = {k.lower(): k for k in known}
    ns, root = _xml_root(data)

    def ok(c: str) -> str:
        c = SPECIAL.get(c.lower(), c)
        if not known:
            return c.upper() if re.fullmatch(r"[A-Za-z]\d{1,4}\w?", c) else ""
        return by_low.get(c.lower(), "")
    m = re.search(r"mfp:anaf:dgti:([^:]+):", ns)
    cands = [m.group(1)] if m else []
    cands.append(root)
    m = re.fullmatch(r"declaratie_?(\d+\w*)", root, re.I)
    if m:
        cands.append("D" + m.group(1))
    m = re.match(r"([A-Za-z]\d{3,4}[A-Za-z]?)(?=[_\-. ]|$)", filename)
    if m:
        cands.append(m.group(1))
    return next((c for c in map(ok, cands) if c), "")


# ---------------------------------------------------------------- rezultatul, pe înțeles

CODES = {
    "-5": "Fișierul nu e un XML întreg: e gol, tăiat sau nu e XML. Exportă-l din nou din programul de contabilitate.",
    "-3": "Validatorul ANAF a dat o eroare tehnică la acest fișier.",
    "-6": "Validatorul acestei declarații nu a putut fi încărcat. Încearcă din nou (se descarcă iar).",
    "-7": "Validatorul acestei declarații nu a putut fi pornit.",
    "-8": "Validatorul nu cunoaște acest tip de declarație.",
    "-9": "Validatorul ANAF s-a oprit neașteptat la acest fișier.",
}
HINTS = [
    (r"namespace .*lips[aă] sau incorect", "XML-ul e făcut pentru altă versiune a formularului decât cea cerută de ANAF pentru perioada din el. "
                                           "Actualizează programul de contabilitate și exportă din nou (sau verifică luna și anul)."),
    (r"\b(CUI|CIF|cif|cui)\b.*invalid", "Codul fiscal nu trece verificarea cifrei de control. Verifică CUI-ul scris în declarație."),
    (r"nu respect[aă] algoritmul", "Un cod de TVA al unui partener nu e valid pentru țara lui (nu trece verificarea cifrei de control)."),
    (r"\bCNP\b.*(invalid|incorect|eronat)", "Un CNP nu trece verificarea cifrei de control."),
    (r"\bIBAN\b.*(invalid|incorect|eronat)", "Un cont IBAN nu e valid."),
    (r"eroare structur[aă]", "Fișierul nu respectă structura cerută de ANAF: lipsește un câmp obligatoriu sau are unul în plus."),
    (r"eroare atribut: *([\w.]+)", "Câmpul „{0}” are o valoare pe care ANAF nu o acceptă."),
]


def hint(text: str) -> str:
    for pat, h in HINTS:
        m = re.search(pat, text)
        if m:
            return h.format(*m.groups()) if m.groups() else h
    return ""


def parse_errors(text: str) -> list:
    """Fișierul de erori al DUKIntegrator -> [{level: error | warning, section, lines, hint}].
    Forma lui: un rând „E: secțiunea” (F = structură, A/W = atenționare), apoi rândurile indentate ale mesajului."""
    items = []
    cur = None
    for raw in text.replace("\r", "").split("\n"):
        line = raw.strip()
        if not line or line == "ok":
            continue
        m = re.match(r"([A-Z]): ?(.*)$", raw)
        if m and not raw.startswith(" "):
            cur = {"level": "warning" if m.group(1) in "AW" else "error", "kind": m.group(1), "section": m.group(2).strip(), "lines": []}
            items.append(cur)
            continue
        if cur is None:
            cur = {"level": "error", "kind": "", "section": "", "lines": []}
            items.append(cur)
        cur["lines"].append(line)
    for it in items:
        it["hint"] = hint(" ".join(it["lines"]))
    return items


def _read(p: Path) -> str:
    if not p.is_file():
        return ""
    b = p.read_bytes()
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp1250", "replace")


def _verdict(out: str, err_text: str) -> dict:
    """Din ce a scris DUKIntegrator: status (ok | warnings | errors | fatal), mesajele și, dacă e cazul, eroarea de PDF."""
    res = {"status": "ok", "messages": [], "note": ""}
    m = re.search(r"cod eroare=(-?\d+)", out)
    if m:
        res.update(status="fatal", note=CODES.get(m.group(1), f"Validatorul ANAF a dat codul de eroare {m.group(1)}."))
    elif "Tip declaratie necunoscut" in out:
        res.update(status="fatal", note=CODES["-8"])
    elif "Perioada raportare eronata" in out:
        res.update(status="fatal", note="Perioada de raportare din fișier (luna / anul) nu e acceptată de validatorul acestei declarații.")
    elif "Erori la validare fisier" in out:
        res.update(status="errors", messages=parse_errors(err_text))
    elif "Atentionari la validare fisier" in out:
        res.update(status="warnings", messages=[{**i, "level": "warning"} for i in parse_errors(err_text)])
    elif "Validare fara erori fisier" not in out:
        res.update(status="fatal", note=out.strip()[-300:])
    m = re.search(r"Eroare creare PDF!\s*\n\s*(.*)", out)
    if m:
        res["pdfError"] = m.group(1).strip()
    return res


# ---------------------------------------------------------------- validare, PDF, verificarea PDF-ului semnat

def xml_of_pdf(pdf: Path):
    """XML-ul atașat unui PDF de declarație (PDF inteligent ANAF sau făcut de DUKIntegrator): (nume, conținut)."""
    with fitz.open(str(pdf)) as doc:
        if doc.needs_pass:
            raise AnafError("PDF-ul are parolă.")
        for key in doc.embfile_names():
            info = doc.embfile_info(key)
            name = info.get("filename") or info.get("ufilename") or key
            if name.lower().endswith(".xml") or key.lower() in ("xml",):
                return name if name.lower().endswith(".xml") else name + ".xml", doc.embfile_get(key)
    raise AnafError("PDF-ul nu are un XML atașat: nu e o declarație ANAF completată și validată.")


def _made_by_duk(pdf: Path) -> bool:
    """PDF făcut mai devreme tot de validatorul ANAF (îl putem înlocui cu cel nou)?"""
    try:
        with fitz.open(str(pdf)) as doc:
            return (doc.metadata.get("producer") or "").startswith("iText") and bool(doc.embfile_names()) and not doc.get_sigflags() == 3
    except Exception:
        return False


def _workdir() -> Path:
    w = HOME / "work" / uuid.uuid4().hex[:12]
    w.mkdir(parents=True)
    return w


def _clean_old_work():
    try:
        for d in (HOME / "work").iterdir():
            if time.time() - d.stat().st_mtime > 3600:
                shutil.rmtree(d, ignore_errors=True)
    except OSError:
        pass


def process(path: str, decl: str = "", make_pdf: bool = True, option: int = 0) -> dict:
    """Validează o declarație (XML sau PDF cu XML atașat) și, pentru un XML fără erori, face PDF-ul lângă el.

    Întoarce: decl, source (xml | pdf), status (ok | warnings | errors | fatal), messages, note,
    pdf (PDF-ul făcut, dacă e), sign ({"path", "place"}: ce se semnează), versions, updated."""
    src = Path(path)
    if not src.is_file():
        raise AnafError("Fișierul nu mai există.")
    is_pdf = src.suffix.lower() == ".pdf"
    with _LOCK:
        JOB.update(state="running", line="Se pregătește…")
        work = None
        try:
            name, data = xml_of_pdf(src) if is_pdf else (src.name, src.read_bytes())
            v = versions()
            code = decl or detect(data, name, v["decl"].keys()) or (detect(b"", src.name, v["decl"].keys()) if is_pdf else "")
            if not code:
                return {"ok": True, "status": "unknown", "source": "pdf" if is_pdf else "xml", "types": types(v),
                        "note": "Nu mi-am dat seama ce declarație e. Alege tipul din listă."}
            updated = ensure(code, v)
            _clean_old_work()
            work = _workdir()
            rel = f"work/{work.name}"
            (work / "declaratie.xml").write_bytes(data)
            _say(f"Validez {code} cu validatorul ANAF…")
            want_pdf = make_pdf and not is_pdf
            if want_pdf:
                out = _duk(["-p", code, f"{rel}/declaratie.xml", f"+{rel}/erori.txt", str(int(option)), "0", f"{rel}/declaratie.pdf"])
            else:
                out = _duk(["-v", code, f"{rel}/declaratie.xml", f"{rel}/erori.txt", str(int(option))])
            res = _verdict(out, _read(work / "erori.txt"))
            st = (_state().get("decl") or {}).get(code) or {}
            res.update(ok=True, decl=code, name=NAMES.get(code, ""), source="pdf" if is_pdf else "xml", file=src.name,
                       versions={"J": st.get("J", ""), "P": st.get("P", ""), "integrator": _state().get("integrator", "")},
                       updated=updated, online=v.get("online", True), pdf="", sign=None)
            good = res["status"] in ("ok", "warnings")
            if good and is_pdf:
                res["sign"] = {"path": str(src), "place": "auto"}
            elif good and want_pdf:
                made = work / "declaratie.pdf"
                if not made.is_file() or res.get("pdfError"):
                    res["note"] = "Declarația e validă, dar PDF-ul nu a putut fi făcut" + (f": {res['pdfError']}" if res.get("pdfError") else ".")
                else:
                    import localtools
                    target = src.with_suffix(".pdf")
                    if target.exists() and not _made_by_duk(target):
                        target = localtools.free_name(src.parent, src.stem, ".pdf")
                    tmp = target.with_name(f".{target.stem}.tmp.pdf")
                    shutil.copyfile(made, tmp)
                    os.replace(tmp, target)
                    res["pdf"] = str(target)
                    res["sign"] = {"path": str(target), "place": None}
            return res
        finally:
            if work is not None:
                shutil.rmtree(work, ignore_errors=True)  # copia declarației nu rămâne în folderul aplicației
            JOB.update(state="", line="")


def verify_signed(path: str, decl: str) -> dict:
    """Verifică PDF-ul semnat cu DUKIntegrator (structură, atașament, semnătură, XML, metadate față de XML).
    Are rost doar pentru PDF-urile făcute de el: pe PDF-urile inteligente noi verificarea lui de PDF dă erori false."""
    src = Path(path)
    if not src.is_file():
        raise AnafError("Fișierul nu mai există.")
    if not SAFE_CODE.fullmatch(decl or "") or not (HOME / "lib" / f"{decl}Validator.jar").is_file():
        raise AnafError("Tipul declarației nu e unul validat mai devreme.")
    with _LOCK:
        JOB.update(state="running", line="Verific PDF-ul semnat cu validatorul ANAF…")
        work = _workdir()
        try:
            shutil.copyfile(src, work / "semnat.pdf")
            out = _duk(["-v", decl, f"work/{work.name}/semnat.pdf", f"work/{work.name}/erori.txt"])
        finally:
            shutil.rmtree(work, ignore_errors=True)
            JOB.update(state="", line="")
    lines = [ln.strip() for ln in out.split("\n") if ln.strip()]
    sig_err = next((ln for ln in lines if ln.startswith("Eroare semnatura PDF")), "")
    problems = [ln for ln in lines if ln.startswith(("Eroare", "Erori", "Tipul declaratiei")) and ln != sig_err]
    unsigned = any("nu este semnat" in ln for ln in lines)
    if "NoSuchAlgorithmException" in sig_err:
        # Biblioteca din 2010 a validatorului nu știe cheile ECDSA (buletinul electronic): nu e o semnătură greșită.
        return {"ok": True, "status": "unsupported", "lines": problems,
                "note": "Validatorul ANAF de pe calculator nu poate verifica semnăturile făcute cu acest tip de cheie (ECDSA, ca la buletinul "
                        "electronic). Semnătura e pusă corect, dar nu putem confirma de aici că ANAF o primește."}
    if sig_err or problems or unsigned:
        return {"ok": True, "status": "errors", "lines": ([sig_err] if sig_err else []) + problems + (["PDF-ul nu este semnat."] if unsigned else []),
                "note": "Validatorul ANAF a găsit probleme la PDF-ul semnat."}
    return {"ok": True, "status": "ok", "lines": [],
            "note": "Validatorul ANAF a verificat și PDF-ul semnat: structura, XML-ul atașat și semnătura sunt în regulă."}


def types(v: dict | None = None) -> list:
    """Declarațiile pentru care ANAF are validator: întâi cele obișnuite, apoi restul, după cod."""
    try:
        v = v or parse_versions((HOME / "versiuni.xml").read_text(encoding="utf-8", errors="replace"))
    except (OSError, AnafError):
        return [{"code": c, "name": n} for c, n in NAMES.items()]
    codes = sorted(v["decl"], key=lambda c: (c not in NAMES, c))
    return [{"code": c, "name": NAMES.get(c, "")} for c in codes]


def status() -> dict:
    st = _state()
    return {"ok": True, "job": dict(JOB), "checked": st.get("checked") or 0, "integrator": st.get("integrator", ""),
            "installed": {c: {"J": d.get("J"), "P": d.get("P")} for c, d in (st.get("decl") or {}).items()},
            "java": bool(os.environ.get("FX_ANAF_JAVA") or deps.java()), "types": types()}
