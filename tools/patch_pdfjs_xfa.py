"""Pregătește pdf.js pentru formularele XFA ale ANAF, ca să arate ca în Adobe Reader.

pdf.js (pdfjs-dist 4.10.38) desenează XFA, dar față de Adobe: lasă la 0 coloanele de tabel cu lățime 0/-1 (Adobe le
dă lățimea conținutului: la D301 dispare coloana „TVA datorat”), ignoră alinierea (para hAlign) în câmpuri, nu
formatează numerele după limbă (Adobe: 27.525,55), nu desenează căsuțele „comb” (CIF-ul pe 13 căsuțe), arată bifele
ca elemente HTML rotunde (Adobe: pătrat cu X) și strică sigla ANAF (BMP cu offsetul datelor 0, pe care Chrome nu-l
acceptă).

Folosire (din rădăcina repo-ului):
    npm pack pdfjs-dist@4.10.38 && tar xzf pdfjs-dist-4.10.38.tgz
    python tools/patch_pdfjs_xfa.py package
Scrie editor/xfa/pdf.min.mjs (neschimbat), editor/xfa/pdf.worker.mjs (cu corecturile de mai jos) și
editor/xfa/standard_fonts/ (metricile fonturilor; fără ele pdf.js măsoară greșit textele și le suprapune).
"""
import shutil
import sys
from pathlib import Path

VERSION = "4.10.38"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "editor" / "xfa"

