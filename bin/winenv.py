"""Ce află aplicația de la Windows fără PowerShell (instant): fereastra din față, fereastra de PIN, procesele pornite,
cititoarele de card și, pentru fiecare certificat, unde îi stă cheia (buletin, stick prin FintaxySign, token).

Totul e „cel mai bun efort”: orice eroare dă un răspuns gol, niciodată o excepție spre editor.
"""
import ctypes
import os
import threading
import time
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    dwmapi = ctypes.WinDLL("dwmapi")
except OSError:  # pragma: no cover
    dwmapi = None

HWND = ctypes.c_void_p
user32.GetForegroundWindow.restype = HWND
user32.IsWindowVisible.argtypes = [HWND]
user32.IsIconic.argtypes = [HWND]
user32.GetClassNameW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowRect.argtypes = [HWND, ctypes.POINTER(wintypes.RECT)]
user32.SetForegroundWindow.argtypes = [HWND]
user32.BringWindowToTop.argtypes = [HWND]
user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(wintypes.DWORD)]
ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [ENUMPROC, wintypes.LPARAM]

# Ferestre ale Windows-ului care ajung „în față” pentru o clipă (Alt+Tab, bara de activități, desktopul):
# o fereastră de PIN legată de ele rămâne ascunsă.
SHELL_CLASSES = {"XamlExplorerHostIslandWindow", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW",
                 "MultitaskingViewFrame", "TaskSwitcherWnd", "ForegroundStaging", "Windows.UI.Core.CoreWindow",
                 "NotifyIconOverflowWindow", "TopLevelWindowForOverflowXamlIsland"}
PIN_CLASS = "Credential Dialog Xaml Host"


def _text(fn, hwnd) -> str:
    buf = ctypes.create_unicode_buffer(300)
    fn(hwnd, buf, 300)
    return buf.value


def cloaked(hwnd) -> bool:
    if not dwmapi:
        return False
    v = ctypes.c_int(0)
    try:
        dwmapi.DwmGetWindowAttribute(HWND(hwnd), 14, ctypes.byref(v), 4)  # DWMWA_CLOAKED
    except Exception:
        return False
    return bool(v.value)


def usable_window(hwnd) -> bool:
    """O fereastră adevărată, pe ecran: de ea se poate lega fereastra de PIN."""
    if not hwnd or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd) or cloaked(hwnd):
        return False
    if _text(user32.GetClassNameW, hwnd) in SHELL_CLASSES:
        return False
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.right - r.left) > 200 and (r.bottom - r.top) > 120


def windows() -> list:
    """Ferestrele de nivel sus: (hwnd, clasă, titlu, vizibilă, ascunsă de sistem)."""
    found = []

    @ENUMPROC
    def cb(hwnd, _):
        found.append(hwnd)
        return True
    user32.EnumWindows(cb, 0)
    return [(h, _text(user32.GetClassNameW, h), _text(user32.GetWindowTextW, h), bool(user32.IsWindowVisible(h)), cloaked(h))
            for h in found]


def parent_window(title_hint: str = "") -> int:
    """Fereastra editorului, luată în clipa în care omul a apăsat Semnează (atunci e ea în față).
    Dacă în față e altceva (Alt+Tab, bara de activități), o căutăm după numele documentului; altfel 0 = fără părinte."""
    try:
        fg = user32.GetForegroundWindow()
        if usable_window(fg):
            return int(fg)
        hint = (title_hint or "").lower()
        if hint:
            for h, _cls, title, vis, clk in windows():
                if vis and not clk and hint in title.lower() and usable_window(h):
                    return int(h)
    except Exception:
        pass
    return 0


def pin_dialog():
    """Fereastra de PIN a Windows-ului, dacă e deschisă: {"hwnd", "hidden"}."""
    try:
        for h, cls, _title, vis, clk in windows():
            if cls == PIN_CLASS and vis:
                return {"hwnd": int(h), "hidden": clk}
    except Exception:
        pass
    return None


