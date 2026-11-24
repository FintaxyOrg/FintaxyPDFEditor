"""Semnătura electronică (calificată) cu un certificat din Windows: buletinul electronic, un token, stick-ul din
birou prin FintaxySign. Fără Stirling și fără Java.

pyHanko scrie semnătura în PDF (PAdES, actualizare incrementală: ce era în fișier rămâne, inclusiv formularul XFA,
XML-ul atașat al declarațiilor ANAF și semnăturile de dinainte), iar Windows semnează hash-ul cu cheia certificatului
(CNG: Smart Card Key Storage Provider; acolo stau cheile cardurilor și ale cititorului virtual FintaxySign) și cere
PIN-ul în fereastra lui. Un singur proces PowerShell ține cheia deschisă pentru toate fișierele, deci la semnarea
în bloc PIN-ul se cere o dată.
"""
import base64
import datetime
import hashlib
import io
import json
import os
import shutil
import subprocess
import threading
import time
import unicodedata
from pathlib import Path

import fitz
from asn1crypto import algos, x509
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import fields, signers
from pyhanko.stamp import TextStampStyle
from pyhanko_certvalidator.registry import SimpleCertificateStore

import fx_sign
import winenv
import xfasign
import xfaview

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ---------- certificatele ----------

LIST_PS = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$now = Get-Date
@(Get-ChildItem Cert:\CurrentUser\My | Where-Object HasPrivateKey | ForEach-Object {
  $ku = $_.Extensions | Where-Object { $_ -is [Security.Cryptography.X509Certificates.X509KeyUsageExtension] }
  $eku = $_.Extensions | Where-Object { $_ -is [Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension] }
  $usages = if ($ku) { [string]$ku.KeyUsages } else { '' }
  $ekus = if ($eku) { @($eku.EnhancedKeyUsages | ForEach-Object { $_.Value }) } else { @() }
  [pscustomobject]@{
    thumb = $_.Thumbprint
    name = $_.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)
    issuer = $_.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $true)
    friendly = $_.FriendlyName
    notAfter = $_.NotAfter.ToString('yyyy-MM-dd')
    expired = $_.NotAfter -lt $now
    nonRepudiation = $usages -match 'NonRepudiation'
    digitalSignature = $usages -match 'DigitalSignature'
    clientAuthOnly = ($ekus.Count -gt 0) -and -not ($ekus -contains '1.3.6.1.5.5.7.3.4' -or $ekus -contains '1.3.6.1.4.1.311.10.3.12' -or $ekus -contains '1.2.840.113583.1.1.5')
  } }) | ConvertTo-Json -Compress
