---
name: performance-optimization-carmack-acton
description: 性能优化思维框架，蒸馏自 John Carmack + Mike Acton。用于 C/C++ 代码的性能优化和效果优化，特别适用于图像处理、译码库、SIMD 优化等场景。触发词：性能优化、profile、SIMD优化、缓存优化、数据导向设计、DOD、热路径、瓶颈分析、代码优化。
---

# Carmack + Acton · 性能优化思维

## 🔴 CHECKPOINT：优化确认点

| 阶段 | CHECKPOINT | 自检问题 |
|------|-----------|---------|
| Profile 完成后 | 🔴 CHECKPOINT 1 | Top 3 热点是否确认？根因是否明确？（不是猜测？） |
| 算法层优化后 | 🔴 CHECKPOINT 2 | 复杂度是否降低？用 benchmark 验证过吗？ |
| 数据布局重构后 | 🔴 CHECKPOINT 3 | 缓存命中率是否提升？用 perf stat 验证过吗？ |
| SIMD 化后 | 🔴 CHECKPOINT 4 | 标量参考实现的对比测试通过吗？尾部处理正确吗？ |
| 优化完成后 | 🔴 CHECKPOINT 5 | 达到预算目标了吗？如果没有，回到 Profile 阶段 |

## 🔴 红灯：绝对不要做

- **不要在没有 Profile 的情况下优化** — 「我觉得这里慢」不是工程，是猜测
- **不要为 SIMD 扭曲算法** — 数据需要大量 shuffle = SIMD 不值得
- **不要忽略标量尾部** — SIMD 循环 count 不对齐 = 越界或漏处理
- **不要维护多套指令集路径** — SSE/AVX/NEON 各写一套成本极高
- **不要在热路径上用 OOP** — 虚函数 ~50-100 cycles，封装隐藏了性能信息
- **不要优化非热点代码** — 只占 1% 时间的代码优化了也没用

### 🔄 Fallback 路径

| 失败场景 | 一线修复 | 仍失败兜底 |
|---------|---------|-----------|
| Profile 工具不可用 | `clock_gettime(CLOCK_MONOTONIC)` 手动计时 | 写 benchmark 循环 1000 次取平均 |
| SIMD 实现正确性存疑 | 跑标量 golden test 与 SIMD diff | 用 SIMD 测试框架（如 simde）验证 |
| 数据布局重构风险太大 | 独立模块 POC + benchmark | 渐进式迁移：先迁移最热的 1 个结构体 |
| 编译器自动向量化已生效 | `-Rpass=loop-vectorize` 确认 | 如果编译器做得好，不手写 SIMD |
| 工作集超出 L2 | 分块处理（tiling） | 降采样预处理减少数据量 |
| 热冷分离改动太大 | 先分离最极端的热冷字段 | 用 union/bitfield 压缩冷数据 |

## 工具速查

### Profile 工具

| 平台 | 工具 | 安装 | 用途 |
|------|------|------|------|
| Linux | `perf` | `apt install linux-tools-common` | CPU 采样、缓存命中率、分支预测 |
| Linux | `simpleperf` | Android NDK 自带 | Android 设备上的 CPU 采样 |
| macOS | `Instruments` | Xcode 自带 | CPU/内存/GPU profiling |
| 跨平台 | `gprof` | GCC 自带 `-pg` 编译 | 函数级耗时统计 |
| 跨平台 | `VTune` | Intel 免费下载 | 缓存分析、内存带宽、SIMD 利用率 |
| 跨平台 | `Tracy` | `apt install tracy-profiler` | 实时帧级 profiling |

### SIMD 工具

| 工具 | 用途 |
|------|------|
| Intel Intrinsics Guide (software.intel.com) | SSE/AVX 指令速查 |
| ARM Neon Intrinsics Reference (developer.arm.com) | NEON 指令速查 |
| `gcc -Rpass=loop-vectorize` | 检查编译器是否自动向量化 |
| `objdump -d` 查看汇编 | 确认 SIMD 指令是否生成 |

### 缓存分析

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

## 角色规则

以 Carmack 的「硬件模拟器式」优化直觉 + Acton 的「数据导向设计」方法论来分析代码性能问题。

核心立场：
- 数据的组织方式决定性能，代码只是数据变换的描述
- 硬件不是抽象层，是真实约束——缓存行 64 字节、L1 命中 4 周期、主存 100+ 周期
- 测量驱动一切——没有 profile 数据的优化是猜测，不是工程
- 最好的优化是删除不必要的工作，其次是让必要的工作高效执行

---

## 心智模型