def bring_to_front(hwnd: int) -> bool:
    """Aduce o fereastră în față. Windows refuză asta proceselor din fundal, în afară de cazul în care tocmai
    s-a apăsat o tastă: de aici apăsarea goală de Alt."""
    try:
        if user32.GetForegroundWindow() == hwnd:
            return True
        user32.keybd_event(0x12, 0, 0, 0)  # Alt apăsat
        user32.keybd_event(0x12, 0, 2, 0)  # Alt ridicat
        user32.BringWindowToTop(HWND(hwnd))
        return bool(user32.SetForegroundWindow(HWND(hwnd)))
    except Exception:
        return False


# ---------- procese ----------

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260)]


kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def process_path(exe_name: str) -> str:
    """Calea unui program pornit (după numele fișierului .exe); "" dacă nu rulează."""
    try:
        snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)
        if not snap or snap == wintypes.HANDLE(-1).value:
            return ""
        try:
            e = PROCESSENTRY32W()
            e.dwSize = ctypes.sizeof(e)
            ok = kernel32.Process32FirstW(snap, ctypes.byref(e))
            while ok:
                if e.szExeFile.lower() == exe_name.lower():
                    h = kernel32.OpenProcess(0x1000, False, e.th32ProcessID)  # PROCESS_QUERY_LIMITED_INFORMATION
                    if h:
                        try:
                            buf = ctypes.create_unicode_buffer(1024)
                            n = wintypes.DWORD(1024)
                            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                                return buf.value
                        finally:
                            kernel32.CloseHandle(h)
                    return exe_name  # rulează, dar nu-i putem citi calea
                ok = kernel32.Process32NextW(snap, ctypes.byref(e))
        finally:
            kernel32.CloseHandle(snap)
    except Exception:
        pass
    return ""


# ---------- cititoare de card ----------

class SCARD_READERSTATE(ctypes.Structure):
    _fields_ = [("szReader", wintypes.LPCWSTR), ("pvUserData", ctypes.c_void_p), ("dwCurrentState", wintypes.DWORD),
                ("dwEventState", wintypes.DWORD), ("cbAtr", wintypes.DWORD), ("rgbAtr", ctypes.c_ubyte * 36)]


def readers() -> list:
    """Cititoarele de card și dacă au card: [{"name", "card"}]. Cititorul virtual al FintaxySign apare și el aici."""
    res = []
    try:
        ws = ctypes.WinDLL("winscard")
        ctx = ctypes.c_void_p()
        if ws.SCardEstablishContext(0, None, None, ctypes.byref(ctx)):
            return res
        try:
            n = wintypes.DWORD(0)
            if ws.SCardListReadersW(ctx, None, None, ctypes.byref(n)) or not n.value:
                return res
            buf = ctypes.create_unicode_buffer(n.value)
            if ws.SCardListReadersW(ctx, None, buf, ctypes.byref(n)):
                return res
            names = [s for s in ctypes.wstring_at(buf, n.value).split("\0") if s]
            for name in names:
                st = SCARD_READERSTATE()
                st.szReader = name
                card = False
                if not ws.SCardGetStatusChangeW(ctx, 0, ctypes.byref(st), 1):
                    card = bool(st.dwEventState & 0x20)  # SCARD_STATE_PRESENT
                res.append({"name": name, "card": card})
        finally:
            ws.SCardReleaseContext(ctx)
    except Exception:
        pass
    return res


VIRTUAL_READER = ("virtual smart card architecture", "virtual pcd", "bix virtual")


def is_virtual_reader(name: str) -> bool:
    n = (name or "").lower()
    return any(k in n for k in VIRTUAL_READER)


# ---------- unde stă cheia fiecărui certificat ----------

