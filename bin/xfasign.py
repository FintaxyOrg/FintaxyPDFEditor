"""Semnătura VIZIBILĂ pe formularele XFA dinamice (declarațiile ANAF nesalvate din Adobe: D300, D394, D112…), ca în Acrobat.

În fișier, formularul are doar pagina „Please wait…” și niciun câmp de semnătură AcroForm. Acrobat semnează în câmpul
XFA de tip semnătură (caseta „Semnatura” din antet) și adaugă un câmp AcroForm cu numele SOM al lui
(ex. `form1[0].Antet[0].IdDoc[0].sgn[0]`), pe care îl arată apoi în acel loc din formular. Facem la fel:
- `fields(doc)`: câmpurile de semnătură din șablonul XFA, cu numele SOM (cum le scrie Acrobat);
- `add_field(writer, name, rect)`: câmpul AcroForm cu ierarhia lui (form1[0] → Antet[0] → … → sgn[0]), în aceeași
  actualizare incrementală în care pyHanko pune semnătura;
- `rect_for(path)`: locul casetei, măsurat pe formularul desenat de pdf.js (xfaview), în coordonatele paginii
  formularului (A4, origine jos-stânga), cum îl scrie și Acrobat;
- `look(name, when)`: aspectul semnăturii ca la Acrobat (numele mare în stânga, „Digitally signed by … / Date: …” în
  dreapta, Courier New Bold), fără sigla Adobe.
"""
import datetime as dt
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

import fx_sign

CONTAINERS = {"subform", "subformSet", "area", "exclGroup", "field"}
FONT_FILES = [Path(r"C:\Windows\Fonts\courbd.ttf")]  # Courier New Bold, ca în formularele ANAF și la Acrobat


def _tag(e) -> str:
    return e.tag.split("}")[-1] if isinstance(e.tag, str) else ""


def _template(doc) -> bytes | None:
    try:
        arr = doc.xref_get_key(doc.pdf_catalog(), "AcroForm/XFA")
    except Exception:  # noqa: BLE001
        return None
    if arr[0] != "array":
        return None
    for name, xref in re.findall(r"\(([^)]*)\)\s*(\d+) 0 R", arr[1]):
        if name == "template":
            return doc.xref_stream(int(xref))
    return None


def _named_children(node):
    """Copiii cu nume care contează în SOM; subformularele fără nume sunt „transparente” (copiii lor urcă un nivel)."""
    for c in node:
        t = _tag(c)
        if t == "pageSet":
            continue
        if t in CONTAINERS and c.get("name"):
            yield c
        elif t in CONTAINERS or t in ("proto",):
            if t != "proto":
                yield from _named_children(c)


def _is_signature(field) -> bool:
    ui = next((c for c in field if _tag(c) == "ui"), None)
    return ui is not None and any(_tag(c) == "signature" for c in ui)


def _caption(field) -> str:
    cap = next((c for c in field if _tag(c) == "caption"), None)
    if cap is None:
        return ""
    return " ".join(t.strip() for t in cap.itertext() if t.strip())


def fields(doc) -> list:
    """Câmpurile de semnătură din șablonul XFA: [{"name": "form1[0].Antet[0].IdDoc[0].sgn[0]", "caption": "Semnatura"}]."""
    raw = _template(doc)
    if not raw:
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    out = []

    def walk(node, path):
        seen = {}
        for c in _named_children(node):
            name = c.get("name")
            i = seen.get(name, 0)
            seen[name] = i + 1
            p = path + [f"{name}[{i}]"]
            if _tag(c) == "field":
                if _is_signature(c):
                    out.append({"name": ".".join(p), "caption": _caption(c)})
            else:
                walk(c, p)

    walk(root, [])
    return out


def rect_for(path: str, index: int = 0):
    """Locul casetei de semnătură nr. `index` (în ordinea paginilor), măsurat pe formularul desenat:
    (pagina, [x0, y0, x1, y1]) în puncte, origine jos-stânga, pe pagina formularului. None dacă nu s-a putut desena."""
    import xfaview
    boxes = xfaview.signature_boxes(path)
    if not boxes or index >= len(boxes):
        return None
    b = boxes[index]
    H = b.get("pageHeight") or 842
    return b["page"], [round(b["x0"], 3), round(H - b["y1"], 3), round(b["x1"], 3), round(H - b["y0"], 3)]


