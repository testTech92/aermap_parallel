"""Python 版 AERMAP 重构的输入/输出工具。"""
from __future__ import annotations

from importlib import import_module, util
from pathlib import Path
from typing import Iterable, Iterator

from .models import ElevationTile, Receptor, Source

rasterio_spec = util.find_spec("rasterio")
rasterio = import_module("rasterio") if rasterio_spec else None  # type: ignore[assignment]
gdal_spec = util.find_spec("osgeo.gdal")
gdal = import_module("osgeo.gdal") if gdal_spec else None  # type: ignore[assignment]
numpy_spec = util.find_spec("numpy")
np = import_module("numpy") if numpy_spec else None  # type: ignore[assignment]

def _read_rows(path: Path, delimiter: str = ",") -> Iterator[list[str]]:
    """逐行读取文本，跳过空行和注释，保持顺序不变。"""

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            yield [segment.strip() for segment in line.split(delimiter)]


def load_sources(path: Path, delimiter: str = ",") -> list[Source]:
    """按固定顺序读取源点，解析失败将抛出异常，便于尽早暴露输入错误。"""

    sources: list[Source] = []
    for row in _read_rows(path, delimiter):
        identifier, x_str, y_str, *rest = row
        elevation = float(rest[0]) if rest else None
        sources.append(Source(identifier=identifier, x=float(x_str), y=float(y_str), elevation=elevation))
    return sources


def load_receptors(path: Path, delimiter: str = ",") -> list[Receptor]:
    """按原始顺序读取受体，保证后续写出与输入一致。"""

    receptors: list[Receptor] = []
    for row in _read_rows(path, delimiter):
        identifier, x_str, y_str, *rest = row
        base_height = float(rest[0]) if rest else None
        receptors.append(Receptor(identifier=identifier, x=float(x_str), y=float(y_str), base_height=base_height))
    return receptors


def write_results(path: Path, receptors: Iterable[Receptor], precision: int = 3, delimiter: str = ",") -> None:
    """以接近 Fortran 的格式写出结果，保持顺序与精度。"""

    fmt = f"{{:.{precision}f}}"
    with path.open("w", encoding="utf-8") as handle:
        for receptor in receptors:
            height_str = fmt.format(receptor.computed_height or 0.0)
            handle.write(delimiter.join([receptor.identifier, fmt.format(receptor.x), fmt.format(receptor.y), height_str]))
            handle.write("\n")


__all__ = ["load_sources", "load_receptors", "write_results"]


def _load_with_rasterio(path: Path) -> ElevationTile:
    """优先使用 rasterio（GDAL 绑定）读取瓦片，保留掩膜。"""

    if rasterio is None:  # pragma: no cover - 动态路径保护
        raise ImportError("rasterio 未安装")

    with rasterio.open(path) as dataset:
        band1 = dataset.read(1, masked=True)
        transform = dataset.transform

        x0 = float(transform.c)
        y0 = float(transform.f)
        dx = float(transform.a)
        dy = float(abs(transform.e))  # 常见为负值，取绝对值便于索引

        fill_value = dataset.nodata if dataset.nodata is not None else float("nan")
        values = band1.filled(fill_value)

        return ElevationTile(
            path=path,
            x0=x0,
            y0=y0,
            dx=dx,
            dy=dy,
            width=dataset.width,
            height=dataset.height,
            values=values,
        )


def _load_with_gdal(path: Path) -> ElevationTile:
    """当未安装 rasterio 时回退到 osgeo.gdal，仍保持行列顺序与 nodata。"""

    if gdal is None or np is None:  # pragma: no cover - 动态路径保护
        raise ImportError("需要安装 osgeo.gdal 与 numpy 才能读取 DEM/GeoTIFF 数据")

    dataset = gdal.Open(path.as_posix(), gdal.GA_ReadOnly)
    if dataset is None:  # pragma: no cover - 与文件存在性相关
        raise FileNotFoundError(path)

    transform = dataset.GetGeoTransform()
    x0 = float(transform[0])
    dx = float(transform[1])
    y0 = float(transform[3])
    dy = float(abs(transform[5]))

    band = dataset.GetRasterBand(1)
    nodata = band.GetNoDataValue()
    fill_value = nodata if nodata is not None else float("nan")
    values = band.ReadAsArray().astype(float)
    if nodata is not None:
        values[values == nodata] = fill_value  # type: ignore[index]
    else:
        values[np.isnan(values)] = fill_value  # type: ignore[index]

    return ElevationTile(
        path=path,
        x0=x0,
        y0=y0,
        dx=dx,
        dy=dy,
        width=dataset.RasterXSize,
        height=dataset.RasterYSize,
        values=values,
    )


def load_elevation_tile(path: Path) -> ElevationTile:
    """读取 DEM/GeoTIFF 瓦片，优先 rasterio，缺失时回退到 GDAL。"""

    if rasterio is not None:
        return _load_with_rasterio(path)
    if gdal is not None and np is not None:
        return _load_with_gdal(path)

    raise ImportError("需要安装 rasterio 或 osgeo.gdal 才能读取 DEM/GeoTIFF 数据")


__all__.append("load_elevation_tile")