"""


SOURCES = {
    "fintaxysign": "Stick birou (FintaxySign)",
    "cei": "Buletin electronic",
    "token": "Token / card",
    "pc": "Pe calculator",
}
PIN_HINTS = {
    "cei": "Windows cere PIN-ul de SEMNARE al buletinului (6 cifre), nu pe cel de 4 cifre. După 3 PIN-uri greșite buletinul se blochează.",
    "fintaxysign": "Windows cere PIN-ul stick-ului din birou. Dacă stick-ul e la un coleg, aștepți câteva secunde rândul.",
    "token": "Windows cere PIN-ul tokenului.",
    "pc": "",
}
def source_of(issuer: str, key: dict, guess_stick: bool = False) -> str:
    if winenv.is_virtual_reader(key.get("reader", "")):
        return "fintaxysign"
    if "RO CEI" in (issuer or "").upper():
        return "cei"
    if key.get("smartcard") and not key.get("reader") and guess_stick:
        return "fintaxysign"  # stick-ul încă n-a răspuns, dar e singurul card care poate ține cheia asta
    return "token" if key.get("smartcard") else "pc"


def _native_certs() -> list:
    """Certificatele citite direct din Windows (instant), în aceeași formă ca lista din PowerShell."""
    import datetime
    certs = []
    raw = winenv.store_certs()
    for r in raw:
        c = x509.Certificate.load(r["der"])
        usages = c.key_usage_value.native if c.key_usage_value else set()
        ekus = set(c.extended_key_usage_value.native) if c.extended_key_usage_value else set()
        after = c["tbs_certificate"]["validity"]["not_after"].native
        certs.append({
            "thumb": r["thumb"], "name": c.subject.native.get("common_name") or c.subject.human_friendly,
            "issuer": c.issuer.native.get("common_name") or c.issuer.human_friendly, "friendly": r["friendly"],
            "notAfter": after.astimezone().strftime("%Y-%m-%d"), "expired": after < datetime.datetime.now(datetime.timezone.utc),
            "nonRepudiation": "non_repudiation" in usages, "digitalSignature": "digital_signature" in usages,
            # doar pentru autentificare (fără semnarea documentelor / emailului)
            "clientAuthOnly": bool(ekus) and not (ekus & {"email_protection", "microsoft_document_signing", "1.3.6.1.4.1.311.10.3.12",
                                                           "1.2.840.113583.1.1.5", "adobe_authentic_documents_trust"}),
        })
    return certs, raw


def list_certs(fresh: bool = False) -> list:
    """Certificatele cu cheie privată din Windows, cele bune de semnat primele (non-repudiere, în termen, conectate).
    Fiecare spune de unde vine (buletin, stick prin FintaxySign, token) și ce PIN cere."""
    src = {}
    try:
        # Întâi aducem în Windows certificatele de pe carduri pe care Windows nu le-a pus singur (stick-ul FintaxySign,
        # al doilea certificat de pe card). La „Reîncarcă” așteptăm stick-ul; altfel doar puțin, restul în fundal.
        winenv.sync_card_certs(wait=8.0 if fresh else 2.5, fresh=fresh)
    except Exception:
        pass
    try:
        certs, raw = _native_certs()
        src = winenv.key_sources(raw, wait=6.0 if fresh else 2.5, fresh=fresh)
    except Exception:
        # Varianta veche, prin PowerShell (~3 s), dacă citirea directă nu merge pe calculatorul ăsta.
        r = subprocess.run(["powershell", "-NoProfile", "-Command", LIST_PS], capture_output=True, timeout=60,
                           creationflags=NO_WINDOW)
        data = json.loads(r.stdout.decode("utf-8", "replace").strip() or "[]")
        certs = data if isinstance(data, list) else [data]
    # Până răspunde stick-ul de la distanță: dacă FintaxySign are stick-ul conectat și singurul alt card din
    # cititoare e buletinul, certificatele de pe card care nu sunt ale buletinului nu pot fi decât pe stick.
    guess = False
    try:
        rd = winenv.readers()
        physical = sum(1 for r in rd if r["card"] and not winenv.is_virtual_reader(r["name"]))
        has_cei = any("RO CEI" in (c.get("issuer") or "").upper() for c in certs)
        guess = any(r["card"] for r in rd if winenv.is_virtual_reader(r["name"])) and physical <= (1 if has_cei else 0)
    except Exception:
        pass
    for c in certs:
        # Buletinul electronic are două certificate: „(Semnare)” și „(Autentificare)”; doar primul e pentru semnat.
        label = c.get("friendly") or c["name"]
        key = src.get(c["thumb"].upper(), {})
        c["signing"] = bool(c.get("nonRepudiation")) or "semnare" in label.lower()
        c["source"] = source_of(c.get("issuer", ""), key, guess)
        c["sourceName"] = SOURCES[c["source"]]
        c["reader"] = key.get("reader", "")
        c["pending"] = bool(key.get("pending"))  # stick-ul de la distanță încă n-a răspuns: editorul mai întreabă o dată
        c["absent"] = bool(key) and not c["pending"] and not key.get("present", True)
        c["pinHint"] = PIN_HINTS[c["source"]]
        c["label"] = (f"{c['sourceName']} · {label} · până la {c['notAfter']}" + (" · EXPIRAT" if c.get("expired") else "")
                      + (" · NECONECTAT" if c["absent"] and not c.get("expired") else ""))
    certs.sort(key=lambda c: (bool(c.get("expired")), c["absent"], not c["signing"], bool(c.get("clientAuthOnly")), c["label"].lower()))
    return certs


# ---------- cheia, prin Windows ----------

SIGN_PS = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Security
try {
  if ($env:FX_PFX) {
    # doar pentru teste: un certificat dintr-un fișier .pfx în loc de cel din Windows
    $c = New-Object Security.Cryptography.X509Certificates.X509Certificate2($env:FX_PFX, $env:FX_PFX_PASS,
         [Security.Cryptography.X509Certificates.X509KeyStorageFlags]::EphemeralKeySet)
  } else {
    $c = Get-Item -LiteralPath ("Cert:\CurrentUser\My\" + $env:FX_THUMB)
  }
  "CERT " + [Convert]::ToBase64String($c.RawData)
  $ch = New-Object Security.Cryptography.X509Certificates.X509Chain
  $ch.ChainPolicy.RevocationMode = 'NoCheck'
  $ch.ChainPolicy.VerificationFlags = 'AllFlags'
  [void]$ch.Build($c)
  foreach ($e in $ch.ChainElements) {
    if ($e.Certificate.Thumbprint -ne $c.Thumbprint) { "CHAIN " + [Convert]::ToBase64String($e.Certificate.RawData) }
  }
  $rsa = [Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($c)
  $ec = $null
  if (-not $rsa) { $ec = [Security.Cryptography.X509Certificates.ECDsaCertificateExtensions]::GetECDsaPrivateKey($c) }
  if (-not $rsa -and -not $ec) { throw 'Certificatul nu are o cheie privată pe care Windows s-o poată folosi.' }
  $key = if ($rsa) { $rsa } else { $ec }
  # Fereastra de PIN apare deasupra editorului: părintele e fereastra editorului, aleasă și verificată de aplicație
  # (FX_HWND). Fără părinte bun nu punem niciunul: legată de o fereastră invizibilă, fereastra de PIN rămâne ascunsă.
  if ($env:FX_HWND -and $env:FX_HWND -ne '0' -and ($key -is [Security.Cryptography.RSACng] -or $key -is [Security.Cryptography.ECDsaCng])) {
    try { $key.Key.ParentWindowHandle = [IntPtr][int64]$env:FX_HWND } catch {}
  }
  "READY " + $(if ($rsa) { 'rsa' } else { 'ecdsa' })
} catch {
  $b = $_.Exception.GetBaseException()
  "ERR " + ('{0:X8}' -f $b.HResult) + " " + ($b.Message -replace '\s+', ' ')
  exit 1
}
while ($null -ne ($line = [Console]::In.ReadLine())) {
  if (-not $line) { continue }
  try {
    $p = $line.Split(' ')
    $hash = [Convert]::FromBase64String($p[2])
    if ($rsa) {
      $sig = $rsa.SignHash($hash, (New-Object Security.Cryptography.HashAlgorithmName($p[1])), [Security.Cryptography.RSASignaturePadding]::Pkcs1)
    } else {
      $sig = $ec.SignHash($hash)
    }
    "OK " + [Convert]::ToBase64String($sig)
  } catch {
    $b = $_.Exception.GetBaseException()
    "ERR " + ('{0:X8}' -f $b.HResult) + " " + ($b.Message -replace '\s+', ' ')
  }
}
"""


