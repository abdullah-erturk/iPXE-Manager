"""
davinst.exe - iPXE Manager WinFsp Driver Installer
WinPE ortaminda WinFsp dosya sistemi suruculerini
registry'ye RUNTIME'DA yazarak baslatir.
"""

import os, sys, time, ctypes, winreg, platform
from ctypes import wintypes

# ── Win32 sabitleri ───────────────────────────────────────────────────────────
SC_MANAGER_ALL_ACCESS       = 0x000F003F
SERVICE_ALL_ACCESS          = 0x000F01FF
SERVICE_FILE_SYSTEM_DRIVER  = 0x00000002
SERVICE_WIN32_SHARE_PROCESS = 0x00000020
SERVICE_DEMAND_START        = 3
SERVICE_ERROR_NORMAL        = 1
SERVICE_RUNNING             = 4

advapi32 = ctypes.windll.advapi32
advapi32.CloseServiceHandle.argtypes = [wintypes.HANDLE]
advapi32.CloseServiceHandle.restype = wintypes.BOOL

class SERVICE_STATUS(ctypes.Structure):
    _fields_ = [
        ("dwServiceType",             wintypes.DWORD),
        ("dwCurrentState",            wintypes.DWORD),
        ("dwControlsAccepted",        wintypes.DWORD),
        ("dwWin32ExitCode",           wintypes.DWORD),
        ("dwServiceSpecificExitCode", wintypes.DWORD),
        ("dwCheckPoint",              wintypes.DWORD),
        ("dwWaitHint",                wintypes.DWORD),
    ]

# ── Yardimcilar ───────────────────────────────────────────────────────────────
def log(msg):
    print(msg, flush=True)

def reg_set(key_path, values: list):
    """HKLM altinda key_path'e values listesini yazar. Yol yoksa olusturur."""
    try:
        try:
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                               winreg.KEY_SET_VALUE | winreg.KEY_CREATE_SUB_KEY)
        except FileNotFoundError:
            k = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                                   winreg.KEY_SET_VALUE | winreg.KEY_CREATE_SUB_KEY)
        for name, typ, data in values:
            winreg.SetValueEx(k, name, 0, typ, data)
        winreg.CloseKey(k)
        return True
    except Exception as e:
        log(f"    [WARN] Registry {key_path}: {e}")
        return False

def svc_state(scm, name):
    advapi32.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
    advapi32.OpenServiceW.restype = wintypes.HANDLE
    
    svc = advapi32.OpenServiceW(scm, str(name), 0x0004)  # QUERY_STATUS
    if not svc:
        return 0
    st = SERVICE_STATUS()
    
    advapi32.QueryServiceStatus.argtypes = [wintypes.HANDLE, ctypes.POINTER(SERVICE_STATUS)]
    advapi32.QueryServiceStatus.restype = wintypes.BOOL
    
    advapi32.QueryServiceStatus(svc, ctypes.byref(st))
    advapi32.CloseServiceHandle(svc)
    return st.dwCurrentState

def svc_create_or_open(scm, name, display, svc_type, start_type, binary_path, deps=None):
    advapi32.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
    advapi32.OpenServiceW.restype = wintypes.HANDLE

    advapi32.CreateServiceW.argtypes = [
        wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPCWSTR,
        wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD),
        wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR
    ]
    advapi32.CreateServiceW.restype = wintypes.HANDLE
    
    advapi32.CloseServiceHandle.argtypes = [wintypes.HANDLE]
    advapi32.CloseServiceHandle.restype = wintypes.BOOL

    svc = advapi32.OpenServiceW(scm, str(name), SERVICE_ALL_ACCESS)
    if svc:
        return svc
        
    deps_ptr = ctypes.c_wchar_p(deps) if deps else None
    
    return advapi32.CreateServiceW(
        scm, str(name), str(display),
        SERVICE_ALL_ACCESS, svc_type, start_type,
        SERVICE_ERROR_NORMAL, str(binary_path),
        None, None, deps_ptr, None, None
    )

def svc_start(scm, name, wait=8):
    advapi32.StartServiceW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p]
    advapi32.StartServiceW.restype = wintypes.BOOL

    if svc_state(scm, name) == SERVICE_RUNNING:
        log(f"    [OK] {name} is already running")
        return True
    
    advapi32.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
    advapi32.OpenServiceW.restype = wintypes.HANDLE
    svc = advapi32.OpenServiceW(scm, str(name), SERVICE_ALL_ACCESS)
    if not svc:
        log(f"    [FAIL] Could not open {name}")
        return False
    ret = advapi32.StartServiceW(svc, 0, None)
    advapi32.CloseServiceHandle(svc)
    err = ctypes.get_last_error()
    if not ret and err != 1056:   # 1056 = ERROR_SERVICE_ALREADY_RUNNING
        log(f"    [FAIL] Failed to start {name}: Win32 Error {err}")
        return False
    for _ in range(wait * 2):
        time.sleep(0.5)
        if svc_state(scm, name) == SERVICE_RUNNING:
            log(f"    [OK] {name} started successfully")
            return True
    log(f"    [WARN] {name} start timeout")
    return False

# ── Ana mantik ────────────────────────────────────────────────────────────────
def main():
    log("=" * 58)
    log("   davinst.exe — iPXE Manager (WinPE)")
    log("=" * 58)

    # ── SCM aç ────────────────────────────────────────────────────────────────
    log("\n[1/2] Opening Service Control Manager...")
    
    advapi32.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    advapi32.OpenSCManagerW.restype = wintypes.HANDLE
    
    scm = advapi32.OpenSCManagerW(None, None, SC_MANAGER_ALL_ACCESS)
    if not scm:
        err = ctypes.get_last_error()
        log(f"    [ERROR] OpenSCManager: Win32 Error {err}")
        sys.exit(3)

    try:
        log("\n[2/2] Registering and starting WinFsp service:")
        
        # Mimari tespiti: 64-bit ise winfsp-x64.sys, 32-bit ise winfsp-x86.sys
        arch = platform.machine().lower()
        if arch in ('amd64', 'x86_64', 'x64'):
            fsp_sys = "winfsp-x64.sys"
        else:
            fsp_sys = "winfsp-x86.sys"
        log(f"    Architecture: {arch} -> {fsp_sys}")
        
        fsp_path = rf"\SystemRoot\System32\drivers\{fsp_sys}"
        
        svc = svc_create_or_open(
            scm, "winfsp", "WinFsp",
            SERVICE_FILE_SYSTEM_DRIVER, SERVICE_DEMAND_START,
            fsp_path,
            None
        )
        if svc:
            advapi32.CloseServiceHandle(svc)

        ok_fsp = svc_start(scm, "winfsp", wait=8)

    finally:
        advapi32.CloseServiceHandle(scm)

    log("")
    if ok_fsp:
        log("[SUCCESS] WinFsp driver is running.")
        sys.exit(0)
    else:
        log("[FAILED] WinFsp failed to start.")
        sys.exit(2)

if __name__ == "__main__":
    main()
