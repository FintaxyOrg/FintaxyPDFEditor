"""Certificatele de pe carduri aduse în Windows (winenv.register_certs / card_keys), fără card și fără PIN:
un certificat de test e pus într-un depozit separat al utilizatorului, legat de o cheie de card inventată,
apoi depozitul e șters. Cu --live citește și cardurile reale din cititoare (doar citire, nu scrie nimic).

  python tests/test_cardcerts.py [--live]
"""
import ctypes
import datetime
import hashlib
import secrets
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

import winenv  # noqa: E402

FAILED = []


def check(name: str, ok: bool, detail: str = ""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""), flush=True)
    if not ok:
        FAILED.append(name)


def test_cert(cn: str) -> bytes:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=30))
            .add_extension(x509.KeyUsage(True, True, False, False, False, False, False, False, False), critical=True)
            .sign(key, hashes.SHA256()))
    return cert.public_bytes(serialization.Encoding.DER)


def drop_store(name: str):
    c32 = ctypes.WinDLL("crypt32")
    c32.CertUnregisterSystemStore.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
    c32.CertUnregisterSystemStore(name, 0x10000)  # CERT_SYSTEM_STORE_CURRENT_USER


def main(live: bool) -> int:
    store = "FXTEST" + secrets.token_hex(4).upper()
    print(f"== înregistrare în depozitul de test {store} ==")
    try:
        a, b = test_cert("Ion Popescu"), test_cert("Ion Popescu (reinnoit)")
        keys = [{"reader": "Virtual Smart Card Architecture Virtual PCD 0", "container": "cont_test_a", "der": a},
                {"reader": "Virtual Smart Card Architecture Virtual PCD 0", "container": "cont_test_b", "der": b}]
        thumbs = {hashlib.sha1(a).hexdigest().upper(), hashlib.sha1(b).hexdigest().upper()}
        check("ambele certificate de pe card sunt adăugate", set(winenv.register_certs(keys, store_name=store)) == thumbs)
        listed = {c["thumb"]: c for c in winenv.store_certs(store)}
        check("apar în listă cu cheie privată", thumbs <= set(listed), str(list(listed)))
        for t, cont in zip(sorted(thumbs, key=lambda x: x != hashlib.sha1(a).hexdigest().upper()), ("cont_test_a", "cont_test_b")):
            c = listed.get(t, {})
            check(f"{cont}: legat de cheia de pe card", c.get("container") == cont and c.get("provider") == winenv.SC_KSP,
                  f"{c.get('container')} / {c.get('provider')}")
        check("a doua oară nu mai adaugă nimic", winenv.register_certs(keys, store_name=store) == [])
        check("lista goală nu scrie nimic", winenv.register_certs([], store_name=store) == [])
    finally:
        drop_store(store)

    print("\n== sync_card_certs: rulează în fundal, nu de două ori deodată ==")
    calls = []
    real_keys, real_reg = winenv.card_keys, winenv.register_certs
    winenv.card_keys = lambda *a, **k: (calls.append(1), time.sleep(0.5), [])[2]
    winenv.register_certs = lambda keys, **k: []
    try:
        winenv._SYNC.update(thread=None, t=0.0, added=[])
        r1 = winenv.sync_card_certs(wait=0)
        r2 = winenv.sync_card_certs(wait=0, fresh=True)
        check("prima cerere pornește citirea în fundal", r1["running"])
        check("a doua, cât rulează prima, nu pornește alta", r2["running"] and len(calls) <= 1)
        r3 = winenv.sync_card_certs(wait=2)
        check("se termină în timpul de așteptare", not r3["running"] and len(calls) == 1)
        winenv.sync_card_certs(wait=0)
        check("nu se repetă mai des de 30 s", len(calls) == 1)
        winenv.sync_card_certs(wait=2, fresh=True)
        check("„Reîncarcă” citește din nou", len(calls) == 2)
    finally:
        winenv.card_keys, winenv.register_certs = real_keys, real_reg

    if live:
        print("\n== cardurile reale (doar citire) ==")
        t = time.time()
        ks = winenv.card_keys()
        for k in ks:
            print(f"  {k['reader']} · {k['container']} · {hashlib.sha1(k['der']).hexdigest().upper()}")
        check("citirea cardurilor nu dă eroare", True, f"{len(ks)} certificate, {time.time() - t:.1f} s")

    print("\n" + ("TOATE TESTELE AU TRECUT" if not FAILED else f"{len(FAILED)} TESTE AU PICAT: {FAILED}"))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main("--live" in sys.argv))
