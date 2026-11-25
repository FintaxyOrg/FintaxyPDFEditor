"""Versiunea formularului ANAF (`universalCode`) în datele unui formular XFA, înainte de semnare.

Butonul „Validare” al formularelor ANAF (în Adobe) scrie în datele formularului câmpul ascuns `universalCode`
(ex. D112_A7.2.4, D300_A12.0.2, D301_A2.0.4). Serverul ANAF citește de acolo versiunea formularului. Dacă lipsește,
respinge depunerea cu „Fisierul depus nu este un document valid - Versiunea formularului nu este corecta”.
Așa s-a întâmplat la un D112 din SAGA Web, semnat aici, pe 25.11.2026. PDF-urile scoase de SAGA Web sunt completate
fără Adobe, deci nu au câmpul. Validatorul ANAF de pe calculator (DUKIntegrator -v pe PDF) arată același lucru:
„Tipul declaratiei (D112) nu corespunde cu cel din PDF ()”.

Valoarea e cea pe care o scrie formularul însuși: cea mai nouă dintre atribuirile `universalCode.rawValue="…"` din
scripturile lui. La D112 e A7.2.4, deși valoarea implicită a câmpului e A7.2.5; ANAF a primit A7.2.4. Dacă scripturile
nu o scriu (D300), se ia valoarea implicită a câmpului. Câmpul se adaugă doar când lipsește sau e gol; restul datelor
rămân octet cu octet la fel.
"""
import html
import re
import xml.etree.ElementTree as ET

FIELD = "universalCode"
_ASSIGN = re.compile(r"\buniversalCode\s*\.\s*rawValue\s*=\s*[\"']([^\"']+)[\"']")


def _tag(e) -> str:
    return e.tag.split("}")[-1] if isinstance(e.tag, str) else ""


def _version_key(code: str):
    return tuple(int(n) for n in re.findall(r"\d+", code.rsplit("_", 1)[-1]))


def _bind(node):
    return next((c for c in node if _tag(c) == "bind"), None)


def expected(template: bytes) -> dict | None:
    """{"path": ["frmMAIN", "universalCode"], "value": "D112_A7.2.4"} sau None: formularul nu are câmpul."""
    try:
        root = ET.fromstring(template)
    except ET.ParseError:
        return None
    found = []

    def walk(node, path):
        for c in node:
            t = _tag(c)
            if t in ("pageSet", "proto"):
                continue
            b = _bind(c)
            unbound = b is not None and b.get("match") == "none"
            if t == "field":
                if c.get("name") == FIELD and not unbound:
                    found.append((c, path))
            elif t in ("subform", "subformSet", "area", "exclGroup"):
                # un subformular cu nume e un grup în date; fără nume sau cu bind="none" e „transparent”
                walk(c, path + [c.get("name")] if c.get("name") and not unbound and t == "subform" else path)

    walk(root, [])
    if len(found) != 1:
        return None
    field, path = found[0]
    b = _bind(field)
    if b is not None and b.get("match") == "dataRef":
        ref = (b.get("ref") or "").strip()
        if not ref.startswith("$."):  # alt fel de legare decât relativă la subformular: nu ghicim
            return None
        path = path + [p for p in re.sub(r"\[\d+\]", "", ref[2:]).split(".") if p]
    else:
        path = path + [FIELD]
    text = html.unescape(template.decode("utf-8", "replace"))
    assigned = set(_ASSIGN.findall(text))
    if assigned:
        value = max(assigned, key=_version_key)
    else:
        v = next((c for c in field if _tag(c) == "value"), None)
        value = next(("".join(x.itertext()).strip() for x in (v if v is not None else []) if _tag(x) == "text"), "")
    if not value or not path:
        return None
    return {"path": path, "value": value}


def _data_root(datasets: bytes, top: str):
    root = ET.fromstring(datasets)
    data = next((e for e in root.iter() if _tag(e) == "data"), None)
    if data is None:
        return None
    return next((c for c in data if _tag(c) == top), None)


def current(datasets: bytes, path: list) -> str | None:
    """Valoarea din date (\"\" = câmp gol sau lipsă). None: datele nu sunt ale acestui formular."""
    try:
        node = _data_root(datasets, path[0])
    except ET.ParseError:
        return None
    if node is None:
        return None
    for name in path[1:]:
        node = next((c for c in node if _tag(c) == name), None)
        if node is None:
            return ""
    return (node.text or "").strip()


