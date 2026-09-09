# Baidu → Amap Favorites Migration

[中文](#chinese) | [English](#english)

把**百度地图网页版收藏**批量迁到**高德地图（Amap）**，自动完成坐标系转换。适合任意体量收藏（几十到上千均可），不改动你本机 Chrome 配置。

**Version:** v1.1.0 · **License:** MIT

---

<a id="chinese"></a>
## 中文

### 适用场景

- 从百度地图换到高德，想带走「我的收藏」
- 收藏点较多，不想逐条手动添加
- 需要自己掌控数据：先导出 JSON，再按需导入

不保证覆盖百度侧全部收藏类型（当前优先提取地点类 POI）；路线、文件夹等可能被跳过并在日志中统计。

### 工作原理

两套地图坐标系不同：

| 平台 | 坐标系 |
|------|--------|
| 百度地图 | BD-09（网页内部多为墨卡托整数坐标） |
| 高德地图 | GCJ-02（火星坐标） |

流水线：

```text
百度网页收藏 ── Playwright 拦截 favdata ──▶ raw JSON（BD-09 墨卡托）
                                              │
                    BD-09 墨卡托 → BD-09 经纬度 → GCJ-02
                                              │
                                         GCJ-02 JSON
                                              │
                              生成 Console 脚本 amap_batch_add.js
                                              │
                     在已登录的 amap.com 控制台执行 ──▶ 高德「我的收藏」
```

### 环境要求

- Python 3.11+（3.9+ 一般也可用）
- 百度地图账号、高德地图账号
- Chromium / Chrome（提取用独立临时浏览器；导入用你自己的 Chrome）

### 安装

```bash
git clone https://github.com/h2utaz/baidu-to-amap-migration.git
cd baidu-to-amap-migration
pip install playwright
playwright install chromium
```

### 使用步骤

在项目根目录执行：

```bash
# 1) 提取百度收藏（弹出浏览器，完成登录即可）
python3 scripts/extract_baidu.py
# 输出: baidu_favorites_raw.json

# 2) 坐标转换
python3 scripts/convert_coords.py
# 输出: baidu_favorites_gcj02.json

# 3) 生成高德导入脚本
python3 scripts/generate_amap_js.py
# 输出: amap_batch_add.js
```

然后导入高德：

1. 打开 [amap.com](https://www.amap.com/) 并登录  
2. `F12` → **Console**  
3. 粘贴 `amap_batch_add.js` 全部内容并回车  
4. 执行：`batchAddFavorites()`  
5. 完成后刷新收藏页核对  

耗时约 `条数 × 间隔秒数`（默认间隔 2.5s）。中途可关页，之后再跑一次即可续传。

### 常用参数

| 脚本 | 参数 | 说明 |
|------|------|------|
| `extract_baidu.py` | `-o PATH` | 原始 JSON 输出路径 |
| `extract_baidu.py` | `--headless` | 无头模式（需登录时通常不推荐） |
| `convert_coords.py` | `-i` / `-o` | 输入 / 输出 JSON |
| `generate_amap_js.py` | `-i` / `-o` | 输入 / 输出路径 |
| `generate_amap_js.py` | `-d` / `--delay` | 每条请求间隔（秒），默认 `2.5` |
| `generate_amap_js.py` | `--default-city` | 地址识别不出城市时的回退城市，默认 `北京` |

示例：

```bash
python3 scripts/extract_baidu.py -o data/raw.json
python3 scripts/convert_coords.py -i data/raw.json -o data/gcj02.json
python3 scripts/generate_amap_js.py -i data/gcj02.json -o out/amap_batch_add.js \
  --delay 3 --default-city 上海
```

### 导入控制（浏览器 Console）

| 命令 | 作用 |
|------|------|
| `batchAddFavorites()` | 开始导入；自动跳过已成功项 |
| `batchAddFavorites({force:true})` | 忽略进度，全部重跑 |
| `resetBatchProgress()` | 仅清空本机进度（localStorage） |

进度保存在 `amap.com` 域名下的 `localStorage`，换浏览器/清站点数据后需重新导入。

### 输出字段

| 字段 | 阶段 | 说明 |
|------|------|------|
| `name` / `address` | 提取 | 名称与地址 |
| `bd_lng` / `bd_lat` | 提取 | 百度 BD-09 墨卡托坐标 |
| `tags` | 提取 / 转换 | 百度侧标签（导入时写入高德 `tag`） |
| `gcj02_lng` / `gcj02_lat` | 转换 | 高德可用的 GCJ-02 经纬度 |

### 说明与限制

- 提取使用**临时 Chromium 配置**，结束后删除，不写入你的日常 Chrome 配置  
- 导入脚本在**你已登录的浏览器标签页**内请求高德接口，请合理设置 `--delay`，避免过快请求  
- 坐标转换采用公开的 BD-09 → GCJ-02 算法，误差通常在数米级；原始百度坐标不准时，导入后也会偏  
- 导入类型为高德「自定义地点」，一般**不会**自动关联高德 POI 详情  
- 城市码按地址/名称关键词推断；识别失败时使用 `--default-city`

### 常见问题

**提取为 0 条或登录超时？**  
在弹出的 Chromium 窗口完成百度登录。脚本同时检查收藏页 URL 与登录 Cookie（如 `BDUSS`），约 120 秒内未检测到会退出。

**控制台报认证 / CSRF 错误？**  
确认已在 **amap.com 同一标签页**登录，再粘贴并执行脚本。

**中断后续跑？**  
重新粘贴同一份（或重新生成的）脚本后执行 `batchAddFavorites()`。

**个别点位置不准？**  
先对照 `baidu_favorites_gcj02.json` 里的坐标；源数据偏差无法靠转换完全消除。

### 目录结构

```text
baidu-to-amap-migration/
├── README.md
├── SKILL.md                 # Agent Skill 描述（可选）
├── LICENSE
└── scripts/
    ├── extract_baidu.py     # 提取
    ├── convert_coords.py    # 坐标转换
    └── generate_amap_js.py  # 生成导入脚本
```

生成的 `*.json` / `amap_batch_add.js` 默认被 `.gitignore` 忽略，勿把含个人足迹的数据提交到仓库。

---

<a id="english"></a>
## English

Migrate **Baidu Maps web favorites** to **Amap (Gaode)** with automatic BD-09 → GCJ-02 conversion. Works for small or large collections. Extraction uses a temporary browser profile and does not modify your everyday Chrome settings.

**Version:** v1.1.0 · **License:** MIT

### When to use

- Switching from Baidu Maps to Amap and want to keep saved places
- Too many favorites to add by hand
- Prefer an exportable JSON intermediate you can inspect before import

Only place-like POI favorites are extracted today; other Baidu collection types may be skipped (counts are logged).

### Pipeline

```text
Baidu web favorites ── Playwright favdata capture ──▶ raw JSON (BD-09 Mercator)
                                                         │
                       BD-09 Mercator → BD-09 deg → GCJ-02
                                                         │
                                                    GCJ-02 JSON
                                                         │
                                         generate amap_batch_add.js
                                                         │
                    run in logged-in amap.com Console ──▶ Amap favorites
```

### Setup

```bash
git clone https://github.com/h2utaz/baidu-to-amap-migration.git
cd baidu-to-amap-migration
pip install playwright
playwright install chromium
```

Requires Python 3.11+ (3.9+ often works), Baidu + Amap accounts, and Chrome/Chromium.

### Usage

```bash
python3 scripts/extract_baidu.py          # → baidu_favorites_raw.json
python3 scripts/convert_coords.py         # → baidu_favorites_gcj02.json
python3 scripts/generate_amap_js.py       # → amap_batch_add.js
```

Then on [amap.com](https://www.amap.com/) (logged in): DevTools → Console → paste `amap_batch_add.js` → run `batchAddFavorites()`.

Runtime ≈ `count × delay` (default delay 2.5s). Re-run `batchAddFavorites()` to resume after interruption; use `batchAddFavorites({force:true})` to restart; `resetBatchProgress()` clears saved progress.

### Useful flags

```bash
python3 scripts/extract_baidu.py -o data/raw.json
python3 scripts/convert_coords.py -i data/raw.json -o data/gcj02.json
python3 scripts/generate_amap_js.py -i data/gcj02.json -o out/amap_batch_add.js \
  --delay 3 --default-city 上海
```

| Script | Flags |
|--------|--------|
| `extract_baidu.py` | `-o`, `--headless` |
| `convert_coords.py` | `-i`, `-o` |
| `generate_amap_js.py` | `-i`, `-o`, `--delay`, `--default-city` |

### Notes

- Temp Chromium profile for extraction; deleted afterward  
- Import runs in **your** logged-in tab — keep a sensible `--delay`  
- Conversion accuracy is typically within a few meters; bad source coords stay bad  
- Imported items are custom places (not linked Amap POIs)  
- City codes are guessed from text; override fallback with `--default-city`  
- Do not commit personal `*.json` / generated JS (ignored by default)

### FAQ

- **0 items / login timeout:** finish Baidu login in the opened window (URL + auth cookie required).  
- **Auth / CSRF errors on Amap:** run the script in the same logged-in `amap.com` tab.  
- **Wrong pin location:** check GCJ-02 values in the JSON; conversion cannot fix bad originals.

### Project layout

```text
scripts/extract_baidu.py
scripts/convert_coords.py
scripts/generate_amap_js.py
```

---

## License

MIT