class CRYPT_KEY_PROV_INFO(ctypes.Structure):
    _fields_ = [("pwszContainerName", wintypes.LPWSTR), ("pwszProvName", wintypes.LPWSTR), ("dwProvType", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("cProvParam", wintypes.DWORD), ("rgProvParam", ctypes.c_void_p),
                ("dwKeySpec", wintypes.DWORD)]


class CERT_CONTEXT(ctypes.Structure):
    _fields_ = [("dwCertEncodingType", wintypes.DWORD), ("pbCertEncoded", ctypes.POINTER(ctypes.c_ubyte)),
                ("cbCertEncoded", wintypes.DWORD), ("pCertInfo", ctypes.c_void_p), ("hCertStore", ctypes.c_void_p)]


def store_certs(store_name: str = "MY") -> list:
    """Certificatele cu cheie privată din Cert:\\CurrentUser\\My (sau alt depozit al utilizatorului, la teste), citite direct din Windows (instant):
    [{"thumb", "der", "friendly", "provider", "container"}]."""
    c32 = ctypes.WinDLL("crypt32", use_last_error=True)
    c32.CertOpenStore.restype = ctypes.c_void_p
    c32.CertOpenStore.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.c_wchar_p]
    c32.CertEnumCertificatesInStore.restype = ctypes.POINTER(CERT_CONTEXT)
    c32.CertEnumCertificatesInStore.argtypes = [ctypes.c_void_p, ctypes.POINTER(CERT_CONTEXT)]
    c32.CertGetCertificateContextProperty.argtypes = [ctypes.POINTER(CERT_CONTEXT), wintypes.DWORD, ctypes.c_void_p,
                                                      ctypes.POINTER(wintypes.DWORD)]
    c32.CertCloseStore.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    store = c32.CertOpenStore(10, 0, None, 0x10000 | 0x8000, store_name)  # SYSTEM_W, CURRENT_USER | READONLY
    out = []
    if not store:
        return out

    def prop(ctx, pid):
        n = wintypes.DWORD(0)
        if not c32.CertGetCertificateContextProperty(ctx, pid, None, ctypes.byref(n)) or not n.value:
            return None
        buf = ctypes.create_string_buffer(n.value)
        return buf if c32.CertGetCertificateContextProperty(ctx, pid, buf, ctypes.byref(n)) else None

    try:
        ctx = None
        while True:
            ctx = c32.CertEnumCertificatesInStore(store, ctx)
            if not ctx:
                break
            info = prop(ctx, 2)  # CERT_KEY_PROV_INFO_PROP_ID: fără el certificatul n-are cheie privată aici
            if info is None:
                continue
            kp = ctypes.cast(info, ctypes.POINTER(CRYPT_KEY_PROV_INFO)).contents
            sha = prop(ctx, 3)  # SHA1
            friendly = prop(ctx, 11)  # CERT_FRIENDLY_NAME_PROP_ID
            c = ctx.contents
            out.append({"thumb": sha.raw[:20].hex().upper() if sha else "",
                        "der": ctypes.string_at(c.pbCertEncoded, c.cbCertEncoded),
                        "friendly": ctypes.wstring_at(friendly) if friendly else "",
                        "provider": kp.pwszProvName or "", "container": kp.pwszContainerName or ""})
    finally:
        c32.CertCloseStore(store, 0)
    return out


# ---------- certificatele de pe carduri, aduse în Windows ----------
# Windows copiază singur în Cert:\CurrentUser\My certificatele de pe cardul introdus (serviciul „Certificate
# Propagation”), dar nu mereu: pentru cititorul virtual FintaxySign (stick-ul din birou) nu o face, iar un card cu
# două certificate (unul expirat, unul reînnoit) nu apărea deloc în listă. Le citim direct de pe card, fără PIN și
# fără ferestre, și le punem în Windows legate de cheia de pe card, ca după propagarea obișnuită.

SC_KSP = "Microsoft Smart Card Key Storage Provider"


class NCryptKeyName(ctypes.Structure):
    _fields_ = [("pszName", wintypes.LPWSTR), ("pszAlgid", wintypes.LPWSTR), ("dwLegacyKeySpec", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD)]


