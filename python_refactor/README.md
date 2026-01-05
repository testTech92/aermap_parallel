# Python 版本重构说明（AERMAP）

本目录提供将 Fortran 版 AERMAP 预处理器迁移到 Python 的骨架代码，并以中文总结实现思路、性能取舍以及潜在风险。设计目标是保证输入/输出格式与 Fortran 一致，同时便于向量化和并行化加速。

## 设计目标
- 保持输入/输出顺序和数值精度，方便与 Fortran 结果逐行比对。
- 使用结构化数据模型让计算步骤更清晰、更易测。
- 预留 NumPy 向量化与多进程并行入口，确保在纯 Python 环境下也能回退运行。

## 模块概览
- `config.py`：`AermapConfig` 捕获与 Fortran 相同的输入/输出路径，并提供精度、分块大小、并行线程数等性能参数。
- `models.py`：源、受体和高程瓦片的轻量级数据类，以及稳定分块的工具函数。
- `io.py`：集中处理输入/输出，控制分隔符和数值格式，保证读写顺序不变；新增 `load_elevation_tile`，优先使用 rasterio（GDAL 绑定）读取 DEM/GeoTIFF 并保留原始分辨率与行列顺序，缺失时回退到 `osgeo.gdal`。
- `pipeline.py`：高层管线，串接读写、插值计算与并行调度。

## 实现过程与关键决策
1. **路径规范化**：`AermapConfig.expand_paths` 允许基于 Fortran 工作目录补全相对路径，保证老输入文件可直接复用，并支持直接指定 `tile_file`（DEM/GeoTIFF）。
2. **确定性读写**：`io.py` 过滤空行和注释但保持原始行序；写出阶段按配置控制分隔符和数值精度，避免并行导致的重排。
3. **插值核心**：`_bilinear_interpolation` 先做边界检查，超界时回退为最近点，避免异常；在检测到 NumPy 时走向量化矩阵乘法，否则执行可移植的标量计算。
4. **并行与分块**：`models.chunked` 提前切分受体列表，`ProcessPoolExecutor` 按分块索引收集结果，确保合并后顺序与输入一致；当 `max_workers=1` 或仅有单块时退化为串行逻辑，降低开销。
5. **输出稳定性**：写出阶段统一在主进程完成，避免多进程竞争同一文件。
6. **DEM/GeoTIFF 读取**：`load_elevation_tile` 使用 rasterio 获取仿射变换、分辨率和 nodata，填充掩膜区域后生成 `ElevationTile`；若未安装 rasterio，则回退到 `osgeo.gdal` + NumPy 读取，仍保持行列顺序与 nodata 处理一致，确保与 Fortran 版的输入输出一致性。

## 潜在问题与改进建议（Bug 分析）
- **瓦片选择缺失**：当前示例假设所有受体共享同一 `ElevationTile`，尚未实现基于坐标定位不同瓦片；在实际数据下必须增加瓦片索引与缓存策略，否则会返回错误高程。
- **输入校验不足**：`load_sources`/`load_receptors` 对列数与类型未做严格校验，遇到格式漂移时可能抛出 `ValueError`；建议补充字段校验与错误行提示。
- **NumPy 可选路径**：当 NumPy 不可用时性能退化明显；在生产环境应明确安装依赖或增加 Cython/Numba 加速方案。
- **并行复制成本**：当前把 `ElevationTile` 作为参数传入子进程，若瓦片较大可能导致进程间复制开销；可通过共享内存或在子进程内懒加载文件优化。
- **依赖声明**：DEM/GeoTIFF 读取优先依赖 rasterio；若缺失会明确报错并回退到 `osgeo.gdal`（需 NumPy），部署时需二选一安装好依赖或提供纯 Python 备选方案。

## 后续步骤
- 将 Fortran 中 `sub_*.f` 的 DEM/NED/NADCON 读取与转换逻辑逐一移植到 `io.py` 和新的计算模块。
- 补充回归测试，对比一组稳定的 Fortran 输出，验证坐标转换、插值和格式化是否一致。
- 根据数据规模调优 `chunk_size` 与 `max_workers`，并评估缓存策略对内存的影响。