def add_field(w, name: str, rect: list):
    """Câmpul de semnătură cu numele SOM `name`, cu ierarhia lui de câmpuri-părinte (refolosite dacă există deja),
    widget pe prima pagină a fișierului, la `rect`. În scriitorul incremental pyHanko `w`, înaintea semnării."""
    from pyhanko.pdf_utils import generic

    parts = name.split(".")
    root = w.root
    af_ref = root.raw_get("/AcroForm")
    af = af_ref.get_object()
    if "/Fields" not in af:
        af[generic.NameObject("/Fields")] = generic.ArrayObject()
    kids = af["/Fields"]
    kids_owner = None  # None = /Fields din AcroForm
    parent = None
    for part in parts[:-1]:
        found = None
        for k in list(kids):
            ko = k.get_object()
            if str(ko.get("/T", "")) == part and "/Kids" in ko:
                found = k
                break
        if found is None:
            d = generic.DictionaryObject({generic.NameObject("/T"): generic.TextStringObject(part),
                                          generic.NameObject("/Kids"): generic.ArrayObject()})
            if parent is not None:
                d[generic.NameObject("/Parent")] = parent
            found = w.add_object(d)
            kids.append(found)
            if kids_owner is not None:
                w.mark_update(kids_owner)
        parent = found
        kids_owner = found
        kids = found.get_object()["/Kids"]
    page_ref = w.find_page_for_modification(0)[0]
    page = page_ref.get_object()
    sig = generic.DictionaryObject({
        generic.NameObject("/Type"): generic.NameObject("/Annot"),
        generic.NameObject("/Subtype"): generic.NameObject("/Widget"),
        generic.NameObject("/FT"): generic.NameObject("/Sig"),
        generic.NameObject("/T"): generic.TextStringObject(parts[-1]),
        generic.NameObject("/F"): generic.NumberObject(4),
        generic.NameObject("/Rect"): generic.ArrayObject(generic.FloatObject(v) for v in rect),
        generic.NameObject("/P"): page_ref,
    })
    if parent is not None:
        sig[generic.NameObject("/Parent")] = parent
    sig_ref = w.add_object(sig)
    kids.append(sig_ref)
    if kids_owner is not None:
        w.mark_update(kids_owner)
    af[generic.NameObject("/SigFlags")] = generic.NumberObject(3)
    if isinstance(af_ref, generic.IndirectObject):
        w.mark_update(af_ref)
    else:
        w.update_root()
    annots = page.get("/Annots")
    if annots is None:
        page[generic.NameObject("/Annots")] = generic.ArrayObject([sig_ref])
    else:
        annots.get_object().append(sig_ref)
        if isinstance(page.raw_get("/Annots"), generic.IndirectObject):
            w.mark_update(page.raw_get("/Annots"))
    w.mark_update(page_ref)


# ---------------------------------------------------------------- aspectul, ca la Acrobat

def _font_file() -> str | None:
    return next((str(f) for f in FONT_FILES if f.is_file()), None)


def _wrap(text, width, font, size):
    """Rupe rândurile ca Acrobat: după spațiu sau după cratimă (cratima rămâne la capătul rândului)."""
    tokens = re.findall(r"[^ -]+-?|[ ]", text)
    lines, cur = [], ""
    for tok in tokens:
        cand = cur + tok
        if font.text_length(cand.rstrip(), fontsize=size) <= width or not cur.strip():
            cur = cand
        else:
            lines.append(cur.rstrip())
            cur = tok.lstrip()
    lines.append(cur.rstrip())
    return [ln for ln in lines if ln]


def adobe_date(when: dt.datetime) -> str:
    off = when.utcoffset() or dt.timedelta(0)
    sign = "+" if off >= dt.timedelta(0) else "-"
    mins = abs(int(off.total_seconds())) // 60
    return f"{when:%Y.%m.%d %H:%M:%S} {sign}{mins // 60:02d}'{mins % 60:02d}'"


def look(name: str, when: dt.datetime, width: float, height: float) -> str | None:
    """PDF de o pagină cât caseta, cu aspectul semnăturii ca la Acrobat. None dacă lipsește fontul (rămâne aspectul
    obișnuit al aplicației). Mărimile sunt măsurate pe o semnătură Acrobat din caseta „Semnatura” a D300
    (189,9 x 21 pt): numele 7,8 pt, detaliile 4,5 pt, de la 51% din lățime; la altă casetă se scalează."""
    ff = _font_file()
    if not ff:
        return None
    font = fitz.Font(fontfile=ff)
    k = min(width / 189.922, height / 20.975)
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    page.insert_font(fontname="CB", fontfile=ff)
    pad = 1.0 * k
    left_w, right_x = width * 0.49 - pad, width * 0.51
    right_w = width - right_x - pad
    parts = name.split(" ")
    left = [" ".join(parts[:-1]), parts[-1]] if len(parts) > 1 else [name]
    ls = 7.8 * k
    while ls > 2 and (max(font.text_length(t, fontsize=ls) for t in left) > left_w or len(left) * ls * 1.15 > height - 2 * pad):
        ls -= 0.1
    top = (height - len(left) * ls * 1.15) / 2
    for i, t in enumerate(left):
        page.insert_text((pad, top + ls * (1.0 + 1.15 * i)), t, fontname="CB", fontsize=ls)
    rs = 4.5 * k
    while True:
        right = _wrap(f"Digitally signed by {name}", right_w, font, rs) + [f"Date: {adobe_date(when)}"]
        if rs <= 2 or (max(font.text_length(t, fontsize=rs) for t in right) <= right_w
                       and len(right) * rs * 1.15 <= height - 2 * pad):
            break
        rs -= 0.1
    top = (height - len(right) * rs * 1.15) / 2
    for i, t in enumerate(right):
        page.insert_text((right_x, top + rs * (1.0 + 1.15 * i)), t, fontname="CB", fontsize=rs)
    doc.subset_fonts()
    fd, name_ = tempfile.mkstemp(prefix="fx-sig-", suffix=".pdf", dir=str(fx_sign.STATE))
    os.close(fd)  # pe Windows un handle deschis blochează ștergerea de după semnare
    out = Path(name_)
    doc.save(out)
    doc.close()
    return str(out)


def stamp_style(look_pdf: str):
    """Aspectul pentru pyHanko: desenul ocupă exact caseta (fără marginile implicite, care îl micșorau)."""
    from pyhanko.pdf_utils.layout import AxisAlignment, InnerScaling, Margins, SimpleBoxLayoutRule
    from pyhanko.stamp import StaticStampStyle
    rule = SimpleBoxLayoutRule(x_align=AxisAlignment.ALIGN_MIN, y_align=AxisAlignment.ALIGN_MIN,
                               margins=Margins(0, 0, 0, 0), inner_content_scaling=InnerScaling.STRETCH_FILL)
    return StaticStampStyle.from_pdf_file(look_pdf, border_width=0, background_layout=rule, background_opacity=1)
