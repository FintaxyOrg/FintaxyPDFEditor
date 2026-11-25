"""„Validează formularul” ca în Adobe, pentru declarațiile ANAF dinamice nesalvate din Adobe (D300 scos din SAGA Web).

Programele de contabilitate (SAGA Web) dau D300 ca PDF-ul inteligent ANAF: formular XFA dinamic, „FORMULAR
NEVALIDAT”, fără XML atașat. În Adobe, butonul „Validează formularul” rulează scripturile din formular: genXML()
(scrie XML-ul declarației din câmpuri), suma de control (totalPlata_A) și valorile implicite, apoi atașează D300.xml.
Facem același lucru fără Adobe:
- `build_xml`: maparea câmp → atribut e citită din genXML() al formularului, nu scrisă aici, deci urmează versiunea
  formularului (verificat 24.11.2026: D300 MIRALEV 09.2026, validat în Adobe și depus cu recipisă → XML-ul nostru
  trece validatorul ANAF cu 0 erori, aceeași sumă de control ca Adobe);
- `validated_pdf`: PDF-ul original + o actualizare incrementală (xref stream, ca formularele ANAF; drepturile Reader
  UR3 rămân): datele XFA cu suma de control și „FORMULAR VALIDAT”, plus D300.xml atașat. Se scrie lângă original ca
  `<nume>_validat.pdf`; originalul rămâne neatins. Semnătura (caseta „Semnatura”, xfasign) se pune apoi pe el.
Doar D300 deocamdată (rădăcina XML declaratie300, suma de control din antet); alte formulare: `kind` = "".
"""
from __future__ import annotations

import html
import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr

import fitz

PAIR = re.compile(r"obj\s*=\s*([\w\.\[\]]+)\s*;[^\n]*\n?\s*if\s*\(obj\.rawValue\s*!=\s*null\)\s*xml\s*\+=\s*\"\s*(\w+)=")
ADR = [("str", "strada: "), ("nr", "nr: "), ("loc", "localitate: "), ("judet", "judet: "), ("sect", "sector: "),
       ("bloc", "bloc: "), ("scara", "scara: "), ("etaj", "etaj: "), ("apt", "apartament: "), ("codPst", "cod postal: ")]


class PrepError(ValueError):
    pass


def _parts(doc) -> dict:
    arr = doc.xref_get_key(doc.pdf_catalog(), "AcroForm/XFA")
    if arr[0] != "array":
        return {}
    return {n: x for n, x in re.findall(r"\(([^)]*)\)\s*(\d+) 0 R", arr[1])}


def _template(doc) -> str:
    x = _parts(doc).get("template")
    return html.unescape(doc.xref_stream(int(x)).decode("utf-8", "replace")) if x else ""


def kind(path: str) -> str:
    """"D300" când PDF-ul e un D300 inteligent ANAF nevalidat, fără XML atașat (îl putem valida aici); altfel ""."""
    try:
        with fitz.open(path) as doc:
            if doc.needs_pass or any(n.lower().endswith(".xml") for n in doc.embfile_names()):
                return ""
            tpl = _template(doc)
    except Exception:  # noqa: BLE001
        return ""
    return "D300" if "function genXML()" in tpl and "<declaratie300" in tpl.replace("&lt;", "<") else ""


def _gen_xml(tpl: str) -> str:
    i = tpl.find("function genXML()")
    if i < 0:
        raise PrepError("formularul nu are scriptul genXML() (nu e un D300 inteligent ANAF)")
    j = tpl.find("// eof genXML", i)
    return tpl[i:j if j > 0 else None]


def _counties(tpl: str) -> dict:
    i = tpl.find('name="judet"')
    if i < 0:
        return {}
    lists = re.findall(r"<items([^>]*)>(.*?)</items\s*>", tpl[i:i + 80000], re.S)[:2]
    if len(lists) < 2:
        return {}
    shown = re.findall(r"<text\s*>(.*?)</text\s*>", lists[0][1])
    saved = re.findall(r"<text\s*>(.*?)</text\s*>", lists[1][1])
    return dict(zip(saved, shown))