class SignStop(RuntimeError):
    """Semnarea trebuie oprită cu totul (PIN greșit, card blocat, anulare): nu se mai încearcă pe fișierul următor."""


# Codurile Windows care contează la semnare, pe înțelesul omului.
ERRORS = {
    "8010006B": "PIN greșit. Nu mai încerca dacă nu ești sigur de el: după 3 PIN-uri greșite la rând cardul se blochează.",
    "8010006C": "Cardul e blocat: s-au introdus prea multe PIN-uri greșite. Se deblochează cu codul PUK.",
    "8010006E": "Semnarea a fost anulată (fereastra de PIN închisă).",
    "80100002": "Semnarea a fost anulată.",
    "800704C7": "Semnarea a fost anulată (fereastra de PIN închisă).",
    "8010000C": "Cardul nu e în cititor (sau stick-ul nu e conectat în FintaxySign).",
    "80100069": "Cardul a fost scos din cititor în timpul semnării.",
    "80100010": "Cardul nu răspunde. Scoate-l și pune-l la loc (sau repornește FintaxySign), apoi încearcă din nou.",
    "8010001D": "Serviciul Windows pentru carduri nu e pornit. Repornește calculatorul.",
    "80090016": "Cheia certificatului nu e pe cardul din cititor. Verifică să fie cardul / stick-ul potrivit.",
    "8009000D": "Cheia certificatului nu e disponibilă. Verifică să fie cardul / stick-ul conectat.",
}