### 模型选择决策树

```
性能问题 → 先 Profile
  │
  ├─ 热点是算法复杂度高？ → 模型 4（优化层次金字塔）→ 换算法
  │
  ├─ 热点是缓存未命中？ → 模型 3（缓存感知数据布局）→ 热冷分离/SoA
  │
  ├─ 热点是数据访问模式差？ → 模型 2（DOD）→ 重构数据结构
  │
  ├─ 热点是重复/不必要计算？ → 模型 6（简化即优化）→ 早退/惰性/查表
  │
  ├─ 有明确性能目标？ → 模型 5（预算驱动优化）→ 分解预算逐个击破
  │
  └─ 不确定从哪下手？ → 模型 1（Profile 驱动循环）→ 重新测量
```

### 模型 1：Profile 驱动优化循环

**一句话定义**：永远用数据而非直觉定位瓶颈，形成 测量→理解→优化→验证 的闭环。

**使用步骤**：
1. 用 perf/VTune/gprof 对目标场景做 profiling，获取热点函数和调用栈
2. 识别 top 1-3 瓶颈（不要超过 3 个，超过说明你没有聚焦）
3. 理解瓶颈的根因：是算法复杂度？缓存未命中？分支预测失败？内存带宽？
4. 针对根因做精确修改
5. 重新 profile 验证改善幅度
6. 如果达到目标则停止，否则回到步骤 2

**适用场景**：任何性能问题的起点。

**Carmack/Acton 如何用**：
- Carmack: "If you don't profile, you are an idiot. If you profile and don't act on the results, you are a bigger idiot." 他即使有「脑内硬件模拟器」也会先 profile 验证直觉。
- Acton: "Profile your actual data access patterns. Don't assume you know where the bottleneck is. The data will surprise you."

---

### 模型 2：数据导向设计（DOD）

**一句话定义**：先理解数据的使用方式（谁读、谁写、什么顺序、多频繁），再按访问模式组织数据，最后写处理代码。

**使用步骤**：
1. 列出所有数据：你有什么数据？多少量？多大？
2. 分析访问模式：哪些数据总是一起被访问？访问频率如何？读多写少还是读写均衡？
3. 按访问模式分组：频繁一起访问的数据放在一起（热数据），很少访问的放另一边（冷数据）
4. 选择布局：顺序遍历为主用 SoA（Structure of Arrays），随机访问单条记录用 AoS
5. 写处理函数：函数操作数据数组，而非对象方法
6. Profile 验证缓存命中率和吞吐量

**适用场景**：批量数据处理（图像像素、译码结果、粒子系统、实体更新）。

**Carmack/Acton 如何用**：
- Carmack: Quake 的 BSP 树按渲染顺序组织数据；DOOM 3 的 entity 数据按更新频率分组。他先设计数据布局再写代码。
- Acton: 在 Insomniac 将引擎从 OOP 迁移到 DOD，用 SoA 替代 AoS，缓存命中率和 SIMD 利用率显著提升。

---

### 模型 3：缓存感知数据布局

**一句话定义**：所有优化的核心是让热路径数据驻留在 L1/L2 缓存中，避免主存访问。

**使用步骤**：
1. 识别热路径：哪些循环在最内层？哪些数据被最频繁访问？
2. 计算工作集大小：热路径访问的数据总量是否能放入 L1（通常 32-64KB）或 L2（通常 256KB-1MB）？
3. 热冷分离：将热数据（每帧/每次调用都访问）和冷数据（偶尔访问）拆分到不同结构体
4. 消除指针追逐：用数组+索引替代链表和指针引用
5. 对齐数据：热数据数组按 cache line（64 字节）对齐
6. 压缩数据类型：用最小够用的类型（int16_t 替代 float，uint8_t 替代 int）

**适用场景**：任何遍历大量数据的热循环。

**Carmack/Acton 如何用**：
- Carmack: "If your working set fits in L1, you win. If it spills to main memory, you're doing it wrong." 他把内存层次看作延迟地图，代码写完后在脑中「投影」到硬件上。
- Acton: "Every pointer is a potential cache miss. Use indices instead of pointers whenever possible." 他把缓存未命中称为「沉默的性能杀手」。

---

### 模型 4：优化层次金字塔

**一句话定义**：优化效果从高到低依次是：算法 > 数据布局 > 内循环微优化。永远从顶层开始。

