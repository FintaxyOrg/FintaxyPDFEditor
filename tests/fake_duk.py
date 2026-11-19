"""Ține loc de Java + DUKIntegrator la teste (FX_ANAF_JAVA): aceeași linie de comandă, aceleași mesaje și fișiere ca
programul ANAF, fără Java și fără internet. Regulile lui sunt inventate, doar cât să acopere drumurile aplicației:

  XML stricat                -> „Erori la validare fisier; cod eroare=-5”
  atributul cui="123"        -> eroare (E:), fișierul de erori ca al validatorului
  spațiu de nume greșit      -> eroare de structură (F:)
  atributul atentie="1"      -> atenționare (A:), dar valid
  altfel                     -> „Validare fara erori fisier”; cu -p face și PDF-ul, cu XML-ul atașat
  -v pe un .pdf              -> verificarea PDF-ului: semnat / nesemnat / cheie ECDSA necunoscută bibliotecii vechi

  python fake_duk.py [opțiuni java] -jar DUKIntegrator.jar -v|-p TIP fisier [erori] [optiune] [zip] [pdf]
"""
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz

sys.stdout.reconfigure(encoding="utf-8", newline="\r\n")
args = sys.argv[1:]
args = args[args.index("-jar") + 2:]
mode, decl, src = args[0], args[1], Path(args[2])
err_arg = args[3] if len(args) > 3 else "$"
prefix = err_arg[0] if err_arg[:1] in "+!" else ""
err_arg = err_arg[len(prefix):]
err = Path(str(src) + ".err.txt") if err_arg in ("", "$") else Path(err_arg)
pdf = Path(args[6]) if len(args) > 6 and args[6] != "$" else src.with_suffix(".pdf")
NS = f"mfp:anaf:dgti:{decl.lower()}:declaratie:v1"


def write_err(text: str, append: bool = False):
    with open(err, "ab" if append else "wb") as f:
        f.write(text.replace("\n", "\r\n").encode("utf-8"))


print("1.")
if src.suffix.lower() == ".pdf":
    with fitz.open(str(src)) as doc:
        raw = src.read_bytes()
        signed = doc.get_sigflags() == 3
    print(f"     a. Verificare PDF: {src}")
    if not signed:
        print("Atentionare semnatura PDF: Pdf-ul nu este semnat. Documentul nu poate fi transmis prin internet")
    elif b"2a8648ce3d0403" in raw.lower():  # semnătură ECDSA (OID-ul ei, în conținutul scris în hex)
        print("Eroare semnatura PDF:  Eroare verificare semnatura: ExceptionConverter: java.security.NoSuchAlgorithmException: "
              "SHA384with1.2.840.10045.4.3.3 Signature not available")
    else:
        print("Validare fara erori fisier PDF ")
    print("     b. Validare XML:")
    print(f"Validare fara erori fisier: {src}.dukintegrator.xml")
    print("     c. Verificare PDF vs. XML:")
    print("Valorile metadatelor din PDF corespund cu valorile din XML")
    write_err("ok")
    sys.exit(0)

try:
    root = ET.fromstring(src.read_bytes())
except ET.ParseError:
    print("Erori la validare fisier; cod eroare=-5")
    sys.exit(0)
ns = re.match(r"\{(.*?)\}", root.tag)
if not ns or ns.group(1) != NS:
    write_err("F: validari globale\n va rugam sa verificati daca folositi versiunea corecta de PDF inteligent\n"
              f" eroare structura: namespace ('{ns.group(1) if ns else ''}') lipsa sau incorect la sectiunea {root.tag.split('}')[-1]}. "
              f"Valoarea corecta este xmlns='{NS}'\n")
    print(f"Erori la validare fisier: {src}\n       Erorile au fost scrise in fisierul: {err}")
    sys.exit(0)
if root.get("cui") == "123":
    write_err("E: validari globale\n eroare atribut: cui: CUI invalid ('123')\n")
    print(f"Erori la validare fisier: {src}\n       Erorile au fost scrise in fisierul: {err}")
    sys.exit(0)
warn = root.get("atentie") == "1"
if warn:
    write_err("A: sectiunea rezumat\n atentionare: suma de control este 0\n")
    print(f"Atentionari la validare fisier: {src}\n       Atentionarile au fost scrise in fisierul: {err}")
else:
    print(f"Validare fara erori fisier: {src}")
if mode == "-p":
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), f"Declaratia {decl} (test)", fontsize=16, fontname="helv")
    page.insert_text((60, 110), f"cui {root.get('cui')}  luna {root.get('luna')}  an {root.get('an')}", fontsize=11, fontname="helv")
    doc.embfile_add("XML", src.read_bytes(), filename=f"{decl}.xml")
    doc.set_metadata({"producer": "iText 5.0.4 (test)"})
    doc.save(str(pdf))
    doc.close()
    print(f"Fisierul PDF a fost creat cu succes:\n       {pdf}")
if mode == "-v" or not warn:
    if not warn:
        write_err("ok")
elif prefix == "+":
    write_err("\nok", append=True)