def add(datasets: bytes, path: list, value: str) -> bytes:
    """Datele cu câmpul completat. Inserat ca text în datele existente (restul rămâne identic)."""
    node = _data_root(datasets, path[0])
    if node is None:
        raise ValueError("Datele formularului nu au grupul " + path[0])
    depth = 1
    for name in path[1:]:
        nxt = next((c for c in node if _tag(c) == name), None)
        if nxt is None:
            break
        node, depth = nxt, depth + 1
    leaf = f"<{path[-1]}>{_esc(value)}</{path[-1]}>"
    if depth == len(path):  # câmpul există, dar e gol: <universalCode/> sau <universalCode></universalCode>
        pat = re.compile(rb"<" + path[-1].encode() + rb"\s*(/>|>\s*</" + path[-1].encode() + rb"\s*>)")
        hits = pat.findall(datasets)
        if len(hits) != 1:
            raise ValueError("Câmpul gol apare de mai multe ori în date; nu îl completez la ghici.")
        return pat.sub(leaf.encode(), datasets, count=1)
    frag = leaf
    for name in reversed(path[depth:-1]):
        frag = f"<{name}>{frag}</{name}>"
    anc = path[depth - 1].encode()
    close = re.compile(rb"</(?:\w+:)?" + anc + rb"\s*>")
    empty = re.compile(rb"<((?:\w+:)?" + anc + rb")(\s[^<>]*?)?\s*/>")
    if len(close.findall(datasets)) == 1 and not empty.search(datasets):
        m = close.search(datasets)
        return datasets[:m.start()] + frag.encode() + datasets[m.start():]
    if not close.search(datasets) and len(empty.findall(datasets)) == 1:
        m = empty.search(datasets)
        return (datasets[:m.start()] + b"<" + m.group(1) + (m.group(2) or b"") + b">" + frag.encode()
                + b"</" + m.group(1) + b">" + datasets[m.end():])
    raise ValueError(f"Grupul {path[depth - 1]} apare de mai multe ori în date; nu adaug versiunea la ghici.")


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _packets(arr):
    """[(nume, index_în_listă_al_fluxului)] din lista /XFA."""
    out = []
    for i in range(0, len(arr) - 1, 2):
        out.append((str(arr[i]), i + 1))
    return out


def needed(path: str) -> dict | None:
    """Pentru un PDF: {"path", "value"} dacă formularul ANAF n-are versiunea în date (o completăm la semnare)."""
    from pyhanko.pdf_utils.reader import PdfFileReader
    try:
        with open(path, "rb") as f:
            r = PdfFileReader(f, strict=False)
            return _needed_in(r.root)
    except Exception:  # noqa: BLE001  - nu e un formular XFA citibil: nu avem ce completa
        return None


def _signed(af) -> bool:
    """Are deja o semnătură? Atunci datele nu se mai ating: o schimbare după semnare ar strica semnătura existentă."""
    stack = list(af.get("/Fields") or [])
    while stack:
        f = stack.pop().get_object()
        if f.get("/FT") == "/Sig" and f.get("/V") is not None:
            return True
        stack.extend(f.get("/Kids") or [])
    return False


def _needed_in(root) -> dict | None:
    af = root.get("/AcroForm")
    if af is None:
        return None
    af = af.get_object()
    if _signed(af):
        return None
    arr = af.get("/XFA")
    if arr is None or not hasattr(arr.get_object(), "__len__"):
        return None
    arr = arr.get_object()
    streams = {name: arr[i].get_object() for name, i in _packets(arr)}
    if "template" not in streams or "datasets" not in streams:
        return None
    want = expected(streams["template"].data)
    if not want:
        return None
    have = current(streams["datasets"].data, want["path"])
    if have is None or have:
        return None
    return want


def fix(w) -> str | None:
    """În scriitorul incremental pyHanko `w` (înaintea semnăturii): completează versiunea formularului dacă lipsește.
    Întoarce valoarea pusă sau None (nu era nevoie / nu e formular ANAF)."""
    from pyhanko.pdf_utils import generic

    try:
        want = _needed_in(w.root)
    except Exception:  # noqa: BLE001
        return None
    if not want:
        return None
    af_ref = w.root.raw_get("/AcroForm")
    af = af_ref.get_object()
    xfa_ref = af.raw_get("/XFA")
    arr = xfa_ref.get_object()
    idx = next(i for name, i in _packets(arr) if name == "datasets")
    old = arr[idx].get_object()
    new = generic.StreamObject(stream_data=add(old.data, want["path"], want["value"]))
    new.compress()
    arr[idx] = w.add_object(new)
    if isinstance(xfa_ref, generic.IndirectObject):
        w.mark_update(xfa_ref)
    elif isinstance(af_ref, generic.IndirectObject):
        w.mark_update(af_ref)
    else:
        w.update_root()
    return want["value"]
