"""AERMAP Python 重构所需的基础数据模型。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(slots=True)
class Source:
    """表示排放源点位置。"""

    identifier: str
    x: float
    y: float
    elevation: float | None = None


@dataclass(slots=True)
class Receptor:
    """表示需要查询高程的受体位置。"""

    identifier: str
    x: float
    y: float
    base_height: float | None = None
    computed_height: float | None = None


@dataclass(slots=True)
class ElevationTile:
    """高程瓦片的内存表示。"""

    path: Path
    x0: float
    y0: float
    dx: float
    dy: float
    width: int
    height: int
    values: Sequence[Sequence[float]]

    def value_at(self, ix: int, iy: int) -> float:
        """返回指定索引的高程值。"""

        return float(self.values[iy][ix])


def chunked(seq: Iterable[Receptor], chunk_size: int) -> list[list[Receptor]]:
    """按固定大小切分受体序列，保持原始顺序。"""

    batch: list[list[Receptor]] = []
    current: list[Receptor] = []
    for receptor in seq:
        current.append(receptor)
        if len(current) >= chunk_size:
            batch.append(current)
            current = []
    if current:
        batch.append(current)
    return batch


__all__ = ["Source", "Receptor", "ElevationTile", "chunked"]
