"""支持并行的 AERMAP Python 计算管线。

该模块重现 Fortran 地形预处理器的主要步骤，强调确定性 I/O、
易向量化以及可选的并行执行路径。所有注释均采用中文说明。
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from importlib import import_module, util
from typing import Sequence

_numpy_spec = util.find_spec("numpy")
np = import_module("numpy") if _numpy_spec else None  # type: ignore[assignment]

from .config import AermapConfig
from .io import load_elevation_tile, load_receptors, load_sources, write_results
from .models import ElevationTile, Receptor, chunked


def _bilinear_interpolation(tile: ElevationTile, x: float, y: float) -> float:
    """双线性插值，高度超界时回退到最近网格点。"""

    # 将坐标转换为瓦片内的浮点索引
    fx = (x - tile.x0) / tile.dx
    fy = (y - tile.y0) / tile.dy

    if fx < 0 or fy < 0 or fx >= tile.width - 1 or fy >= tile.height - 1:
        # 超出瓦片范围，采用最安全的最近点回退，确保结果稳定
        return tile.value_at(int(max(0, min(tile.width - 1, round(fx)))), int(max(0, min(tile.height - 1, round(fy)))))

    ix, iy = int(fx), int(fy)
    wx, wy = fx - ix, fy - iy

    if np is not None:
        # NumPy 向量化路径
        a = np.array(
            [
                [tile.value_at(ix, iy), tile.value_at(ix + 1, iy)],
                [tile.value_at(ix, iy + 1), tile.value_at(ix + 1, iy + 1)],
            ]
        )
        weights = np.array([[1 - wx, wx]])
        interp = weights @ a @ np.array([[1 - wy], [wy]])
        return float(interp.squeeze())

    # 纯 Python 路径，便于无第三方依赖的环境
    v00 = tile.value_at(ix, iy)
    v10 = tile.value_at(ix + 1, iy)
    v01 = tile.value_at(ix, iy + 1)
    v11 = tile.value_at(ix + 1, iy + 1)
    return float((1 - wx) * (1 - wy) * v00 + wx * (1 - wy) * v10 + (1 - wx) * wy * v01 + wx * wy * v11)


def _process_receptors(tile: ElevationTile, receptors: Sequence[Receptor]) -> list[Receptor]:
    """对单个分块的受体执行插值。"""

    processed: list[Receptor] = []
    for receptor in receptors:
        computed = _bilinear_interpolation(tile, receptor.x, receptor.y)
        # 使用字典解包复制，避免原对象被并行修改导致数据竞争
        processed.append(Receptor(**{**receptor.__dict__, "computed_height": computed}))
    return processed


def _process_chunk(tile: ElevationTile, receptors: Sequence[Receptor]) -> list[Receptor]:
    """包装函数，便于进程池调用。"""

    return _process_receptors(tile, receptors)


class AermapPipeline:
    """AERMAP Python 计算的高层调度器。"""

    def __init__(self, config: AermapConfig, tile: ElevationTile | None = None):
        self.config = config
        self.tile = tile

    def run(self) -> list[Receptor]:
        """执行读取、计算和写出，保持顺序与 Fortran 一致。"""

        # 优先加载高程瓦片，确保 DEM/GeoTIFF 路径直接可用
        tile = self.tile
        if tile is None:
            if not self.config.tile_file:
                raise ValueError("必须提供 tile 对应的 DEM/GeoTIFF 文件路径")
            tile = load_elevation_tile(self.config.tile_file)
            self.tile = tile

        # 先解析源点，顺序与 Fortran 程序一致，为后续补充源相关逻辑留出位置
        load_sources(self.config.source_file)
        receptors = load_receptors(self.config.receptor_file)

        # 按固定大小切分受体，避免并行乱序
        receptor_chunks = chunked(receptors, self.config.chunk_size)

        if self.config.max_workers == 1 or len(receptor_chunks) == 1:
            processed = [_process_chunk(tile, chunk) for chunk in receptor_chunks]
            flat: list[Receptor] = [item for sublist in processed for item in sublist]
        else:
            with ProcessPoolExecutor(max_workers=self.config.max_workers) as pool:
                futures = {pool.submit(_process_chunk, tile, chunk): idx for idx, chunk in enumerate(receptor_chunks)}
                ordered_results: list[list[Receptor]] = [list() for _ in receptor_chunks]
                for future in as_completed(futures):
                    idx = futures[future]
                    ordered_results[idx] = future.result()
                flat = [item for sublist in ordered_results for item in sublist]

        # 在主进程统一写出，确保文件内容确定性
        write_results(self.config.output_file, flat, precision=self.config.precision)
        return flat


__all__ = ["AermapPipeline"]
