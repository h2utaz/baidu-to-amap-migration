---
name: baidu-to-amap-migration
description: Migrate Baidu Maps favorites/collections to Amap (Gaode) favorites. Extract favorites from Baidu Maps web via API interception, convert BD-09 coordinates to GCJ-02, and batch inject into Amap via browser Console JS. Handles 400+ favorites at once.
version: 1.0.0
display_name: "百度→高德收藏迁移"
display_name_en: "Baidu→Amap Favorites Migration"
description_zh: "将百度地图收藏夹完整迁移到高德地图，包括坐标系转换（BD-09→GCJ-02）和批量注入。自动处理 400+ 收藏点。"
description_en: "Migrate Baidu Maps favorites to Amap (Gaode) with coordinate conversion (BD-09 to GCJ-02) and batch injection. Handles 400+ items."
visibility: "public"
allowed-tools: Bash(python3:*, npm:*, node:*), Read, Write
---

# Baidu → Amap (Gaode) Favorites Migration

Migrate all Baidu Maps favorites to Amap (Gaode) favorites in three steps:
1. Extract from Baidu (Playwright + API interception)
2. Convert coordinates (BD-09 → GCJ-02 → Amap pixel)
3. Inject into Amap (Chrome Console JS batch script)

## When to Use

User wants to migrate favorites/collections/bookmarks from Baidu Maps to Amap (Gaode).

## Prerequisites

- Python 3.11+ with `playwright` installed
- Node.js (for JS syntax validation only, optional)
- User has Baidu account and Amap account
- User can log into both in their normal Chrome browser

## Workflow

### Phase 1: Extract from Baidu Maps

1. **Install Playwright** if not already installed:
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. **Run the extraction script** (`scripts/extract_baidu.py`):
   - Launches an independent Chromium window (doesn't touch user's real Chrome)
   - Navigates to `https://map.baidu.com/fav/`
   - User logs in when prompted
   - Intercepts all `favdata` API responses
   - Extracts `type=10` POI favorites (name, address, BD-09 Mercator coordinates)
   - Saves to `baidu_favorites_raw.json`

3. **Verify output**: should contain `N` entries with `name`, `address`, `bd_lng`, `bd_lat`.

### Phase 2: Coordinate Conversion

1. **Run the conversion script** (`scripts/convert_coords.py`):
   - Input: `baidu_favorites_raw.json`
   - Step 1: BD-09 Mercator → BD-09 lng/lat (using Baidu's internal MC2LL matrix)
   - Step 2: BD-09 → GCJ-02 (standard public formula)
   - Output: `baidu_favorites_gcj02.json`

2. **Verify**: spot-check a few known locations on Amap.

### Phase 3: Generate Amap Injection Script

1. **Run the JS generator** (`scripts/generate_amap_js.py`):
   - Input: `baidu_favorites_gcj02.json`
   - Converts GCJ-02 → Amap internal pixel coordinates (Web Mercator, zoom 20)
   - Generates `amap_batch_add.js`

2. **User executes in browser**:
   - User opens `amap.com` in their real Chrome and logs in
   - User opens DevTools Console (F12 → Console)
   - User pastes the entire `amap_batch_add.js` content
   - Types `batchAddFavorites()` and presses Enter
   - Script runs ~2.5s per item, ~20 minutes for 487 items
   - Shows progress in console, alerts on completion

### Phase 4: Verify

1. User refreshes Amap page
2. Opens "我的收藏" (My Favorites)
3. Confirms all locations are present

## Important Notes

- **No Chrome profile pollution**: Extraction uses a temporary profile, deleted after use.
- **No Amap anti-bot**: Injection JS runs in user's own browser, bypassing CAPTCHA.
- **Rate limiting**: 2.5s delay between requests prevents rate limiting.
- **Coordinate accuracy**: BD-09 → GCJ-02 conversion uses official Baidu algorithms, accurate to within meters.
- **Custom locations only**: Injected locations use `type=1` (custom), not linked to Amap POI database. Names and coordinates are preserved.

## Troubleshooting

- **Baidu extraction returns 0 items**: User may not be logged in. Re-run, ensure login completes before the script continues.
- **Amap injection fails with auth error**: User must be logged into `amap.com` in the SAME tab where Console is opened.
- **Some locations appear in wrong spot**: Check if original Baidu coordinates were valid. Non-POI custom markers may have imprecise coordinates.
- **Console shows "Failed to load resource"**: Normal for ad/tracking blockers. Ignore if batch is progressing.
