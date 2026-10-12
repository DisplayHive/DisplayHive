"""Aspect-ratio helpers shared by Designs, Screens and Layout variations.

A ratio is stored as a "W:H" string as the admin entered it ("16:9", "21:9",
"16:10", "9:16" -- deliberately not reduced to lowest terms, so familiar names
survive); two ratios are the same if their W/H values are equal, and any ratio
equal to 16:9 is the base. 16:9 is the *base* ratio: a Layout's own container
membership and every ContentContainer's own top/left/width/height columns
are the 16:9 variant; other ratios are stored as Layout variations and
per-ratio container positions (see models/content.py).
"""

import math
import re
from typing import Iterable, Optional

BASE_RATIO = '16:9'

_RATIO_RE = re.compile(r'^\s*(\d{1,4})\s*:\s*(\d{1,4})\s*$')


def normalize_ratio(value) -> Optional[str]:
    """Return *value* as a clean "W:H" string, or None if it isn't a valid
    ratio. Anything equal to 16:9 (e.g. "32:18") becomes BASE_RATIO."""
    if not isinstance(value, str):
        return None
    m = _RATIO_RE.match(value)
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    if w <= 0 or h <= 0:
        return None
    if w * 9 == h * 16:
        return BASE_RATIO
    return f'{w}:{h}'


def same_ratio(a: str, b: str) -> bool:
    """True if two valid "W:H" strings describe the same shape (4:3 == 8:6)."""
    aw, ah = a.split(':')
    bw, bh = b.split(':')
    return int(aw) * int(bh) == int(bw) * int(ah)


def ratio_value(ratio: str) -> float:
    """Numeric width/height of a normalized ratio string."""
    w, h = ratio.split(':')
    return int(w) / int(h)


def best_ratio(target: Optional[str], available: Iterable[str]) -> str:
    """Pick the ratio from *available* closest to *target*.

    Distance is measured on a log scale, so 4:3 is as far from 1:1 as 1:1 is
    from 3:4. Equal distances resolve to the base ratio, then to the first listed.
    Falls back to BASE_RATIO when *available* is empty or *target* invalid.
    """
    options = list(dict.fromkeys(available))
    if not options:
        return BASE_RATIO
    target_norm = normalize_ratio(target) if target else None
    if target_norm is None:
        return BASE_RATIO if BASE_RATIO in options else options[0]
    t = math.log(ratio_value(target_norm))
    return min(
        options,
        key=lambda r: (round(abs(math.log(ratio_value(r)) - t), 9), r != BASE_RATIO),
    )


def parse_ratio_list(raw) -> list:
    """Parse a JSON list (or list) of ratio strings into a de-duplicated list
    of normalized ratios, dropping invalid entries and the base ratio."""
    import json
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else []
        except ValueError:
            raw = []
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        n = normalize_ratio(item)
        if n and n != BASE_RATIO and not any(same_ratio(n, o) for o in out):
            out.append(n)
    return out
