"""The graphics adapters DXGI lists: name, dedicated memory and LUID.

The performance counters key every instance by LUID and state no totals, so
this is what names a card and says how much memory it has.
"""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass


@dataclass(frozen=True)
class Adapter:
    # "0x<high>_0x<low>", lower case, as the counters spell it inside an instance.
    luid: str
    name: str
    dedicated_bytes: int


class _Guid(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _Luid(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _AdapterDesc1(ctypes.Structure):
    _fields_ = [
        ("Description", wintypes.WCHAR * 128),
        ("VendorId", wintypes.UINT),
        ("DeviceId", wintypes.UINT),
        ("SubSysId", wintypes.UINT),
        ("Revision", wintypes.UINT),
        ("DedicatedVideoMemory", ctypes.c_size_t),
        ("DedicatedSystemMemory", ctypes.c_size_t),
        ("SharedSystemMemory", ctypes.c_size_t),
        ("AdapterLuid", _Luid),
        ("Flags", wintypes.UINT),
    ]


_IID_IDXGI_FACTORY1 = _Guid(
    0x770AAE78,
    0xF26F,
    0x4DBA,
    (ctypes.c_ubyte * 8)(0xA8, 0x29, 0x25, 0x3C, 0x83, 0xD1, 0xB3, 0x87),
)
_SOFTWARE = 0x2  # DXGI_ADAPTER_FLAG_SOFTWARE
# vtable slots, counted through IUnknown, IDXGIObject and IDXGIFactory/IDXGIAdapter.
_RELEASE = 2
_ENUM_ADAPTERS1 = 12
_GET_DESC1 = 10


def list_adapters() -> list[Adapter]:
    """Hardware adapters only; Microsoft's software renderer is on every machine."""
    dxgi = ctypes.WinDLL("dxgi")  # type: ignore[attr-defined]
    dxgi.CreateDXGIFactory1.restype = ctypes.c_long
    factory = ctypes.c_void_p()
    if (
        dxgi.CreateDXGIFactory1(
            ctypes.byref(_IID_IDXGI_FACTORY1), ctypes.byref(factory)
        )
        < 0
    ):
        return []
    try:
        return list(_enumerate(factory))
    finally:
        _method(factory, _RELEASE)(factory)


def _enumerate(factory: ctypes.c_void_p):
    enum_adapters = _method(
        factory, _ENUM_ADAPTERS1, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)
    )
    index = 0
    while True:
        adapter = ctypes.c_void_p()
        # DXGI_ERROR_NOT_FOUND past the last adapter, a negative HRESULT.
        if enum_adapters(factory, index, ctypes.byref(adapter)) < 0:
            return
        index += 1
        try:
            desc = _AdapterDesc1()
            get_desc = _method(adapter, _GET_DESC1, ctypes.POINTER(_AdapterDesc1))
            if get_desc(adapter, ctypes.byref(desc)) < 0 or desc.Flags & _SOFTWARE:
                continue
            luid = desc.AdapterLuid
            yield Adapter(
                luid=f"0x{luid.HighPart & 0xFFFFFFFF:08x}_0x{luid.LowPart:08x}",
                name=desc.Description,
                dedicated_bytes=int(desc.DedicatedVideoMemory),
            )
        finally:
            _method(adapter, _RELEASE)(adapter)


def _method(obj: ctypes.c_void_p, slot: int, *argtypes):
    vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    prototype = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)  # type: ignore[attr-defined]
    return prototype(vtable[slot])
