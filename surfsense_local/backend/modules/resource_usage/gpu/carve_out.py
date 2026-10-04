# Below this, a card's own memory is an integrated part's reservation (Intel
# 128 MB, a Ryzen APU's BIOS default 512 MB), not memory a model is placed in.
MIN_DEDICATED_BYTES = 1024**3


def is_carve_out(dedicated_bytes: int) -> bool:
    return dedicated_bytes < MIN_DEDICATED_BYTES
