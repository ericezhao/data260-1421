import hashlib
import math
import re

DIM = 64


def embed_text(text: str) -> list[float]:
    """Hash each word into a 64-d vector and L2-normalize it."""
    vec = [0.0] * DIM
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:2], "big") % DIM
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vec[index] += sign
    norm = math.sqrt(sum(value * value for value in vec)) or 1.0
    return [value / norm for value in vec]


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))
