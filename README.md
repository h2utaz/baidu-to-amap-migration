# Baidu → Amap (Gaode) Favorites Migration

[中文](#chinese) | [English](#english)

---

<a name="chinese"></a>
## 中文

将百度地图网页版收藏夹完整迁移到高德地图（高德），支持 400+ 收藏点批量处理。

**当前版本：v1.1.0**

### 原理

百度地图和高德地图使用不同的坐标系：
- **百度地图**：BD-09 坐标系（内部使用墨卡托投影）
- **高德地图**：GCJ-02 坐标系（火星坐标系）

本工具分三步完成迁移：

```
百度地图网页版 ──[Playwright 截获 API]──▶ baidu_favorites_raw.json (BD-09 墨卡托)
        │
        ▼
   [坐标转换: BD-09 墨卡托 → BD-09 度 → GCJ-02]
        │
        ▼
 baidu_favorites_gcj02.json ──[生成 JS 脚本]──▶ amap_batch_add.js
        │
        ▼
   [Chrome Console 运行 JS] ──▶ 高德地图「我的收藏」
```

### 快速开始

#### 前提条件

- Python 3.11+
- 百度地图和高德地图账号
- Chrome 浏览器

#### 第一步：安装依赖

```bash
pip install playwright
playwright install chromium
```

#### 第二步：提取百度收藏

```bash
python3 scripts/extract_baidu.py
```

浏览器窗口会自动打开。登录百度账号后，脚本自动抓取所有收藏点。

输出：`baidu_favorites_raw.json`

#### 第三步：坐标转换

```bash
python3 scripts/convert_coords.py
```

BD-09 墨卡托 → BD-09 经纬度 → GCJ-02 经纬度。

输出：`baidu_favorites_gcj02.json`

#### 第四步：生成注入脚本

```bash
python3 scripts/generate_amap_js.py
```

输出：`amap_batch_add.js`

#### 第五步：批量注入高德

1. 打开 `https://www.amap.com/`，登录高德账号
2. 按 F12 → Console（控制台）
3. 复制 `amap_batch_add.js` 全部内容，粘贴到控制台，回车
4. 输入 `batchAddFavorites()`，回车
5. 等待完成（每条约 2.5 秒，487 条约 20 分钟）
6. 弹窗提示完成后，刷新高德收藏页验证

中断后续跑：再次执行 `batchAddFavorites()`（会跳过 localStorage 里已成功的项）。强制重头：`batchAddFavorites({force:true})`。清空进度：`resetBatchProgress()`。

城市默认回退（地址无法识别城市时）：

```bash
python3 scripts/generate_amap_js.py --default-city 上海
```

### 字段说明

| 字段 | 来源 | 说明 |
|------|------|------|
| `name` | 百度收藏名称 | POI 名称或自定义名称 |
| `address` | 百度收藏地址 | 详细地址 |
| `bd_lng` / `bd_lat` | 百度 API | BD-09 墨卡托整数坐标 |
| `gcj02_lng` / `gcj02_lat` | 转换后 | 高德可用的小数经纬度 |

### 注意事项

- **不会修改你的 Chrome 配置**：提取过程使用独立临时配置，用完即删
- **不会触发高德风控**：注入脚本在你自己的浏览器中跑，高德以为是正常操作
- **坐标精度**：使用百度官方转换算法，误差在数米内
- **自定义类型**：导入的收藏类型为「自定义地点」（type=1），不关联高德 POI 数据库
- **速率限制**：默认 2.5 秒间隔，如遇限流可增加 `--delay` 参数

### 常见问题

**Q: 提取 Baidu 收藏时返回 0 条？**  
A: 确认已在弹出的浏览器窗口中登录百度账号。脚本会检测收藏页 URL + 百度登录 Cookie（如 `BDUSS`）；120 秒内未检测到会报错退出。

**Q: 高德注入时提示认证失败？**  
A: 确保 `amap.com` 已登录，且在**同一标签页**的控制台中执行脚本。

**Q: 注入中途刷新/关页了怎么办？**  
A: 重新粘贴脚本后执行 `batchAddFavorites()` 即可续跑；进度存在该域名的 localStorage。

**Q: 某些点位偏移？**  
A: 原始百度坐标可能不精确（尤其是非 POI 标记点）。坐标转换精度理论上在数米内。

**Q: 能否自定义注入间隔？**  
A: `python3 scripts/generate_amap_js.py --delay 3`（默认 2.5 秒）

---

<a name="english"></a>
## English

Migrate all favorites from Baidu Maps web to Amap (Gaode) in three automated steps.

### How It Works

Baidu Maps and Amap use different coordinate systems:
- **Baidu Maps**: BD-09 (internal Mercator projection)
- **Amap**: GCJ-02 (Mars Coordinates)

```
Baidu Web ──[Playwright API interception]──▶ raw JSON (BD-09 Mercator)
        │
        ▼
   [Convert: BD-09 Mercator → BD-09 deg → GCJ-02]
        │
        ▼
   GCJ-02 JSON ──[Generate JS]──▶ amap_batch_add.js
        │
        ▼
   [Chrome Console runs JS] ──▶ Amap "My Favorites"
```

### Quick Start

```bash
# 1. Install
pip install playwright && playwright install chromium

# 2. Extract from Baidu (login when browser opens)
python3 scripts/extract_baidu.py

# 3. Convert coordinates
python3 scripts/convert_coords.py

# 4. Generate injection script
python3 scripts/generate_amap_js.py

# 5. Manually: open amap.com, F12 → Console,
#    paste amap_batch_add.js, run batchAddFavorites()
#    (re-run to resume; batchAddFavorites({force:true}) to restart)
```

### Notes

- **No Chrome profile pollution**: uses temp profile, deleted after extraction
- **No Amap anti-bot**: JS runs in user's own browser
- **Coordinate accuracy**: within meters using official algorithms
- **Rate limiting**: 2.5s default delay, configurable via `--delay`
- **Resume**: progress saved in `localStorage`; re-run `batchAddFavorites()` after interruption
- **City fallback**: `--default-city` when address has no known city name

### License

MIT