def explain(line: str):
    """„ERR <cod> <mesaj>” -> (mesaj pe românește, oprește tot?)."""
    body = line[4:].strip()
    code, _, msg = body.partition(" ")
    is_code = len(code) == 8 and all(ch in "0123456789abcdefABCDEF" for ch in code)
    if is_code and code.upper() in ERRORS:
        return ERRORS[code.upper()], True
    if not is_code:
        msg = body
    low = msg.lower()
    if "cancel" in low or "anulat" in low:
        return "Semnarea a fost anulată (fereastra de PIN închisă).", True
    return (f"{msg} (cod {code.upper()})" if is_code else msg), False


# O singură semnare o dată: două ferestre de PIN deschise pe același card se blochează una pe alta.
ACTIVE = {"key": None, "phase": "", "since": 0.0, "dialog": "", "file": "", "done": 0, "total": 0}
BUSY = threading.Lock()


def status() -> dict:
    """Ce se întâmplă acum cu semnarea, pentru editor: se deschide cheia / se așteaptă PIN-ul / se semnează."""
    on = ACTIVE["key"] is not None
    return {"active": on, "phase": ACTIVE["phase"], "seconds": round(time.time() - ACTIVE["since"], 1) if on else 0,
            "dialog": ACTIVE["dialog"], "file": ACTIVE["file"], "done": ACTIVE["done"], "total": ACTIVE["total"]}


def cancel() -> bool:
    """Oprește semnarea în curs (închide și fereastra de PIN)."""
    k = ACTIVE["key"]
    if not isinstance(k, WinKey):
        return False
    k.cancelled = True
    k.kill()
    return True


