# 代码示例（SIMD / 缓存优化 / 消除指针追逐）

> 用于 performance-optimization-carmack-acton：需要参考实现时查阅。

## SIMD 优化（C/C++）

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

## 缓存优化

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

## 消除指针追逐

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
