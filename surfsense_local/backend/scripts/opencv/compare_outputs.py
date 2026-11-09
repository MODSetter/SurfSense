"""Compare two record_calls.py outputs byte for byte.

    python -I compare_outputs.py <expected.npz> <actual.npz>

Exits 1 naming each output that differs, and how far apart a numeric one is.
"""

import sys

import numpy as np


def difference(name: str, expected: np.ndarray, actual: np.ndarray) -> str | None:
    if expected.dtype != actual.dtype or expected.shape != actual.shape:
        return (
            f"{name}: {expected.dtype}{expected.shape} vs {actual.dtype}{actual.shape}"
        )
    if expected.tobytes() == actual.tobytes():
        return None
    if expected.dtype.kind in "biuf":
        gap = np.abs(expected.astype(np.float64) - actual.astype(np.float64))
        return f"{name}: {np.count_nonzero(gap)} of {gap.size} differ, by up to {gap.max()}"
    return f"{name}: bytes differ"


def main() -> None:
    expected = np.load(sys.argv[1], allow_pickle=False)
    actual = np.load(sys.argv[2], allow_pickle=False)
    found = []
    for name in sorted(set(expected.files) | set(actual.files)):
        if name not in expected.files or name not in actual.files:
            found.append(
                f"{name}: only in {sys.argv[1] if name in expected.files else sys.argv[2]}"
            )
        elif line := difference(name, expected[name], actual[name]):
            found.append(line)
    print(f"{len(expected.files)} outputs compared byte for byte; {len(found)} differ")
    for line in found:
        print(line)
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