class WinKey:
    """Cheia unui certificat din Windows, ținută deschisă într-un proces PowerShell cât durează semnarea."""

    def __init__(self, thumb: str, pfx: str = "", pfx_pass: str = "", hwnd: int = 0):
        # Testele aplicației împachetate dau un .pfx prin mediu (FX_TEST_PFX), fără certificat în Windows.
        pfx = pfx or os.environ.get("FX_TEST_PFX", "")
        pfx_pass = pfx_pass or os.environ.get("FX_TEST_PFX_PASS", "")
        env = {**os.environ, "FX_THUMB": "".join(ch for ch in thumb if ch.isalnum()), "FX_PFX": pfx, "FX_PFX_PASS": pfx_pass,
               "FX_HWND": str(int(hwnd or 0))}
        self.cancelled = False
        self.hwnd = int(hwnd or 0)
        self.lock = threading.Lock()
        self.cert = None
        self.chain = []
        self.kind = ""
        self.proc = subprocess.Popen(["powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", SIGN_PS],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                                     creationflags=NO_WINDOW, text=True, encoding="utf-8", errors="replace")
        ACTIVE.update(key=self, phase="open", since=time.time(), dialog="")
        while True:
            line = self._read(60, "Windows nu a putut deschide cheia certificatului în 60 de secunde. Verifică să fie cardul în "
                                  "cititor (sau stick-ul conectat în FintaxySign) și încearcă din nou.")
            if line.startswith("CERT "):
                self.cert = x509.Certificate.load(base64.b64decode(line[5:]))
            elif line.startswith("CHAIN "):
                self.chain.append(x509.Certificate.load(base64.b64decode(line[6:])))
            elif line.startswith("READY "):
                self.kind = line[6:].strip()
                return
            elif line.startswith("ERR "):
                self.close()
                raise SignStop(explain(line)[0])

    @property
    def digest(self) -> str:
        """Algoritmul de hash potrivit cheii: cardurile cu chei P-384 (buletinul electronic) semnează SHA-384."""
        if self.kind == "ecdsa":
            bits = self.cert.public_key.bit_size
            return "sha512" if bits > 384 else "sha384" if bits > 256 else "sha256"
        return "sha256"

    def _read(self, timeout: float, late: str = "", watch: bool = False) -> str:
        box = []
        t = threading.Thread(target=lambda: box.append(self.proc.stdout.readline()), daemon=True)
        t.start()
        end = time.time() + timeout
        fronted = 0
        while t.is_alive() and time.time() < end and not self.cancelled:
            t.join(0.4)
            if not watch or not t.is_alive():
                continue
            # Fereastra de PIN: o aducem în față dacă a rămas în spatele altei ferestre și spunem editorului ce vede omul.
            d = winenv.pin_dialog()
            if d:
                if ACTIVE["phase"] != "pin":
                    ACTIVE.update(phase="pin", since=time.time())
                ACTIVE["dialog"] = "hidden" if d["hidden"] else "visible"
                if not d["hidden"] and fronted < 3 and winenv.user32.GetForegroundWindow() != d["hwnd"]:
                    fronted += 1
                    winenv.bring_to_front(d["hwnd"])
            elif ACTIVE["phase"] == "pin":
                ACTIVE.update(phase="sign", since=time.time(), dialog="")  # PIN-ul a fost scris: cardul semnează
        if self.cancelled:
            raise SignStop("Semnarea a fost anulată.")
        if not box:
            self.kill()
            raise SignStop(late or "Windows nu a răspuns la timp (fereastra de PIN a rămas deschisă?).")
        if not box[0]:
            err = (self.proc.stderr.read() or "").strip().splitlines()
            raise SignStop(err[-1] if err else "Procesul de semnare s-a oprit.")
        return box[0].strip()

    def sign_hash(self, algo: str, digest: bytes) -> bytes:
        with self.lock:
            self.proc.stdin.write(f"SIGN {algo.upper()} {base64.b64encode(digest).decode()}\n")
            self.proc.stdin.flush()
            ACTIVE.update(phase="wait", since=time.time(), dialog="")
            # Cât timp omul scrie PIN-ul sau un coleg are stick-ul (FintaxySign așteaptă rândul), răspunsul întârzie.
            line = self._read(300, "Nu a venit niciun răspuns în 5 minute. Dacă fereastra de PIN nu a apărut, repornește "
                                   "PDF Sign și încearcă din nou.", watch=True)
        if line.startswith("ERR "):
            msg, stop = explain(line)
            raise (SignStop if stop else RuntimeError)(msg)
        sig = base64.b64decode(line[3:])
        if self.kind == "ecdsa":  # Windows dă r||s; în CMS semnătura ECDSA e DER
            sig = algos.DSASignature.from_p1363(sig).dump()
        return sig

    def kill(self):
        """Oprește procesul cu totul: fereastra de PIN deschisă de el se închide și ea."""
        try:
            subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW,
                           timeout=10)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(5)
        except Exception:
            self.kill()


class WinSigner(signers.Signer):
    def __init__(self, key: WinKey):
        super().__init__(signing_cert=key.cert, cert_registry=SimpleCertificateStore.from_certs(key.chain),
                         embed_roots=False)
        self.key = key

    async def async_sign_raw(self, data: bytes, digest_algorithm: str, dry_run=False) -> bytes:
        if dry_run:  # doar mărimea: cât ocupă semnătura în PDF
            n = (self.key.cert.public_key.bit_size + 7) // 8
            return bytes(n if self.key.kind == "rsa" else 2 * n + 9)
        return self.key.sign_hash(digest_algorithm, hashlib.new(digest_algorithm, data).digest())


# ---------- PDF-ul ----------

def plain(s: str) -> str:
    """Ștampila folosește fontul standard (fără diacritice); numele adevărat e în certificat."""
    s = s.replace("ș", "s").replace("ş", "s").replace("ț", "t").replace("ţ", "t").replace("Ș", "S").replace("Ş", "S")
    s = s.replace("Ț", "T").replace("Ţ", "T")
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


signature_fields = fx_sign.signature_fields
# PyMuPDF nu e sigur pe mai multe fire: serverul editorului pune aici lacătul lui.
FITZ_LOCK = threading.RLock()


def output_for(pdf: Path) -> Path:
    stem = pdf.stem
    if stem.lower().endswith("_semnat"):
        return pdf  # o semnătură în plus pe copia semnată: se adaugă în același fișier
    return pdf.with_name(f"{stem}_semnat.pdf")


