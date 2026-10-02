"""One collection of PDH wildcard counters, built fresh for every sample.

A wildcard counter lists only the instances alive when it was added (measured:
a process started after that never appears), so a query kept open would never
see llama-server once it restarts. Utilization is a rate, so its raw values
outlive the query and PDH computes the rate from the previous sample's pair.
"""

import ctypes
from collections.abc import Sequence
from ctypes import wintypes
from types import TracebackType

_FMT_DOUBLE = 0x00000200
_FMT_LARGE = 0x00000400
_FMT_NOCAP100 = 0x00008000
_MORE_DATA = 0x800007D2
_VALID = {0, 1}  # PDH_CSTATUS_VALID_DATA, PDH_CSTATUS_NEW_DATA


class _Value(ctypes.Union):
    _fields_ = [
        ("longValue", ctypes.c_long),
        ("doubleValue", ctypes.c_double),
        ("largeValue", ctypes.c_longlong),
    ]


class _FormattedValue(ctypes.Structure):
    _fields_ = [("CStatus", wintypes.DWORD), ("value", _Value)]


class _Item(ctypes.Structure):
    _fields_ = [("szName", ctypes.c_wchar_p), ("FmtValue", _FormattedValue)]


class RawValue(ctypes.Structure):
    """PDH_RAW_COUNTER: one instance's reading, kept to pair with the next."""

    _fields_ = [
        ("CStatus", wintypes.DWORD),
        ("TimeStamp", wintypes.FILETIME),
        ("FirstValue", ctypes.c_longlong),
        ("SecondValue", ctypes.c_longlong),
        ("MultiCount", wintypes.DWORD),
    ]


class _RawItem(ctypes.Structure):
    _fields_ = [("szName", ctypes.c_wchar_p), ("RawValue", RawValue)]


def _library():
    pdh = ctypes.WinDLL("pdh")  # type: ignore[attr-defined]
    handle = ctypes.c_void_p
    count = ctypes.POINTER(wintypes.DWORD)
    pdh.PdhOpenQueryW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.c_size_t,
        ctypes.POINTER(handle),
    ]
    pdh.PdhAddEnglishCounterW.argtypes = [
        handle,
        wintypes.LPCWSTR,
        ctypes.c_size_t,
        ctypes.POINTER(handle),
    ]
    pdh.PdhCollectQueryData.argtypes = [handle]
    pdh.PdhGetFormattedCounterArrayW.argtypes = [
        handle,
        wintypes.DWORD,
        count,
        count,
        ctypes.c_void_p,
    ]
    pdh.PdhGetRawCounterArrayW.argtypes = [handle, count, count, ctypes.c_void_p]
    pdh.PdhCalculateCounterFromRawValue.argtypes = [
        handle,
        wintypes.DWORD,
        ctypes.POINTER(RawValue),
        ctypes.POINTER(RawValue),
        ctypes.POINTER(_FormattedValue),
    ]
    pdh.PdhCloseQuery.argtypes = [handle]
    for function in (
        pdh.PdhOpenQueryW,
        pdh.PdhAddEnglishCounterW,
        pdh.PdhCollectQueryData,
        pdh.PdhGetFormattedCounterArrayW,
        pdh.PdhGetRawCounterArrayW,
        pdh.PdhCalculateCounterFromRawValue,
        pdh.PdhCloseQuery,
    ):
        function.restype = ctypes.c_long
    return pdh


class CounterQuery:
    """Open, add, collect once, read, close: a context manager per sample."""

    def __init__(self, paths: Sequence[str]) -> None:
        self._pdh = _library()
        self._query = ctypes.c_void_p()
        _check(self._pdh.PdhOpenQueryW(None, 0, ctypes.byref(self._query)), "open")
        self._counters: dict[str, ctypes.c_void_p] = {}
        try:
            for path in paths:
                counter = ctypes.c_void_p()
                # English names, so a localized Windows finds the same counters.
                status = self._pdh.PdhAddEnglishCounterW(
                    self._query, path, 0, ctypes.byref(counter)
                )
                _check(status, path)
                self._counters[path] = counter
            _check(self._pdh.PdhCollectQueryData(self._query), "collect")
        except OSError:
            self.close()
            raise

    def __enter__(self) -> "CounterQuery":
        return self

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _error: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._pdh.PdhCloseQuery(self._query)

    def bytes(self, path: str) -> dict[str, int]:
        """A raw count such as bytes in use, readable from one collection."""
        items = self._array(path, _Item, self._formatted(_FMT_LARGE))
        return {
            item.szName: int(item.FmtValue.value.largeValue)
            for item in items
            if item.szName is not None and item.FmtValue.CStatus in _VALID
        }

    def raw(self, path: str) -> dict[str, RawValue]:
        """Copies, so they outlive this query and pair with the next sample's."""
        items = self._array(path, _RawItem, self._pdh.PdhGetRawCounterArrayW)
        return {
            item.szName: RawValue.from_buffer_copy(item.RawValue)
            for item in items
            if item.szName is not None and item.RawValue.CStatus in _VALID
        }

    def rate(self, path: str, current: RawValue, previous: RawValue) -> float | None:
        """The percent between two raw readings of one instance."""
        value = _FormattedValue()
        status = self._pdh.PdhCalculateCounterFromRawValue(
            self._counters[path],
            # Uncapped: a process's share of an engine can round past 100.
            _FMT_DOUBLE | _FMT_NOCAP100,
            ctypes.byref(current),
            ctypes.byref(previous),
            ctypes.byref(value),
        )
        if status != 0 or value.CStatus not in _VALID:
            return None
        return float(value.value.doubleValue)

    def _formatted(self, fmt: int):
        def read(counter, size, count, buffer):
            return self._pdh.PdhGetFormattedCounterArrayW(
                counter, fmt, size, count, buffer
            )

        return read

    def _array(self, path: str, item_type, read) -> list:
        counter = self._counters[path]
        size, count = wintypes.DWORD(0), wintypes.DWORD(0)
        # Anything but "more data" means the counter has no instances.
        status = read(counter, ctypes.byref(size), ctypes.byref(count), None)
        if status & 0xFFFFFFFF != _MORE_DATA:
            return []
        buffer = (ctypes.c_byte * size.value)()
        if read(counter, ctypes.byref(size), ctypes.byref(count), buffer) != 0:
            return []
        items = ctypes.cast(buffer, ctypes.POINTER(item_type))
        # Views into `buffer`, which each one keeps alive.
        return [items[index] for index in range(count.value)]


def _check(status: int, what: str) -> None:
    if status != 0:
        raise OSError(f"PDH {what} failed: 0x{status & 0xFFFFFFFF:08x}")