HELPERS = r'''
/* ---- Fintaxy: XFA ca în Adobe (tools/patch_pdfjs_xfa.py) ---- */
function fxResolveAutoColumns(node) {
  // Coloană cu lățimea 0 sau -1: Adobe îi dă lățimea celei mai late celule de pe ea (pdf.js o lasă la 0).
  const cw = node.columnWidths;
  if (!Array.isArray(cw) || !cw.some(w => !(w > 0))) {
    return;
  }
  const max = cw.map(() => 0);
  const visit = rows => {
    for (const row of rows) {
      if (row.presence === "hidden" || row.presence === "inactive") {
        continue;
      }
      if (row instanceof SubformSet) {
        visit(row[$getChildren]().filter(c => c instanceof Subform || c instanceof SubformSet));
        continue;
      }
      if (!(row instanceof Subform) || !row.layout.includes("row")) {
        continue;
      }
      let col = 0;
      for (const cell of row[$getChildren]()) {
        if (!(cell instanceof Draw || cell instanceof Field || cell instanceof Subform || cell instanceof ExclGroup)) {
          continue;
        }
        if (cell.presence === "hidden" || cell.presence === "inactive") {
          continue;
        }
        const span = cell.colSpan === -1 ? cw.length - col : cell.colSpan;
        if (span === 1 && col < cw.length) {
          const w = typeof cell.w === "number" ? cell.w : typeof cell.minW === "number" ? cell.minW : 0;
          max[col] = Math.max(max[col], w);
        }
        col += span;
      }
    }
  };
  visit(node[$getChildren]().filter(c => c instanceof Subform || c instanceof SubformSet));
  node.columnWidths = cw.map((w, i) => (w > 0 ? w : max[i]));
}
const fxLocaleSymbols = new Map();
function fxSymbols(locale) {
  // Separatorul de mii și cel zecimal ale limbii câmpului (ro_RO: „.” și „,”).
  const key = (locale || "ro_RO").replace("_", "-");
  if (!fxLocaleSymbols.has(key)) {
    let group = ".",
      decimal = ",";
    try {
      const parts = new Intl.NumberFormat(key).formatToParts(1234567.5);
      group = parts.find(p => p.type === "group")?.value ?? group;
      decimal = parts.find(p => p.type === "decimal")?.value ?? decimal;
    } catch {}
    fxLocaleSymbols.set(key, { group, decimal });
  }
  return fxLocaleSymbols.get(key);
}
function fxLocale(node) {
  for (let n = node; n; n = n[$getParent]?.()) {
    if (n.locale) {
      return n.locale;
    }
  }
  return "ro_RO";
}
function fxGroup(intPart, group) {
  return intPart.replace(/\B(?=(\d{3})+(?!\d))/g, group);
}
function fxFormatNumber(field, raw) {
  // Cum afișează Adobe un câmp numeric: după „picture” (num{z,zz9.99}) dacă are; altfel cu separatorii limbii și
  // zecimalele valorii (fără zerourile de la coadă), cel mult câte permite <decimal fracDigits>.
  const num = parseFloat(raw);
  if (isNaN(num)) {
    return "";
  }
  const { group, decimal } = fxSymbols(fxLocale(field));
  let picture = field.format?.picture?.[$content];
  picture = typeof picture === "string" ? picture.trim() : "";
  let pic = "";
  if (picture) {
    const m = /^num(?:\.[a-z]+)?\{(.*)\}$/i.exec(picture);
    pic = m ? m[1] : picture;
  }
  if (pic && /^[-+sS$ ]*[zZ98,]*(\.[zZ98]*)?[-+sS$ ]*$/.test(pic) && /[zZ98]/.test(pic)) {
    const core = pic.replace(/[-+sS$ ]/g, "");
    const [ip, fp = ""] = core.split(".");
    const fixed = (fp.match(/9/g) || []).length;
    const optional = (fp.match(/[zZ8]/g) || []).length;
    let [i, f = ""] = Math.abs(num).toFixed(fixed + optional).split(".");
    while (f.length > fixed && f.endsWith("0")) {
      f = f.slice(0, -1);
    }
    const minInt = (ip.match(/9/g) || []).length;
    i = i.replace(/^0+(?=\d)/, "");
    if (i === "0" && minInt === 0 && f) {
      i = "";
    }
    i = i.padStart(minInt, "0");
    if (ip.includes(",")) {
      i = fxGroup(i, group);
    }
    return (num < 0 ? "-" : "") + i + (f ? decimal + f : "");
  }
  const fd = field.value?.decimal?.fracDigits;
  let s = typeof fd === "number" && fd >= 0 ? Math.abs(num).toFixed(fd) : Math.abs(num).toString();
  if (/e/i.test(s)) {
    s = Math.abs(num).toFixed(20);
  }
  let [i, f = ""] = s.split(".");
  f = f.replace(/0+$/, "");
  return (num < 0 ? "-" : "") + fxGroup(i, group) + (f ? decimal + f : "");
}
function fxEdge(border) {
  const edge = border?.edge?.children?.[0];
  const color = edge?.color ? edge.color[$toStyle]() : "#000000";
  const width = edge && edge.thickness > 0 ? measureToString(edge.thickness) : "0.5pt";
  return { color, width, hidden: !!edge && edge.presence !== "visible" };
}
function fxComb(field, ui, value) {
  // Câmp „comb” (CIF-ul pe căsuțe): câte o căsuță pe caracter, cu linii între ele, ca în Adobe.
  const edit = field.ui.textEdit || field.ui.numericEdit;
  const cells = edit?.comb?.numberOfCells || 0;
  if (!cells || !ui.children?.[0]) {
    return;
  }
  const input = ui.children[0];
  const { color, width } = fxEdge(edit.border || field.border);
  const chars = Array.from(String(value || "")).slice(0, cells);
  const hAlign = field.para?.hAlign;
  let start = 0;
  if (hAlign === "right") {
    start = cells - chars.length;
  } else if (hAlign === "center") {
    start = Math.floor((cells - chars.length) / 2);
  }
  const children = [];
  for (let k = 0; k < cells; k++) {
    const ch = k >= start && k - start < chars.length ? chars[k - start] : "";
    children.push({
      name: "span",
      attributes: {
        class: ["fxCombCell"],
        style: {
          flex: "1 1 0",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderLeft: k ? `${width} solid ${color}` : "none",
          overflow: "hidden"
        }
      },
      children: ch ? [{ name: "#text", value: ch }] : []
    });
  }
  ui.children[0] = {
    name: "div",
    attributes: {
      class: ["xfaTextfield", "fxComb"].concat(input.attributes.required ? ["fxRequired"] : []),
      style: Object.assign({}, input.attributes.style, { display: "flex", alignItems: "stretch", padding: "0" })
    },
    children
  };
}
const FX_MARKS = {
  cross: '<path d="M2 2L18 18M18 2L2 18" stroke="#000" stroke-width="1.4" fill="none"/>',
  check: '<path d="M3.5 10.5L8 15L16.5 4.5" stroke="#000" stroke-width="2" fill="none"/>',
  circle: '<circle cx="10" cy="10" r="5" fill="#000"/>',
  diamond: '<path d="M10 3L17 10L10 17L3 10Z" fill="#000"/>',
  square: '<rect x="5" y="5" width="10" height="10" fill="#000"/>',
  star: '<path d="M10 2.5L12.2 7.6L17.6 7.9L13.4 11.4L14.8 16.8L10 13.8L5.2 16.8L6.6 11.4L2.4 7.9L7.8 7.6Z" fill="#000"/>'
};
function fxCheckBox(button, input) {
  // Bifă / radio desenate ca în Adobe: pătrat (sau cerc) cu chenar și semnul din șablon (implicit X în pătrat, punct
  // în cerc). Elementul <input> din pdf.js arată ca bifa din browser.
  const round = button.shape === "round";
  let mark = button.mark;
  if (mark === "default") {
    mark = round ? "circle" : "cross";
  }
  const { color, width, hidden } = fxEdge(button.border);
  const fill = button.border?.fill?.color ? button.border.fill.color[$toStyle]() : null;
  const size = measureToString(button.size);
  const style = {
    boxSizing: "border-box",
    display: "block",
    width: size,
    height: size,
    flex: "0 0 auto",
    border: hidden ? "none" : `${width} solid ${color}`,
    borderRadius: round ? "50%" : "0",
    background: fill || "transparent"
  };
  if (input.attributes.checked) {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">${FX_MARKS[mark] || FX_MARKS.cross}</svg>`;
    style.backgroundImage = `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
    style.backgroundSize = "100% 100%";
  }
  // Învelișul ia locul elementului <input> (pdf.js îi pune apoi înălțimea câmpului) și tot spațiul rămas lângă textul
  // bifei, ca în Adobe: căsuța, de mărimea din șablon, stă centrată în el.
  return {
    name: "span",
    attributes: {
      class: ["fxCheckWrap"],
      style: Object.assign({}, input.attributes.style, {
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flex: "1 1 auto",
        minWidth: size,
        height: "100%"
      })
    },
    children: [{
      name: "span",
      attributes: {
        class: ["fxCheck", round ? "fxRound" : "fxSquare"].concat(input.attributes.required ? ["fxRequired"] : []),
        style,
        role: input.attributes.type === "radio" ? "radio" : "checkbox",
        "aria-label": input.attributes["aria-label"],
        "aria-checked": input.attributes.checked ? "true" : "false"
      },
      children: []
    }]
  };
}
function fxFixBmp(buffer) {
  // BMP cu offsetul datelor (bfOffBits) 0: Adobe îl deduce, Chrome citește pixelii de la început și decalează imaginea.
  if (buffer.length < 54 || buffer[0] !== 0x42 || buffer[1] !== 0x4d) {
    return buffer;
  }
  const dv = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
  const off = dv.getUint32(10, true);
  const hdr = dv.getUint32(14, true);
  if (off >= 14 + hdr) {
    return buffer;
  }
  const bpp = dv.getUint16(28, true);
  const compression = dv.getUint32(30, true);
  let colors = hdr >= 36 ? dv.getUint32(46, true) : 0;
  if (!colors && bpp <= 8) {
    colors = 1 << bpp;
  }
  const masks = compression === 3 && hdr === 40 ? 12 : 0;
  const fixed = new Uint8Array(buffer);
  new DataView(fixed.buffer).setUint32(10, 14 + hdr + masks + colors * 4, true);
  return fixed;
}
/* ---- sfârșit Fintaxy ---- */
'''

