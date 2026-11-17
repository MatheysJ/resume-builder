from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class FitResult:
    font_size: float
    pages: int
    fits: bool
    attempts: int


def fit_font_size(
    count_pages: Callable[[float], int],
    *,
    max_pages: int = 1,
    min_size: float = 8.0,
    max_size: float = 12.0,
    step: float = 0.1,
) -> FitResult:
    if max_pages < 1:
        raise ValueError("max_pages deve ser pelo menos 1")
    if step <= 0:
        raise ValueError("step deve ser positivo")
    if min_size <= 0 or min_size > max_size:
        raise ValueError("use 0 < min_size <= max_size")

    last = math.floor((max_size - min_size) / step + 1e-9)
    cache: dict[int, int] = {}

    def size_at(index: int) -> float:
        return round(min_size + index * step, 4)

    def pages_at(index: int) -> int:
        if index not in cache:
            cache[index] = count_pages(size_at(index))
        return cache[index]

    def result(index: int, fits: bool) -> FitResult:
        return FitResult(size_at(index), pages_at(index), fits, len(cache))

    if pages_at(last) <= max_pages:
        return result(last, True)
    if pages_at(0) > max_pages:
        return result(0, False)

    # Binary search assumes the page count never drops as the font grows.
    low, high = 0, last
    while high - low > 1:
        middle = (low + high) // 2
        if pages_at(middle) <= max_pages:
            low = middle
        else:
            high = middle
    return result(low, True)