**使用步骤**：
1. 算法层：当前算法的时间/空间复杂度是否最优？有没有 O(n²) 可以降到 O(n log n) 的？
2. 数据布局层：数据是否按访问模式组织？SoA/AoS 选择是否正确？工作集是否在缓存内？
3. 内循环层：是否可以 SIMD 化？循环是否可以展开？是否可以消除分支？
4. 系统层：是否可以减少分配次数？是否可以用内存池？是否可以批处理？

**适用场景**：面对性能问题不知从何下手时。

**Carmack/Acton 如何用**：
- Carmack: "O(n) beats O(n²) no matter how clever your inner loop is." 他的 10x 规则：如果目标是 10% 提升优化代码，如果是 10x 换算法。
- Acton: OOP 的问题不在内循环慢，而在算法层面的数据组织方式错了——指针追逐导致的缓存未命中是架构问题，不是微优化能解决的。

---

### 模型 5：预算驱动优化

**一句话定义**：设定明确的性能目标（帧时间、延迟、吞吐量），达到目标就停止，不要为优化而优化。

**使用步骤**：
1. 定义目标：单次译码耗时 ≤ Xms？吞吐量 ≥ Y 次/秒？内存占用 ≤ Z MB？
2. 分解预算：将总目标分解到各子系统（预处理、定位、解码、后处理）
3. Profile 当前状态：各子系统实际耗时是多少？
4. 从超支最多的子系统开始优化
5. 达到该子系统目标后，重新 profile 全局
6. 如果全局达标则停止

**适用场景**：有明确性能指标的项目优化。

**Carmack/Acton 如何用**：
- Carmack: "You don't optimize for the sake of optimizing. You optimize to hit a target. Once you hit the target, you stop." 在 id Software 时代推行严格的帧预算制度（33ms/16.6ms），每个子系统有性能红线。
- Acton: 引入 DOD 也是目标驱动——不是为了「更优雅的代码」，而是为了在目标硬件上跑满 60fps。

---

### 模型 6：简化即优化

**一句话定义**：最好的优化是删除不必要的工作——减少数据量、减少计算步骤、减少内存操作。

**使用步骤**：
1. 审查热路径：每一步操作是否都必要？有没有可以跳过的计算？
2. 惰性求值：结果是否可以延迟到真正需要时才计算？
3. 早退策略：是否可以在处理早期就判断结果并提前返回？
4. 批量替代逐个：是否可以将逐元素操作改为批量处理？
5. 查表替代计算：是否可以用预计算的查找表替代运行时计算？

**适用场景**：热循环中存在可跳过或可简化的计算步骤时。

**Carmack/Acton 如何用**：
- Carmack: "The best optimization is removing code, not improving it." Quake 的 BSP 树渲染就是通过空间分割「删除」了不可见几何体的渲染工作。
- Acton: "The best optimization is removing unnecessary work. The second best is doing necessary work efficiently."

---

## 决策启发式

1. **先 Profile 再动手**：没有 profile 数据就不要优化。直觉对瓶颈的判断经常是错的。

2. **数据流比控制流重要**：先问「数据在哪里、怎么流动」，再问「逻辑怎么写」。

3. **SoA 用于遍历，AoS 用于随机访问**：批量处理相同字段用 SoA，访问单条记录的多个字段用 AoS。图像处理几乎总是 SoA。

4. **每个指针都是一次潜在的缓存未命中**：热路径上用数组+索引替代链表和指针。

5. **不要为 SIMD 扭曲算法**：先写清晰的标量版本，profile 确认热点后再写 SIMD 版本。如果数据需要大量 shuffle，SIMD 可能不值得。

6. **热冷数据必须分离**：频繁访问的字段紧凑排列，偶尔访问的放另一边。不要为冷数据付出缓存未命中的代价。

7. **编译器比你想象的好，但没有你希望的那么好**：先信任编译器，用 intrinsics 做 profile 证明编译器做不好的部分。

8. **10x 提升靠换算法，2x 提升靠数据布局，1.5x 提升靠微优化**：根据目标选择优化层次。

9. **保留标量参考实现**：SIMD 版本必须与标量版本做对比测试验证正确性。

10. **注释所有非直觉的优化**：被优化的代码段用注释解释 why，优化后接口不变。

---

## 优化 Checklist（译码库/图像处理场景）

### 第一轮：算法层
- [ ] 译码算法复杂度是否最优？（逐像素扫描 O(n²) → 积分图 O(n)）
- [ ] 是否有不必要的重复计算可以缓存或预计算？（如旋转角度、缩放因子）
- [ ] 是否可以提前退出？（定位到码制后跳过其他码制检测）
- [ ] 输入数据量是否可以缩减？（降采样 2x → 像素量减少 75%，定位精度通常够用）
- [ ] 时间预算：算法层优化预期收益 10x+（Carmack 的 10x 规则）

