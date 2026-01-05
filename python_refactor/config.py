"""Python 版 AERMAP 重构的配置对象。

配置项在保持与 Fortran 输入一致的同时，提供了性能相关的可调参数。
所有说明与注释均使用中文，便于快速理解迁移细节。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(slots=True)
class AermapConfig:
    """面向用户的管线配置。

    属性说明
    -------
    source_file: Fortran 使用的源点定义文件路径。
    receptor_file: Fortran 使用的受体定义文件路径。
    tile_directory: DEM/NED 等高程瓦片所在目录。
    tile_file: 单个 DEM/GeoTIFF 瓦片路径；在无瓦片索引逻辑时可直接指定。
    output_file: 计算结果输出文件路径。
    precision: 写出数值的精度，保持与 Fortran 格式一致。
    chunk_size: 并行时每个任务包含的受体数量。
    max_workers: 并行进程数，默认 ``None`` 交由 Python 决定。
    cache_tiles: 是否缓存瓦片以避免重复磁盘读取。
    """

    source_file: Path
    receptor_file: Path
    tile_directory: Path
    output_file: Path
    tile_file: Path | None = None
    precision: int = 3
    chunk_size: int = 512
    max_workers: Optional[int] = None
    cache_tiles: bool = True

    def expand_paths(self, base: Optional[Path] = None) -> None:
        """基于给定基目录展开相对路径。

        目的：兼容以 Fortran 可执行文件所在目录为参照的旧式输入清单。
        """

        if base:
            self.source_file = Path(base, self.source_file)
            self.receptor_file = Path(base, self.receptor_file)
            self.tile_directory = Path(base, self.tile_directory)
            self.output_file = Path(base, self.output_file)
            if self.tile_file:
                self.tile_file = Path(base, self.tile_file)

    @classmethod
    def from_mapping(cls, mapping: Iterable[tuple[str, str]], base: Optional[Path] = None) -> "AermapConfig":
        """从键值对创建配置实例。

        用途：兼容可解析为键值记录的旧控制文件格式。
        """

        data = {
            key: Path(value) if "file" in key or "directory" in key else value for key, value in mapping
        }
        config = cls(**data)  # type: ignore[arg-type]
        config.expand_paths(base)
        return config


__all__ = ["AermapConfig"]
