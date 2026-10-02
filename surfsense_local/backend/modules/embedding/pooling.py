"""One vector per text from a model's per-token output, as its spec says."""

import numpy as np

from modules.embedding.spec import Pooling


def pool(pooling: Pooling, output: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """`output` is (texts, tokens, width), or (texts, width) for a build that
    pools inside its own graph. Padding is on the right, as the tokenizer pads."""
    if pooling is Pooling.IN_MODEL:
        return output
    if pooling is Pooling.CLS:
        return output[:, 0]
    if pooling is Pooling.MEAN:
        weights = mask[:, :, None].astype(output.dtype)
        return (output * weights).sum(axis=1) / np.maximum(weights.sum(axis=1), 1)
    last = mask.sum(axis=1) - 1
    return output[np.arange(output.shape[0]), last]