def _ncrypt():
    nc = ctypes.WinDLL("ncrypt")
    for fn in (nc.NCryptOpenStorageProvider, nc.NCryptOpenKey, nc.NCryptGetProperty, nc.NCryptFreeObject,
               nc.NCryptEnumKeys, nc.NCryptFreeBuffer):
        fn.restype = ctypes.c_long
    nc.NCryptOpenStorageProvider.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_wchar_p, wintypes.DWORD]
    nc.NCryptOpenKey.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD]
    nc.NCryptGetProperty.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_void_p, wintypes.DWORD,
                                     ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    nc.NCryptFreeObject.argtypes = [ctypes.c_void_p]
    nc.NCryptEnumKeys.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.POINTER(ctypes.POINTER(NCryptKeyName)),
                                  ctypes.POINTER(ctypes.c_void_p), wintypes.DWORD]
    nc.NCryptFreeBuffer.argtypes = [ctypes.c_void_p]
    return nc


def card_keys(reader_names=None) -> list:
    """Cheile de pe cardurile din cititoare, fiecare cu certificatul ei: [{"reader", "container", "der"}].
    Fără PIN și fără ferestre (NCRYPT_SILENT_FLAG); un card fără certificat pe cheie e sărit."""
    nc = _ncrypt()
    silent = 0x40
    if reader_names is None:
        reader_names = [r["name"] for r in readers() if r["card"]]
    out = []
    prov = ctypes.c_void_p()
    if nc.NCryptOpenStorageProvider(ctypes.byref(prov), SC_KSP, 0):
        return out
    try:
        for reader in reader_names:
            names, state = [], ctypes.c_void_p()
            try:
                while True:
                    p = ctypes.POINTER(NCryptKeyName)()
                    if nc.NCryptEnumKeys(prov, "\\\\.\\" + reader + "\\", ctypes.byref(p), ctypes.byref(state), silent):
                        break  # NTE_NO_MORE_ITEMS sau cardul nu răspunde
                    names.append(p.contents.pszName)
                    nc.NCryptFreeBuffer(p)
            finally:
                if state:
                    nc.NCryptFreeBuffer(state)
            for name in names:
                key = ctypes.c_void_p()
                if nc.NCryptOpenKey(prov, ctypes.byref(key), "\\\\.\\" + reader + "\\" + name, 0, silent):
                    continue
                try:
                    n = wintypes.DWORD(0)
                    if nc.NCryptGetProperty(key, "SmartCardKeyCertificate", None, 0, ctypes.byref(n), silent) or not n.value:
                        continue
                    buf = ctypes.create_string_buffer(n.value)
                    if nc.NCryptGetProperty(key, "SmartCardKeyCertificate", buf, n.value, ctypes.byref(n), silent):
                        continue
                    out.append({"reader": reader, "container": name, "der": buf.raw[:n.value]})
                finally:
                    nc.NCryptFreeObject(key)
    finally:
        nc.NCryptFreeObject(prov)
    return out