def default_of(tpl: str, field: str):
    name = field.split(".")[-1]
    if re.fullmatch(r"c\d+|nrCrt", name):
        return None
    m = re.search(r'<field\b[^>]*\bname="%s"[^>]*>(.*?)</field\s*>' % re.escape(name), tpl, re.S)
    if not m:
        return None
    body = re.sub(r"<caption\b.*?</caption\s*>", "", m.group(1), flags=re.S)  # eticheta nu e valoare
    body = re.sub(r"<(items|script|event)\b.*?</\1\s*>", "", body, flags=re.S)
    v = re.search(r"<value\s*>\s*<\w+\s*>(.*?)</\w+\s*>", body, re.S)
    return v.group(1).strip() if v and v.group(1).strip() else None


class _Data:
    def __init__(self, datasets: bytes, tpl: str):
        self.root = ET.fromstring(datasets)
        try:
            self.form1 = next(e for e in self.root.iter() if e.tag.split("}")[-1] == "form1")
        except StopIteration as exc:
            raise PrepError("datele formularului nu au form1") from exc
        self.tpl, self.override = tpl, {}

    def raw(self, path: str):
        node = self.form1
        for part in path.split("."):
            name = re.sub(r"\[\d+\]$", "", part)
            idx = int(re.search(r"\[(\d+)\]$", part).group(1)) if part.endswith("]") else 0
            kids = [c for c in node if c.tag.split("}")[-1] == name]
            if len(kids) <= idx:
                return None
            node = kids[idx]
        if len(node):
            return None
        v = (node.text or "").strip()
        return v or None

    def get(self, path: str):
        if path in self.override:
            return self.override[path]
        v = self.raw(path)
        return default_of(self.tpl, path) if v is None else v

    def set(self, path: str, value: str):
        node = self.form1
        for part in path.split("."):
            kids = [c for c in node if c.tag.split("}")[-1] == part]
            if kids:
                node = kids[0]
            else:
                ns = node.tag.split("}")[0] + "}" if node.tag.startswith("{") else ""
                node = ET.SubElement(node, ns + part)
        node.text = value


def _num(v) -> float:
    try:
        return float(str(v).replace(" ", "")) if v not in (None, "") else 0.0
    except ValueError:
        return 0.0


def _control_sum(tpl: str, data: _Data) -> str:
    p = tpl.find("Antet.metaDate.totalPlata_A.rawValue = suma;")
    q = tpl.rfind("var suma", 0, p) if p > 0 else -1
    if q < 0:
        raise PrepError("formularul nu are scriptul sumei de control")
    total = sum(_num(data.get(x)) for x in re.findall(r"([\w\.]+)\.rawValue", tpl[q:p]))
    return str(int(total)) if total == int(total) else str(round(total, 2))


def _load(path: str):
    with fitz.open(path) as doc:
        parts = _parts(doc)
        if "template" not in parts or "datasets" not in parts:
            raise PrepError("PDF-ul nu are formular XFA (șablon și date)")
        tpl = html.unescape(doc.xref_stream(int(parts["template"])).decode("utf-8", "replace"))
        ds = doc.xref_stream(int(parts["datasets"]))
    return tpl, ds