PATCHES = [
    # 0. funcțiile de mai sus, înaintea primei clase din template
    ("class AppearanceFilter extends StringObject {", HELPERS + "class AppearanceFilter extends StringObject {"),
    # 1. tabele: coloanele cu lățime 0/-1 primesc lățimea conținutului, înainte de așezarea rândurilor
    ("""    if (this[$extra]?.afterBreakAfter) {
      return HTMLResult.EMPTY;
    }
    fixDimensions(this);
    const children = [];
    const attributes = {
      id: this[$uid],
      class: []
    };
    setAccess(this, attributes.class);""",
     """    if (this[$extra]?.afterBreakAfter) {
      return HTMLResult.EMPTY;
    }
    if (this.layout === "table") {
      fxResolveAutoColumns(this);
    }
    fixDimensions(this);
    const children = [];
    const attributes = {
      id: this[$uid],
      class: []
    };
    setAccess(this, attributes.class);"""),
    # 2. numere formatate ca în Adobe
    ("""          if (this.ui.numericEdit) {
            value = parseFloat(value);
            value = isNaN(value) ? "" : value.toString();
          }""",
     """          if (this.ui.numericEdit) {
            value = fxFormatNumber(this, value);
          }"""),
    # 3. alinierea din câmp (para hAlign), căsuțele comb și bifele, după ce valoarea e pusă
    ("""    if (!this.ui.imageEdit && ui.children?.[0] && this.h) {
      borderDims = borderDims || getBorderDims(this.ui[$getExtra]());""",
     """    const fxInput = ui.children?.[0];
    if (fxInput && ["input", "textarea"].includes(fxInput.name) && !["checkbox", "radio"].includes(fxInput.attributes.type)) {
      const hAlign = this.para?.hAlign;
      if (["center", "right", "justify"].includes(hAlign)) {
        fxInput.attributes.style = Object.assign(fxInput.attributes.style || {}, { textAlign: hAlign });
      }
      if (this.ui.textEdit?.comb || this.ui.numericEdit?.comb) {
        fxComb(this, ui, fxInput.attributes.value ?? fxInput.attributes.textContent ?? "");
      } else if (fxInput.name === "textarea" && ["middle", "bottom"].includes(this.para?.vAlign)) {
        // text pe mai multe rânduri centrat vertical (adresa din declarații): <textarea> îl lipește sus
        ui.children[0] = {
          name: "div",
          attributes: {
            class: ["xfaTextfield", "fxMultiline"].concat(fxInput.attributes.required ? ["fxRequired"] : []),
            style: Object.assign({}, fxInput.attributes.style, {
              display: "flex",
              flexDirection: "column",
              justifyContent: this.para.vAlign === "middle" ? "center" : "flex-end",
              whiteSpace: "pre-wrap",
              overflow: "hidden"
            })
          },
          children: [{ name: "div", attributes: {}, children: [{ name: "#text", value: fxInput.attributes.textContent ?? "" }] }]
        };
      }
    }
    if (fxInput?.name === "select" && !fxInput.attributes.multiple) {
      // listă derulantă: pe hârtie (și în Adobe) se vede doar valoarea aleasă, așezată după para din șablon
      const chosen = (fxInput.children || []).find(o => o.attributes?.selected);
      const shown = chosen?.value?.trim() ? chosen.value : this.value?.[$text]() || "";
      const hAlign = this.para?.hAlign;
      const vAlign = this.para?.vAlign;
      ui.children[0] = {
        name: "div",
        attributes: {
          class: ["xfaTextfield", "fxChoice"].concat(fxInput.attributes.required ? ["fxRequired"] : []),
          style: Object.assign({}, fxInput.attributes.style, {
            display: "flex",
            alignItems: vAlign === "top" ? "flex-start" : vAlign === "bottom" ? "flex-end" : "center",
            justifyContent: hAlign === "center" ? "center" : hAlign === "right" ? "flex-end" : "flex-start",
            overflow: "hidden",
            whiteSpace: "nowrap"
          })
        },
        children: shown ? [{ name: "#text", value: shown }] : []
      };
    }
    if (this.ui.checkButton && fxInput?.name === "input") {
      ui.children[0] = fxCheckBox(this.ui.checkButton, fxInput);
    }
    if (!this.ui.imageEdit && ui.children?.[0] && this.h) {
      borderDims = borderDims || getBorderDims(this.ui[$getExtra]());"""),
    # 4. grupul de opțiuni obligatoriu primește conturul roșu, ca în Adobe (bifele lui nu mai sunt <input required>)
    ("""    const classNames = ["xfaExclgroup"];""",
     """    const classNames = ["xfaExclgroup"].concat(isRequired(this) ? ["fxRequired"] : []);"""),
    # 5. câmpul de semnătură („Semnătura” din declarații) se desenează: chenarul lui și textul de sub el
    ("""    this.manifest = null;
    this.margin = null;
  }
}
class Signing extends XFAObject {""",
     """    this.manifest = null;
    this.margin = null;
  }
  [$toHTML](availableSpace) {
    const style = toStyle(this, "border", "margin");
    return HTMLResult.success({
      name: "label",
      attributes: {
        class: ["xfaLabel"]
      },
      children: [{
        name: "div",
        attributes: {
          class: ["xfaTextfield", "fxSignature"],
          style
        },
        children: []
      }]
    });
  }
}
class Signing extends XFAObject {"""),
    # 6. câmp cu înălțime/lățime după conținut: layoutNode întoarce mărimea cu marginile câmpului incluse, iar Field le
    #    mai adună o dată (rândurile tabelelor ieșeau cu ~50% mai înalte decât în Adobe și paginile se rupeau altfel)
    ("""        const {
          w,
          h
        } = layoutNode(this, availableSpace);
        if (w !== null) {
          uiW = w;
          uiH = h;
        } else {""",
     """        const {
          w,
          h
        } = layoutNode(this, availableSpace);
        if (w !== null) {
          uiW = this.w === "" ? w - marginH : w;
          uiH = this.h === "" ? h - marginV : h;
        } else {"""),
    # 7. fonturile la mărimea din șablon, ca în Adobe: pdf.js le micșora la 99%, iar textele care la Adobe nu încap pe
    #    un rând încăpeau la limită (D301: „…intracomunitare de mijloace” intra sub butonul „?” în loc să se rupă)
    ("""    style.fontSize = measureToString(0.99 * this.size);""",
     """    style.fontSize = measureToString(this.size);"""),
    ("""  return measureToString(0.99 * value);
}], ["letter-spacing",""",
     """  return measureToString(value);
}], ["letter-spacing","""),
    # 8. sigla BMP a ANAF
    ("""    if (!buffer && this.transferEncoding === "base64") {
      buffer = fromBase64Util(this[$content]);
    }""",
     """    if (!buffer && this.transferEncoding === "base64") {
      buffer = fromBase64Util(this[$content]);
    }
    if (buffer) {
      buffer = fxFixBmp(buffer);
    }"""),
    # 9. o semnătură VIZIBILĂ pe un formular XFA dinamic nu-l face formular AcroForm: Acrobat desenează tot formularul
    #    și pune semnătura în câmpul ei; pdf.js renunța la XFA (rămânea pagina „Please wait…”)
    ("""      const isInvisible = Array.isArray(rectangle) && rectangle.every(value => value === 0);
      return isSignature && isInvisible;""",
     """      const isInvisible = Array.isArray(rectangle) && rectangle.every(value => value === 0);
      return isSignature && (isInvisible || this.catalog.needsRendering);"""),
]


def main(pkg: Path):
    build = pkg / "build"
    if f'"version": "{VERSION}"' not in (pkg / "package.json").read_text(encoding="utf-8"):
        sys.exit(f"Trebuie pdfjs-dist {VERSION}: corecturile sunt scrise pe codul acestei versiuni.")
    src = (build / "pdf.worker.mjs").read_text(encoding="utf-8")
    for i, (old, new) in enumerate(PATCHES):
        n = src.count(old)
        if n != 1:
            sys.exit(f"Corectura {i}: textul căutat apare de {n} ori în pdf.worker.mjs (trebuie o dată).")
        src = src.replace(old, new)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pdf.worker.mjs").write_text(src, encoding="utf-8", newline="\n")
    shutil.copy2(build / "pdf.min.mjs", OUT / "pdf.min.mjs")
    shutil.copytree(pkg / "standard_fonts", OUT / "standard_fonts", dirs_exist_ok=True)
    (OUT / "pdf.worker.min.mjs").unlink(missing_ok=True)
    print(f"pdf.js {VERSION} cu {len(PATCHES)} corecturi XFA -> {OUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "package").resolve())