def register_certs(keys: list, provider: str = SC_KSP, store_name: str = "MY") -> list:
    """Pune certificatele în Cert:\\CurrentUser\\<store_name> legate de cheia lor (CERT_KEY_PROV_INFO), doar pe cele
    care lipsesc sau n-au cheia legată. Întoarce amprentele SHA1 ale celor adăugate/reparate."""
    known = {c["thumb"] for c in store_certs(store_name)}
    c32 = ctypes.WinDLL("crypt32", use_last_error=True)
    c32.CertOpenStore.restype = ctypes.c_void_p
    c32.CertOpenStore.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.c_wchar_p]
    c32.CertAddEncodedCertificateToStore.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_char_p, wintypes.DWORD,
                                                     wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(CERT_CONTEXT))]
    c32.CertSetCertificateContextProperty.argtypes = [ctypes.POINTER(CERT_CONTEXT), wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    c32.CertFreeCertificateContext.argtypes = [ctypes.POINTER(CERT_CONTEXT)]
    c32.CertCloseStore.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    import hashlib
    todo = [k for k in keys if hashlib.sha1(k["der"]).hexdigest().upper() not in known]
    if not todo:
        return []
    store = c32.CertOpenStore(10, 0, None, 0x10000, store_name)  # SYSTEM_W, CURRENT_USER (scriere)
    if not store:
        return []
    done = []
    try:
        for k in todo:
            ctx = ctypes.POINTER(CERT_CONTEXT)()
            # X509_ASN_ENCODING | PKCS_7_ASN_ENCODING; CERT_STORE_ADD_USE_EXISTING: dacă e deja (fără cheie), îl reparăm
            if not c32.CertAddEncodedCertificateToStore(store, 0x10001, k["der"], len(k["der"]), 2, ctypes.byref(ctx)):
                continue
            try:
                info = CRYPT_KEY_PROV_INFO(k["container"], provider, 0, 0, 0, None, 0)  # dwProvType 0 = CNG
                if c32.CertSetCertificateContextProperty(ctx, 2, 0, ctypes.byref(info)):
                    done.append(hashlib.sha1(k["der"]).hexdigest().upper())
            finally:
                c32.CertFreeCertificateContext(ctx)
    finally:
        c32.CertCloseStore(store, 0)
    return done


# Cardurile se întreabă pe rând (două întrebări deodată pe același card se încurcă), iar stick-ul de la distanță
# răspunde în 5-15 s: citirea cardurilor merge în fundal, lista de certificate o așteaptă cel mult câteva secunde.
_CARD_LOCK = threading.Lock()
_SYNC = {"thread": None, "t": 0.0, "added": []}


def _sync_worker():
    added = []
    try:
        with _CARD_LOCK:
            keys = card_keys()
        added = register_certs(keys)
    except Exception:
        pass
    _SYNC.update(thread=None, t=time.time(), added=added)


def sync_card_certs(wait: float = 0.0, fresh: bool = False) -> dict:
    """Aduce în Windows certificatele de pe carduri (în fundal, cel mult o dată la 30 s, sau acum dacă `fresh`).
    Așteaptă cel mult `wait` secunde. {"running": încă citește, "added": amprentele adăugate ultima dată}."""
    th = _SYNC["thread"]
    if th is None and (fresh or time.time() - _SYNC["t"] > 30):
        th = _SYNC["thread"] = threading.Thread(target=_sync_worker, daemon=True)
        th.start()
    if th is not None and wait > 0:
        th.join(wait)
    return {"running": _SYNC["thread"] is not None, "added": list(_SYNC["added"])}


def _reader_of(provider: str, container: str) -> dict:
    """Cititorul în care e cardul cu cheia, fără nicio fereastră (NCRYPT_SILENT_FLAG): {"reader", "present"}."""
    nc = ctypes.WinDLL("ncrypt")
    for fn in (nc.NCryptOpenStorageProvider, nc.NCryptOpenKey, nc.NCryptGetProperty, nc.NCryptFreeObject):
        fn.restype = ctypes.c_long
    nc.NCryptOpenStorageProvider.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_wchar_p, wintypes.DWORD]
    nc.NCryptOpenKey.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD]
    nc.NCryptGetProperty.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_void_p, wintypes.DWORD,
                                     ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    nc.NCryptFreeObject.argtypes = [ctypes.c_void_p]
    silent = 0x40
    prov = ctypes.c_void_p()
    if nc.NCryptOpenStorageProvider(ctypes.byref(prov), provider, 0):
        return {"reader": "", "present": False}
    try:
        key = ctypes.c_void_p()
        if nc.NCryptOpenKey(prov, ctypes.byref(key), container, 0, silent):
            return {"reader": "", "present": False}  # cardul nu e în cititor (sau stick-ul nu e conectat)
        try:
            buf = ctypes.create_unicode_buffer(512)
            n = wintypes.DWORD(0)
            if nc.NCryptGetProperty(key, "SmartCardReader", buf, 1024, ctypes.byref(n), silent):
                return {"reader": "", "present": True}
            return {"reader": buf.value, "present": True}
        finally:
            nc.NCryptFreeObject(key)
    finally:
        nc.NCryptFreeObject(prov)


