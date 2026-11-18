"""Fișierele de test, făcute pe loc (nimic din ele nu e real): PDF-uri, imagini, documente Office și două certificate
de test (.pfx, RSA și ECDSA P-384 ca buletinul electronic). Nu ating certificatele din Windows.

  python tests/make_fixtures.py FOLDER
"""
import datetime
import sys
from pathlib import Path

import fitz

PFX_PASS = "test-1234"
TEXT = ("Contract de prestări servicii nr. 42 din 18.11.2026. Șeful țării vrea înghețată. "
        "Beneficiar: TEST SRL, CUI 12345678, IBAN RO49AAAA1B31007593840000. ")


def pdf(path: Path, pages: int = 3, table: bool = False, blank_at: int = 0):
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        if blank_at and i + 1 == blank_at:
            continue
        page.insert_text((60, 80), f"Pagina {i + 1} din {pages}", fontsize=18, fontname="helv")
        page.insert_textbox(fitz.Rect(60, 110, 535, 400), (TEXT * 6), fontsize=11, fontname="helv")
        if table and i == 0:
            y = 420
            rows = [("Nr.", "Denumire", "Cantitate", "Pret"), ("1", "Servicii contabilitate", "1", "1.250,00"),
                    ("2", "Consultanta fiscala", "3", "450,50"), ("3", "Salarizare", "12", "99,90")]
            for r in rows:
                for k, cell in enumerate(r):
                    x = 60 + k * 120
                    page.draw_rect(fitz.Rect(x, y, x + 120, y + 24), color=(0, 0, 0), width=0.7)
                    page.insert_text((x + 5, y + 16), cell, fontsize=10, fontname="helv")
                y += 24
    doc.save(str(path))
    doc.close()


def form_pdf(path: Path):
    """Formular cu două câmpuri de text, o bifă și un câmp de semnătură gol (ca declarațiile)."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "Formular de test", fontsize=18, fontname="helv")
    for k, (name, y) in enumerate((("nume", 130), ("cui", 170))):
        w = fitz.Widget()
        w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        w.field_name = name
        w.rect = fitz.Rect(160, y, 420, y + 22)
        w.field_value = ""
        page.add_widget(w)
        page.insert_text((60, y + 15), name.upper(), fontsize=11, fontname="helv")
    w = fitz.Widget()
    w.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    w.field_name = "acord"
    w.rect = fitz.Rect(160, 210, 176, 226)
    page.add_widget(w)
    w = fitz.Widget()
    w.field_type = fitz.PDF_WIDGET_TYPE_SIGNATURE
    w.field_name = "Semnatura"
    w.rect = fitz.Rect(320, 700, 520, 770)
    page.add_widget(w)
    doc.save(str(path))
    doc.close()


def images(folder: Path):
    from PIL import Image, ImageDraw
    out = []
    for i, color in enumerate(((235, 240, 255), (255, 244, 230))):
        im = Image.new("RGB", (900, 1200), color)
        d = ImageDraw.Draw(im)
        d.rectangle((60, 60, 840, 300), outline=(20, 40, 120), width=6)
        d.text((90, 150), f"Scanare de test {i + 1}", fill=(20, 40, 120))
        p = folder / f"scan{i + 1}.jpg"
        im.save(p, quality=88)
        out.append(p)
    # semnătură „pe hârtie”: cerneală albastră pe alb
    im = Image.new("RGB", (700, 260), (250, 250, 247))
    d = ImageDraw.Draw(im)
    pts = [(60, 180), (120, 60), (170, 190), (230, 80), (300, 170), (380, 90), (460, 175), (560, 110), (640, 150)]
    d.line(pts, fill=(25, 45, 140), width=7, joint="curve")
    d.line([(80, 215), (620, 200)], fill=(25, 45, 140), width=4)
    sig = folder / "semnatura-hartie.jpg"
    im.save(sig, quality=90)
    return out, sig


def office(folder: Path):
    from docx import Document
    from openpyxl import Workbook
    d = Document()
    d.add_heading("Document de test", 1)
    d.add_paragraph("Șeful țării vrea înghețată. Rând de test cu diacritice: ă î â ș ț.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text, t.cell(1, 0).text, t.cell(1, 1).text = "A", "B", "1", "2"
    docx = folder / "document.docx"
    d.save(docx)
    wb = Workbook()
    ws = wb.active
    ws.append(["Denumire", "Suma"])
    ws.append(["Servicii", 1250.5])
    ws.append(["Total", "=B2"])
    xlsx = folder / "tabel.xlsx"
    wb.save(xlsx)
    return docx, xlsx


def pfx(path: Path, kind: str):
    """Certificat de test autosemnat, cu non-repudiere, ca unul de semnătură."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID
    key = ec.generate_private_key(ec.SECP384R1()) if kind == "ec" else rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"TEST SEMNATAR {kind.upper()}"),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PDF Sign - certificat de test"),
                      x509.NameAttribute(NameOID.COUNTRY_NAME, "RO")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False,
                                         encipher_only=False, decipher_only=False), critical=True)
            .sign(key, hashes.SHA384() if kind == "ec" else hashes.SHA256()))
    path.write_bytes(pkcs12.serialize_key_and_certificates(b"test", key, cert, None,
                                                            serialization.BestAvailableEncryption(PFX_PASS.encode())))


def make(folder: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    f = {"dir": folder}
    f["doc"] = folder / "contract.pdf"
    pdf(f["doc"], 3, table=True)
    f["doc2"] = folder / "anexa.pdf"
    pdf(f["doc2"], 2)
    f["blank"] = folder / "cu-pagina-goala.pdf"
    pdf(f["blank"], 3, blank_at=2)
    f["form"] = folder / "formular.pdf"
    form_pdf(f["form"])
    f["images"], f["sigphoto"] = images(folder)
    f["docx"], f["xlsx"] = office(folder)
    f["pfx_rsa"] = folder / "test-rsa.pfx"
    pfx(f["pfx_rsa"], "rsa")
    f["pfx_ec"] = folder / "test-ec384.pfx"
    pfx(f["pfx_ec"], "ec")
    (folder / "pagina.html").write_text("<html><body><h1>Test HTML</h1><p>Șeful țării.</p></body></html>", encoding="utf-8")
    (folder / "nota.md").write_text("# Test Markdown\n\nUn rând **îngroșat** și o listă:\n\n- unu\n- doi\n", encoding="utf-8")
    return f


if __name__ == "__main__":
    out = make(Path(sys.argv[1]))
    for k, v in out.items():
        print(k, v)