def _xml_of(tpl: str, data: _Data) -> str:
    src = _gen_xml(tpl)
    data.override["Antet.metaDate.totalPlata_A"] = _control_sum(tpl, data)
    attrs = []
    events = [(m.start(), "pair", m.group(1), m.group(2)) for m in PAIR.finditer(src)]
    events.append((src.find('if (adr != "")'), "adresa", "", ""))
    events.append((src.find("obj = identifCntr.caen;"), "caen", "", ""))
    counties = _counties(tpl)
    for _pos, k, field, attr in sorted(events):
        if k == "pair":
            v = data.get(field)
            if v is not None:
                attrs.append((attr, v))
        elif k == "adresa":
            adr = ""
            for key, label in ADR:
                v = data.get(f"identifCntr.adresa.{key}")
                if v is not None:
                    adr += label + (counties.get(v, v) if key == "judet" else v) + ("" if key == "codPst" else ", ")
            if adr:
                attrs.append(("adresa", adr))
        else:
            for f in ("identifCntr.caen", "identifCntr.caen1"):
                v = data.get(f)
                if v is not None:
                    attrs.append(("caen", v))
    live = [ln for ln in src.split("\n") if ln.strip().startswith('xml += " xmlns:xsi')]
    if not live:
        raise PrepError("scriptul genXML() nu are spațiul de nume al XML-ului")
    loc, xmlns = re.search(r'schemaLocation=\\"(.*?)\\" xmlns=\\"(.*?)\\"', live[-1]).groups()
    seen, out = set(), []
    for a, v in attrs:
        if a not in seen:
            seen.add(a)
            out.append(f" {a}={quoteattr(v)}")
    return ('<?xml version="1.0"?>\n<declaratie300' + "".join(out)
            + f' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="{loc}" xmlns="{xmlns}">'
            + "</declaratie300>")


def build_xml(path: str) -> str:
    """XML-ul D300 din formular, ca la „Validează formularul” din Adobe."""
    tpl, ds = _load(path)
    return _xml_of(tpl, _Data(ds, tpl))


def output_for(src: Path) -> Path:
    return src.with_name(f"{src.stem}_validat.pdf")


def validated_pdf(path: str) -> str:
    """`<nume>_validat.pdf`: originalul + datele validate (suma de control, „FORMULAR VALIDAT”, implicitele din XML)
    + D300.xml atașat, într-o actualizare incrementală (xref stream). Întoarce calea lui."""
    from pyhanko.pdf_utils import embed, generic
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

    src = Path(path)
    tpl, ds = _load(path)
    for pfx, uri in re.findall(rb'xmlns:(\w+)="([^"]+)"', ds):
        ET.register_namespace(pfx.decode(), uri.decode())
    data = _Data(ds, tpl)
    data.set("Antet.metaDate.totalPlata_A", _control_sum(tpl, data))
    data.set("Antet.IdDoc.formValid", "FORMULAR VALIDAT")
    for f in ("Antet.d_reprezentant", "Antet.metaDate.d_rez", "Antet.metaDate.d_scc",
              "Antet.opInterne.mtdSimplificata", "Antet.IdDoc.universalCode"):
        if data.raw(f) is None and default_of(tpl, f) is not None:
            data.set(f, default_of(tpl, f))
    new_ds = ET.tostring(data.root, encoding="utf-8")
    xml = _xml_of(tpl, _Data(new_ds, tpl))  # din datele care intră în PDF: exact XML-ul atașat

    w = IncrementalPdfFileWriter(io.BytesIO(src.read_bytes()), strict=False)
    root = w.root
    af_ref = root.raw_get("/AcroForm")
    af = af_ref.get_object()
    st = generic.StreamObject(stream_data=new_ds)
    st.compress()  # comprimat o singură dată (stream_data e necomprimat)
    st_ref = w.add_object(st)
    items = list(af["/XFA"])
    new_xfa = generic.ArrayObject()
    for i in range(0, len(items) - 1, 2):
        new_xfa.append(items[i])
        new_xfa.append(st_ref if str(items[i]) == "datasets" else items[i + 1])
    af[generic.NameObject("/XFA")] = new_xfa
    if isinstance(af_ref, generic.IndirectObject):
        w.mark_update(af_ref)
    else:
        w.update_root()
    spec = embed.FileSpec(file_spec_string="D300.xml", file_name="D300.xml",
                          embedded_data=embed.EmbeddedFileObject.from_file_data(
                              w, data=xml.encode("utf-8"), mime_type="text/xml"))
    embed.embed_file(w, spec)
    buf = io.BytesIO()
    w.write(buf)
    out = output_for(src)
    tmp = out.with_name(f".{out.stem}.tmp.pdf")
    tmp.write_bytes(buf.getvalue())
    tmp.replace(out)
    return str(out)
