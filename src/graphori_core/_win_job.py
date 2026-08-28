"""Windows Job Object wrapper used to terminate an entire child process tree.

Only ever imported when ``sys.platform == "win32"``. Uses :mod:`ctypes`
against ``kernel32.dll``, which is Python stdlib -- no third-party
dependency is introduced. A process placed in a Job Object created with
``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` has every descendant it spawns killed
the moment the job handle is closed or :meth:`WindowsJob.terminate` is
called, which is the only reliable way to bound a Windows process tree
without cooperating children.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

JobObjectExtendedLimitInformation = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
PROCESS_TERMINATE = 0x0001
PROCESS_SET_QUOTA = 0x0100
SYNCHRONIZE = 0x00100000


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


_kernel32.CreateJobObjectW.restype = wintypes.HANDLE
_kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
_kernel32.SetInformationJobObject.restype = wintypes.BOOL
_kernel32.SetInformationJobObject.argtypes = [
    wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
_kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
_kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
_kernel32.TerminateJobObject.restype = wintypes.BOOL
_kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, ctypes.c_uint]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class JobObjectUnavailable(RuntimeError):
    """Raised when the Job Object could not be created, configured, or assigned.

    Callers must catch this and fall back to a documented alternative
    (``taskkill /T /F``) instead of pretending the job succeeded.
    """


class WindowsJob:
    """A Job Object with kill-on-close so an unresponsive tree is always reapable."""

    def __init__(self) -> None:
        handle = _kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise JobObjectUnavailable(f"CreateJobObjectW failed: err={ctypes.get_last_error()}")
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = _kernel32.SetInformationJobObject(
            handle, JobObjectExtendedLimitInformation,
            ctypes.byref(info), ctypes.sizeof(info))
        if not ok:
            err = ctypes.get_last_error()
            _kernel32.CloseHandle(handle)
            raise JobObjectUnavailable(f"SetInformationJobObject failed: err={err}")
        self._handle = handle
        self.closed = False

    def assign(self, pid: int) -> None:
        access = PROCESS_TERMINATE | PROCESS_SET_QUOTA | SYNCHRONIZE
        proc_handle = _kernel32.OpenProcess(access, False, pid)
        if not proc_handle:
            raise JobObjectUnavailable(f"OpenProcess failed: err={ctypes.get_last_error()} pid={pid}")
        try:
            ok = _kernel32.AssignProcessToJobObject(self._handle, proc_handle)
            if not ok:
                raise JobObjectUnavailable(
                    f"AssignProcessToJobObject failed: err={ctypes.get_last_error()} pid={pid}")
        finally:
            _kernel32.CloseHandle(proc_handle)

    def terminate(self, exit_code: int = 1) -> bool:
        return bool(_kernel32.TerminateJobObject(self._handle, exit_code))

    def close(self) -> None:
        if not self.closed:
            _kernel32.CloseHandle(self._handle)
            self.closed = True