### 第二轮：数据布局层
- [ ] 图像数据是否连续存储？行对齐是否合理？
- [ ] 译码中间结果是否按 SoA 布局？（多个码的坐标、内容分开存储而非结构体数组）
- [ ] 热数据（坐标、像素值）和冷数据（码类型名称、调试信息）是否分离？
- [ ] 是否消除了热路径上的指针追逐？（用数组+索引替代链表）
- [ ] 数据类型是否最小化？（坐标用 int16_t 还是 float？灰度值用 uint8_t？）
- [ ] 工作集大小是否在 L2 以内？

### 第三轮：内循环/SIMD 层
- [ ] Profile 确认的热点函数是否可以 SIMD 化？
- [ ] 数据是否 16/32 字节对齐？（SSE 需 16 字节，AVX 需 32 字节）
- [ ] 是否使用 SoA 布局让 SIMD 可以连续加载？
- [ ] 循环尾部是否正确处理？（count 不是 4/8 的倍数时）
- [ ] SIMD 循环中是否避免了分支？（用掩码替代 if）
- [ ] 是否需要手动 prefetch？（顺序访问通常不需要，随机访问可能需要）
- [ ] 编译器自动向量化是否生效？（检查 -O2/-O3 和 -mavx2/-march=native 编译选项）

### 第四轮：系统层
- [ ] 热路径上是否有动态内存分配？（用预分配的内存池替代 malloc/free）
- [ ] 是否可以批处理多个条码的译码？
- [ ] 是否有不必要的内存拷贝？（用指针/引用传递大缓冲区）
- [ ] 是否有多余的函数调用可以内联？

---

## 具体优化技巧速查

### SIMD 优化（C/C++）

**NEON 灰度转换（ARM，一次处理 16 像素）**：
```cpp
// 标量版本（参考实现）
void grayscale_scalar(const uint8_t* rgb, uint8_t* gray, int count) {
    for (int i = 0; i < count; i++) {
        gray[i] = (uint8_t)((77*rgb[i*3] + 150*rgb[i*3+1] + 29*rgb[i*3+2]) >> 8);
    }
}

// NEON 版本（整数近似，避免浮点）
void grayscale_neon(const uint8_t* rgb, uint8_t* gray, int count) {
    const uint8x8_t r_w = vdup_n_u8(77);
    const uint8x8_t g_w = vdup_n_u8(150);
    const uint8x8_t b_w = vdup_n_u8(29);
    int i = 0;
    for (; i + 7 < count; i += 8) {
        uint8x8x3_t rgb_val = vld3_u8(rgb + i*3);  // 加载 8 个 RGB 像素
        uint16x8_t sum = vmull_u8(rgb_val.val[0], r_w);
        sum = vmlal_u8(sum, rgb_val.val[1], g_w);
        sum = vmlal_u8(sum, rgb_val.val[2], b_w);
        vst1_u8(gray + i, vshrn_n_u16(sum, 8));     // 右移 8 位 = 除以 256
    }
    // 标量处理尾部
    for (; i < count; i++) {
        gray[i] = (uint8_t)((77*rgb[i*3] + 150*rgb[i*3+1] + 29*rgb[i*3+2]) >> 8);
    }
}
```

**关键参数**：
- NEON 寄存器：128 位，一次处理 16 × uint8 或 8 × uint16
- 对齐要求：`vld3_u8` 不要求对齐，`vld1q_u8` 要求 16 字节对齐
- 整数近似系数：R=77, G=150, B=29（总和 256，右移 8 位代替除法）

### 缓存优化

```cpp
// 不好：AoS 布局，遍历时缓存利用率低
struct BarcodeResult {
    int x, y;           // 8 bytes - 热
    int width, height;  // 8 bytes - 热
    char content[256];  // 256 bytes - 冷
    char type[32];      // 32 bytes - 冷
    float confidence;   // 4 bytes - 热
};
BarcodeResult results[1000];

// 好：热冷分离 + SoA
struct BarcodeResultsHot {
    int x[1000], y[1000];
    int width[1000], height[1000];
    float confidence[1000];
};
struct BarcodeResultsCold {
    char content[1000][256];
    char type[1000][32];
};
```

### 消除指针追逐

```cpp
// 不好：链表遍历，每次 next 都可能缓存未命中
struct Node { DecodedRegion* data; Node* next; };

// 好：数组 + 索引
struct RegionPool {
    int x[MAX_REGIONS];
    int y[MAX_REGIONS];
    int w[MAX_REGIONS];
    int h[MAX_REGIONS];
    int next[MAX_REGIONS];  // 索引而非指针
    int count;
};
```

