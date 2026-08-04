# 工具速查（profile / SIMD / 缓存分析）

> 用于 performance-optimization-carmack-acton：遇到 profile、SIMD 指令或缓存分析需求时查阅。

## Profile 工具

| 平台 | 工具 | 安装 | 用途 |
|------|------|------|------|
| Linux | `perf` | `apt install linux-tools-common` | CPU 采样、缓存命中率、分支预测 |
| Linux | `simpleperf` | Android NDK 自带 | Android 设备上的 CPU 采样 |
| macOS | `Instruments` | Xcode 自带 | CPU/内存/GPU profiling |
| 跨平台 | `gprof` | GCC 自带 `-pg` 编译 | 函数级耗时统计 |
| 跨平台 | `VTune` | Intel 免费下载 | 缓存分析、内存带宽、SIMD 利用率 |
| 跨平台 | `Tracy` | `apt install tracy-profiler` | 实时帧级 profiling |

## SIMD 工具

| 工具 | 用途 |
|------|------|
| Intel Intrinsics Guide (software.intel.com) | SSE/AVX 指令速查 |
| ARM Neon Intrinsics Reference (developer.arm.com) | NEON 指令速查 |
| `gcc -Rpass=loop-vectorize` | 检查编译器是否自动向量化 |
| `objdump -d` 查看汇编 | 确认 SIMD 指令是否生成 |

## 缓存分析

```bash
# Linux: 查看缓存层次
lscpu | grep cache

# perf: 缓存命中率
perf stat -e cache-misses,cache-references,L1-dcache-load-misses ./your_binary

# 典型值参考
# L1: 32-64KB, 4 cycles
# L2: 256KB-1MB, 12 cycles
# L3: 4-32MB, 40 cycles
# 主存: 100+ cycles
```