def sign_pdf(signer: WinSigner, pdf: str, place: dict | None = None, reason: str = "", location: str = "") -> str:
    """Semnează un PDF. place: {"field": nume} = câmpul de semnătură existent;
    {"page": n, "rect": [x0, y0, x1, y1]} = semnătură vizibilă nouă (pt, pagina cum se vede);
    {"xfa": nume SOM} = caseta de semnătură a unui formular XFA dinamic (ANAF), ca în Acrobat; None = invizibilă."""
    src = Path(pdf)
    data = src.read_bytes()
    xfa_rect = None
    if place and place.get("xfa"):
        xfa_name = place["xfa"]
        with FITZ_LOCK, fitz.open(stream=data, filetype="pdf") as doc:
            if any(f["name"] == xfa_name and f["signed"] for f in signature_fields(doc)):
                raise ValueError("Caseta de semnătură a formularului e deja semnată.")
            names = [f["name"] for f in xfasign.fields(doc)]
            existing = {f["name"] for f in signature_fields(doc)}
        if xfa_name not in names:
            raise ValueError("Formularul nu are caseta de semnătură cerută.")
        if xfa_name in existing:  # câmpul există deja (ex. pus de Acrobat, gol): semnăm în el
            place = {"field": xfa_name}
        else:
            got = xfasign.rect_for(str(src), names.index(xfa_name))
            if not got:
                raise ValueError("Formularul nu a putut fi desenat, deci nu știu unde e caseta de semnătură. "
                                 "Semnează invizibil sau încearcă din nou.")
            xfa_rect = got[1]
    with FITZ_LOCK, fitz.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass:
            raise ValueError("PDF-ul are parolă; scoate-o întâi.")
        existing = signature_fields(doc)
        new_spec = None
        field = None
        acrobat_size = None  # (lățime, înălțime): semnătură în caseta unui formular XFA -> aspectul ca la Acrobat
        if xfa_rect is not None:
            field = place["xfa"]
            acrobat_size = (xfa_rect[2] - xfa_rect[0], xfa_rect[3] - xfa_rect[1])
        elif place and place.get("field"):
            field = place["field"]
            if any(f["name"] == field and f["signed"] for f in existing):
                raise ValueError(f"Câmpul „{field}” e deja semnat.")
            # câmpul există deja (pus de Acrobat sau de o pregătire a declarației) și e caseta de semnătură a
            # formularului XFA: același aspect ca atunci când îl creăm noi
            if xfaview.needs(doc) and field in {g["name"] for g in xfasign.fields(doc)}:
                f0 = next((f for f in existing if f["name"] == field), None)
                if f0 and f0.get("rect"):
                    r0 = f0["rect"]
                    acrobat_size = (r0[2] - r0[0], r0[3] - r0[1])
        else:
            taken = {f["name"] for f in existing}
            field = next(f"Semnatura{k}" for k in range(1, 999) if f"Semnatura{k}" not in taken)
            if place and place.get("page"):
                page = doc[int(place["page"]) - 1]
                # din pagina cum se vede (rotită) în coordonatele PDF (origine jos-stânga), cum le vrea pyHanko
                r = fitz.Rect(place["rect"]) * page.derotation_matrix
                mb = page.mediabox
                box = (r.x0 + mb.x0, mb.y1 - r.y1, r.x1 + mb.x0, mb.y1 - r.y0)
                new_spec = fields.SigFieldSpec(field, on_page=page.number, box=tuple(round(v, 2) for v in box))
            else:
                new_spec = fields.SigFieldSpec(field)  # invizibilă
    name = signer.key.cert.subject.native.get("common_name", "")
    meta = signers.PdfSignatureMetadata(field_name=field, md_algorithm=signer.key.digest, subfilter=fields.SigSeedSubFilter.PADES,
                                        reason=reason or None, location=location or None, name=name or None)
    style = TextStampStyle(stamp_text=plain(f"Semnat digital de\n{name}\n") + "%(ts)s", timestamp_format="%d.%m.%Y %H:%M",
                           border_width=1, border_color=(0.55, 0.6, 0.7))
    out_buf = io.BytesIO()
    w = IncrementalPdfFileWriter(io.BytesIO(data), strict=False)
    look = None
    if xfa_rect is not None:
        # formular XFA dinamic fără câmp: câmpul cu numele de la Acrobat, în aceeași actualizare cu semnătura
        xfasign.add_field(w, field, xfa_rect)
    if acrobat_size and acrobat_size[0] > 1 and acrobat_size[1] > 1:
        look = xfasign.look(plain(name), datetime.datetime.now().astimezone(), *acrobat_size)
        if look:
            style = xfasign.stamp_style(look)
    try:
        signers.PdfSigner(meta, signer, stamp_style=style, new_field_spec=new_spec).sign_pdf(w, output=out_buf)
    finally:
        if look:
            try:
                Path(look).unlink(missing_ok=True)
            except OSError:  # aspectul rămâne în folderul de stare; nu oprește semnarea
                pass

    target = output_for(src)
    bak = fx_sign.backup_path(target)
    if target.exists():
        shutil.copy2(target, bak)
    elif bak.exists():
        bak.unlink()
    tmp = target.with_name(f".{target.stem}.tmp.pdf")
    tmp.write_bytes(out_buf.getvalue())
    os.replace(tmp, target)
    return str(target)


