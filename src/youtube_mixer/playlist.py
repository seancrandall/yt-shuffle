"""Video data, full-coverage shuffle, and search.

The shuffle here is the whole point of the app: a Fisher–Yates shuffle over the *entire*
fetched list. Playback walks the resulting order with next/prev, so every video is reached
once before any repeats — exactly what YouTube's built-in shuffle fails to do on long lists.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Video:
    id: str
    title: str
    thumbnail_url: str | None = None


def shuffle(videos: Sequence[Video], seed: int | None = None) -> list[Video]:
    """Return a new list with the videos in a full-coverage Fisher–Yates order.

    Does not mutate the input. With a fixed ``seed`` the result is reproducible (useful for
    tests and a "replay this shuffle" feature later).
    """
    rng = random.Random(seed)
    result = list(videos)
    for i in range(len(result) - 1, 0, -1):
        j = rng.randint(0, i)
        result[i], result[j] = result[j], result[i]
    return result


def search(videos: Sequence[Video], query: str) -> list[Video]:
    """Case-insensitive substring filter over titles. An empty query returns everything."""
    q = query.strip().lower()
    if not q:
        return list(videos)
    return [v for v in videos if q in v.title.lower()]
