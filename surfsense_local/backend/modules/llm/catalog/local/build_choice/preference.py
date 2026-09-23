"""The quantization order a curated model's default build is chosen by.

Most quality per byte first, unquantized last. Unsloth Studio publishes the same
order for the same purpose; it is a convention, reviewed here, not measured.
"""

PREFERENCE: tuple[str, ...] = (
    "UD-Q4_K_XL",
    "UD-Q4_K_L",
    "UD-Q5_K_XL",
    "UD-Q3_K_XL",
    "UD-Q6_K_XL",
    "UD-Q8_K_XL",
    "UD-Q2_K_XL",
    "Q4_K_M",
    "Q4_K_S",
    "Q5_K_M",
    "Q5_K_S",
    "Q6_K",
    "Q8_0",
    "Q3_K_M",
    "Q3_K_L",
    "Q3_K_S",
    "Q2_K",
    "IQ4_NL",
    "IQ4_XS",
    "F16",
    "BF16",
    "F32",
)