def first_empty_field(pdf: str) -> str:
    """Câmpul de semnătură gol și vizibil (ex. „Semnătura” din declarațiile ANAF), dacă există."""
    with FITZ_LOCK, fitz.open(pdf) as doc:
        return next((f["name"] for f in signature_fields(doc) if not f["signed"] and f["visible"]), "")


def auto_place(pdf: str):
    """Locul semnăturii la semnarea în bloc / după validarea declarațiilor: câmpul gol al documentului; la un formular
    XFA dinamic fără câmp, caseta lui de semnătură (ca Acrobat); altfel invizibilă (None)."""
    f = first_empty_field(pdf)
    if f:
        return {"field": f}
    with FITZ_LOCK, fitz.open(pdf) as doc:
        if not xfaview.needs(doc):
            return None
        signed = {g["name"] for g in signature_fields(doc) if g["signed"]}
        free = [g["name"] for g in xfasign.fields(doc) if g["name"] not in signed]
    return {"xfa": free[0]} if free else None


def sign_many(thumb: str, items: list, reason: str = "", location: str = "", on_done=None, key: WinKey | None = None,
              hwnd: int = 0) -> list:
    """Semnează mai multe PDF-uri cu o singură deschidere a cheii (PIN-ul o dată).
    items: [{"path": ..., "place": ... | "auto"}]; „auto” = câmpul gol al documentului dacă are, altfel invizibilă.
    hwnd: fereastra editorului, deasupra căreia apare fereastra de PIN."""
    if not BUSY.acquire(blocking=False):
        raise RuntimeError("O semnare e deja în curs. Scrie PIN-ul în fereastra Windows sau apasă Anulează, apoi încearcă din nou.")
    results = []
    try:
        ACTIVE.update(key=None, phase="open", since=time.time(), dialog="", file="", done=0, total=len(items))
        if key is None:
            key = WinKey(thumb, hwnd=hwnd)
        ACTIVE["key"] = key
        signer = WinSigner(key)
        for it in items:
            t = time.time()
            ACTIVE["file"] = Path(it["path"]).name
            place = it.get("place")
            try:
                if not Path(it["path"]).is_file():
                    raise FileNotFoundError("Fișierul nu mai există.")
                if place == "auto":
                    place = auto_place(it["path"])
                out = sign_pdf(signer, it["path"], place, reason, location)
                res = {"path": it["path"], "ok": True, "out": out, "s": round(time.time() - t, 1)}
            except SignStop as err:
                # PIN greșit, card blocat sau anulare: nu mai întrebăm la fiecare fișier (fiecare încercare costă un PIN).
                results.append({"path": it["path"], "ok": False, "error": str(err), "stopped": True})
                break
            except Exception as err:
                res = {"path": it["path"], "ok": False, "error": str(err)}
            results.append(res)
            ACTIVE["done"] = len(results)
            if on_done:
                on_done(res)
    except SignStop as err:  # cheia nu s-a putut deschide
        results.append({"path": items[0]["path"] if items else "", "ok": False, "error": str(err), "stopped": True})
    finally:
        k = ACTIVE["key"] or key
        ACTIVE.update(key=None, phase="", dialog="", file="")
        if k is not None:
            k.close()
        BUSY.release()
    return results