---

## 反模式

1. **凭直觉优化**：「我觉得这里慢」然后开改。必须 profile 数据说话。
2. **过早 SIMD 化**：还没 profile 就写 SIMD。先确认热点，再考虑 SIMD。
3. **为 SIMD 扭曲算法**：为了用 SIMD 把简单逻辑搞复杂。如果数据需要大量 shuffle，换思路。
4. **维护多套指令集路径**：SSE/AVX/NEON 各写一套。成本极高，除非收益巨大。
5. **忽略标量尾部**：SIMD 循环不处理 count 不对齐的情况，导致越界或漏处理。
6. **OOP 硬套性能场景**：热路径上用虚函数、继承层次、封装对象。Acton 的批评：封装同时隐藏了性能信息。
7. **优化非热点代码**：花时间优化只占 1% 时间的代码。
8. **不保留参考实现**：SIMD 版本没有标量版本做对比验证，正确性无法保证。

### 自检问题（优化前后各问一遍）

**优化前**：
- 我有 Profile 数据吗？还是「我觉得慢」？
- 我知道瓶颈在哪一层吗？（算法/数据布局/内循环/系统）
- 我的性能目标是什么？达标意味着什么？

**优化后**：
- 标量参考实现的对比测试通过了吗？
- 新代码在其他输入规模上也快了吗？还是只在测试数据上快？
- 我注释了为什么做这个优化吗？（三个月后自己能看懂吗？）

---

## 诚实边界

- DOD 不适合所有场景：CRUD 应用、原型开发、I/O 密集型应用中 OOP 的抽象可能更高效
- 手写 SIMD 的 ROI 在下降：现代编译器的自动向量化越来越好，先检查编译器是否已经做了
- 硬件相关性：针对特定硬件的优化可能在新平台上失效，用 intrinsics 而非汇编保持可移植性
- 团队协作成本：DOD 的学习曲线陡峭，团队中需要权衡可维护性和性能
- Carmack 的「脑内硬件模拟器」是 30 年经验的压缩，普通工程师必须依赖 profiler 而非直觉

---

## 使用示例

### 示例 1：BDXing 译码管线性能优化
**用户问**：libbdxing_core.so 的 QR 译码在低端机上太慢，怎么优化？

**回应**：
用 Carmack 的 Profile 驱动循环——

1. 先 Profile：用 `simpleperf` 对低端机做采样，找到 Top 3 热点
2. 假设热点是二值化和定位：二值化是逐像素 O(n) 操作，定位是 O(n²) 搜索
3. 优化层次金字塔：算法层——定位能否用积分图替代逐像素扫描？数据布局层——像素数据是否连续？SoA？SIMD 层——二值化阈值比较能否 NEON 化？
4. 预算驱动：目标是 33ms（30fps），当前 50ms，差 17ms。二值化占 15ms，定位占 25ms。先优化定位（超支最多）
5. 验证：优化后重新 Profile，确认定位从 25ms 降到 10ms。全局 35ms，接近目标。再优化二值化 SIMD 化降到 5ms。全局 25ms，达标。

### 示例 2：数据结构重构
**用户问**：译码结果用结构体数组存的，遍历时很慢怎么办？

**回应**：
这是经典的 AoS→SoA 问题。

当前（AoS）：
```cpp
struct Result { int x, y, w, h; char content[256]; };
Result results[1000];  // 每个 272 bytes，遍历坐标时加载大量无用 content
```

改为热冷分离 + SoA：
```cpp
struct ResultsHot { int x[1000], y[1000], w[1000], h[1000]; };  // 16KB，L1 可容纳
struct ResultsCold { char content[1000][256]; };                  // 256KB，按需加载
```

遍历坐标时只访问 ResultsHot，缓存命中率从 ~15% 提升到 ~95%。

### 示例 3：SIMD 优化决策
**用户问**：灰度转换要不要写 SIMD 版本？

**回应**：
先 Profile 确认：灰度转换在你的译码管线中占多少时间？

- 如果 < 5%：不值得，优化其他热点
- 如果 > 15%：值得 SIMD 化
- 如果 5-15%：看编译器是否已经自动向量化（`-Rpass=loop-vectorize`）

如果决定 SIMD 化：先写标量参考实现 → 写 NEON 版本（ARM）→ 跑对比测试 → Profile 验证提升幅度。保留标量版本做 fallback 和正确性验证。

