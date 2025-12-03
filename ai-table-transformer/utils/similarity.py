def levenshtein(a: str, b: str) -> int:
    """Simple Levenshtein distance."""
    a, b = a or "", b or ""
    if a == b:
        return 0
    if len(a) == 0:
        return len(b)
    if len(b) == 0:
        return len(a)
    v0 = list(range(len(b) + 1))
    v1 = [0] * (len(b) + 1)
    for i in range(len(a)):
        v1[0] = i + 1
        for j in range(len(b)):
            cost = 0 if a[i] == b[j] else 1
            v1[j + 1] = min(v1[j] + 1, v0[j + 1] + 1, v0[j] + cost)
        v0, v1 = v1, v0
    return v0[len(b)]


def name_similarity(a: str, b: str) -> float:
    """Normalized similarity between two column names."""
    if not a and not b:
        return 1.0
    a = (a or "").lower()
    b = (b or "").lower()
    dist = levenshtein(a, b)
    max_len = max(len(a), len(b), 1)
    return 1.0 - dist / max_len