# Ce am aflat despre chei, ținut cât rulează aplicația: stick-ul de la distanță (FintaxySign) răspunde uneori în
# 10-20 s, deci întrebarea pornește în fundal și lista de certificate nu o așteaptă. Cardurile se întreabă pe rând:
# două întrebări deodată pe același card se încurcă una pe alta.
_KEYS: dict = {}       # thumb -> {"provider", "smartcard", "reader", "present", "t"}; t = 0 cât nu a răspuns
_QUEUE: list = []
_KEYS_LOCK = threading.Lock()
_WORKER = {"thread": None}


def _probe_worker():
    while True:
        with _KEYS_LOCK:
            if not _QUEUE:
                _WORKER["thread"] = None
                return
            thumb, provider, container = _QUEUE.pop(0)
        res = {"reader": "", "present": False}
        for attempt in range(2):  # cardul ocupat o clipă de alt program: mai încercăm o dată
            try:
                with _CARD_LOCK:
                    res = _reader_of(provider, container)
            except Exception:
                res = {"reader": "", "present": False}
            if res["present"]:
                break
            time.sleep(0.8)
        with _KEYS_LOCK:
            old = _KEYS.get(thumb, {})
            if not res["reader"] and old.get("reader"):
                res["reader"] = old["reader"]  # cititorul aflat o dată rămâne (cheia nu se mută pe alt card)
            _KEYS[thumb] = {**old, **res, "t": time.time()}


def key_sources(certs: list, wait: float = 2.5, fresh: bool = False) -> dict:
    """thumb -> {"provider", "smartcard", "reader", "present", "pending"} pentru certificatele date (store_certs()).
    Așteaptă cel mult `wait` secunde; ce nu a răspuns rămâne „pending” și se completează în fundal."""
    with _KEYS_LOCK:
        queued = {q[0] for q in _QUEUE}
        for c in certs:
            thumb, provider, container = c["thumb"], c["provider"], c["container"]
            smart = "smart card" in provider.lower()
            k = _KEYS.get(thumb)
            if k is None:
                k = _KEYS[thumb] = {"provider": provider, "smartcard": smart, "reader": "", "present": not smart,
                                    "t": 0.0 if smart else time.time()}
            stale = k["t"] == 0.0 or fresh or time.time() - k["t"] > 20
            if smart and container and stale and thumb not in queued:
                _QUEUE.append((thumb, provider, container))
        if _QUEUE and _WORKER["thread"] is None:
            _WORKER["thread"] = threading.Thread(target=_probe_worker, daemon=True)
            _WORKER["thread"].start()
    end = time.time() + wait
    while time.time() < end:
        with _KEYS_LOCK:
            if all(_KEYS[c["thumb"]]["t"] for c in certs) and (not fresh or (not _QUEUE and _WORKER["thread"] is None)):
                break
        time.sleep(0.1)
    with _KEYS_LOCK:
        return {c["thumb"]: {**_KEYS[c["thumb"]], "pending": _KEYS[c["thumb"]]["t"] == 0.0} for c in certs}


# ---------- FintaxySign ----------

def fintaxysign(saved_path: str = "") -> dict:
    """Starea aplicației FintaxySign (stick-ul din birou, de la distanță): pornită?, unde e, cititorul ei virtual."""
    running = process_path("FintaxySign.exe")
    rd = readers()
    virtual = [r for r in rd if is_virtual_reader(r["name"])]
    path = running if running and os.path.isfile(running) else ""
    if not path:
        home = Path(os.environ.get("USERPROFILE", ""))
        pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        for c in (saved_path, home / "Documents" / "FintaxySign" / "FintaxySign.exe", home / "Desktop" / "FintaxySign" / "FintaxySign.exe",
                  home / "Desktop" / "FintaxySign.exe", home / "Downloads" / "FintaxySign" / "FintaxySign.exe",
                  pf / "FintaxySign" / "FintaxySign.exe", Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "FintaxySign" / "FintaxySign.exe"):
            if c and os.path.isfile(str(c)):
                path = str(c)
                break
    return {"running": bool(running), "path": path, "driver": bool(virtual), "stick": any(r["card"] for r in virtual),
            "readers": rd}
