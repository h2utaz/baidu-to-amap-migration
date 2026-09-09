#!/usr/bin/env python3
"""
Amap (Gaode) Batch Injection Script Generator
===============================================
Converts GCJ-02 coordinates to Amap's internal Web Mercator pixel coordinates
(zoom level 20), then generates a JavaScript file that can be pasted into the
Chrome Console on amap.com to batch-add all favorites via the addFav API.

Why this works:
  - Amap's addFav API uses Web Mercator pixel coordinates, not decimal degrees
  - The API requires an x-csrf-token from the browser's Cookie
  - Running JS in the user's own browser bypasses Amap's anti-bot verification
  - 2.5s delay between requests prevents rate limiting

Usage:
    python3 generate_amap_js.py [--input baidu_favorites_gcj02.json] [--output amap_batch_add.js] [--delay 2.5]

Then:
    1. Open amap.com in Chrome and log in
    2. F12 → Console
    3. Paste the entire amap_batch_add.js content
    4. Type batchAddFavorites() and press Enter
    5. Wait ~20 minutes for completion (487 items × 2.5s)

Resume after interruption:
    batchAddFavorites()          # skip already-succeeded ids in localStorage
    batchAddFavorites({force:true})  # ignore saved progress and start over
    resetBatchProgress()         # clear saved progress only
"""

import json
import math
import os
import sys
import hashlib
import argparse


# Common city / province-level adcodes. Longer names first so e.g. 哈尔滨 beats 哈尔滨市-less 哈尔.
CITY_CODES = [
    ("乌鲁木齐", 650100), ("呼和浩特", 150100), ("哈尔滨", 230100),
    ("石家庄", 130100), ("齐齐哈尔", 230200), ("张家口", 130700),
    ("秦皇岛", 130300), ("景德镇", 360200), ("连云港", 320700),
    ("西宁", 630100), ("拉萨", 540100), ("银川", 640100),
    ("北京", 110000), ("上海", 310000), ("天津", 120000), ("重庆", 500000),
    ("广州", 440100), ("深圳", 440300), ("杭州", 330100), ("成都", 510100),
    ("武汉", 420100), ("南京", 320100), ("西安", 610100), ("长沙", 430100),
    ("苏州", 320500), ("郑州", 410100), ("青岛", 370200), ("大连", 210200),
    ("厦门", 350200), ("宁波", 330200), ("福州", 350100), ("济南", 370100),
    ("合肥", 340100), ("昆明", 530100), ("南昌", 360100), ("沈阳", 210100),
    ("长春", 220100), ("太原", 140100), ("贵阳", 520100), ("南宁", 450100),
    ("海口", 460100), ("三亚", 460200), ("无锡", 320200), ("佛山", 440600),
    ("东莞", 441900), ("珠海", 440400), ("中山", 442000), ("惠州", 441300),
    ("温州", 330300), ("嘉兴", 330400), ("金华", 330700), ("绍兴", 330600),
    ("常州", 320400), ("徐州", 320300), ("南通", 320600), ("扬州", 321000),
    ("烟台", 370600), ("潍坊", 370700), ("临沂", 371300), ("洛阳", 410300),
    ("开封", 410200), ("芜湖", 340200), ("泉州", 350500), ("漳州", 350600),
    ("桂林", 450300), ("丽江", 530700), ("大理", 532900), ("宜昌", 420500),
    ("襄阳", 420600), ("株洲", 430200), ("湘潭", 430300), ("绵阳", 510700),
    ("德阳", 510600), ("兰州", 620100), ("宝鸡", 610300), ("咸阳", 610400),
]


def lnglat_to_amap_pixel(lng, lat):
    """
    Convert GCJ-02 decimal degrees to Amap's internal Web Mercator
    pixel coordinates at zoom level 20.

    Total pixels at zoom 20 = 2^20 × 256 = 268,435,456

    Args:
        lng: GCJ-02 longitude (decimal degrees)
        lat: GCJ-02 latitude (decimal degrees)

    Returns:
        (point_x, point_y): integer pixel coordinates for Amap addFav API
    """
    tile_size = 256
    zoom = 20
    total_pixels = (2 ** zoom) * tile_size

    # Longitude: linear mapping
    x = (lng + 180.0) / 360.0 * total_pixels

    # Latitude: Mercator projection
    lat_rad = lat * math.pi / 180.0
    mercator = math.log(math.tan(math.pi / 4.0 + lat_rad / 2.0))
    y = (1.0 - mercator / math.pi) / 2.0 * total_pixels

    return int(round(x)), int(round(y))


def guess_city_code(name, address, default_city="北京", default_code=110000):
    """
    Determine city code from name/address text.
    Falls back to --default-city when no city name matches.
    """
    combined = f"{address or ''} {name or ''}"
    for city_name, code in CITY_CODES:
        if city_name in combined:
            return code, city_name
    return default_code, default_city


def resolve_default_city(default_city):
    """Map a user-provided default city name to an adcode."""
    for city_name, code in CITY_CODES:
        if city_name == default_city or default_city.startswith(city_name):
            return code, city_name
    print(f"[WARN] Unknown --default-city '{default_city}', falling back to 北京/110000")
    return 110000, "北京"


def _tags_to_amap_tag(tags):
    """Join Baidu tags into a single Amap tag string (skip empty parts)."""
    if not tags:
        return ""
    parts = [str(t).strip() for t in tags if str(t).strip()]
    return ",".join(parts)


def generate_js(input_path, output_path, delay=2.5, default_city="北京"):
    """Generate the batch injection JavaScript file."""
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    default_code, default_city_name = resolve_default_city(default_city)

    items = []
    for i, fav in enumerate(data):
        px, py = lnglat_to_amap_pixel(fav["gcj02_lng"], fav["gcj02_lat"])
        city_code, city_name = guess_city_code(
            fav.get("name", ""),
            fav.get("address", ""),
            default_city=default_city_name,
            default_code=default_code,
        )
        id_str = hashlib.md5(f'{fav["name"]}_{px}_{py}_{i}'.encode()).hexdigest()
        tag = _tags_to_amap_tag(fav.get("tags", []))

        item = {
            "id": id_str,
            "data": {
                "item_id": id_str,
                "custom_name": fav["name"],
                "custom_address": fav.get("address", fav["name"]),
                "name": fav["name"],
                "address": fav.get("address", fav["name"]),
                "point_x": px,
                "point_y": py,
                "city_code": city_code,
                "city_name": city_name,
                "phone_numbers": "",
                "custom_phone_numbers": "",
                "comment": "",
                "tag": tag,
                "top_time": "",
                "type": 1,  # 1 = custom/non-POI location
            },
            "type": 101,
            "ver": "alGtGQAAAAABAAAB",
        }
        items.append(item)

    json_data = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    delay_ms = int(delay * 1000)

    js_code = f"""// ─── Amap Batch Add Favorites ──────────────────────────────────────────
// Generated by baidu-to-amap-migration tool
// {len(items)} items, {delay}s delay per item, ~{int(len(items) * delay / 60)} minutes total
//
// HOW TO USE:
//   1. Open https://www.amap.com/ in Chrome and log in
//   2. Open DevTools Console (F12 → Console)
//   3. Paste this ENTIRE file content and press Enter
//   4. Type: batchAddFavorites()
//   5. Wait until the alert popup appears
//
// RESUME:
//   batchAddFavorites()              // skip ids already marked success
//   batchAddFavorites({{force:true}})  // ignore progress and re-import all
//   resetBatchProgress()             // clear saved progress only
//
// WARNING: Do NOT close this tab or refresh while the script is running
//          (progress is saved after each success, so a re-run can resume).

const FAVORITES = {json_data};
const TOTAL = FAVORITES.length;
const DELAY = {delay_ms};
const PROGRESS_KEY = 'baidu_to_amap_batch_progress_v1';

function loadProgress() {{
    try {{
        const raw = localStorage.getItem(PROGRESS_KEY);
        if (!raw) return {{ successIds: [], failedIds: [] }};
        const parsed = JSON.parse(raw);
        return {{
            successIds: Array.isArray(parsed.successIds) ? parsed.successIds : [],
            failedIds: Array.isArray(parsed.failedIds) ? parsed.failedIds : [],
        }};
    }} catch (e) {{
        console.warn('Failed to load progress, starting fresh:', e.message);
        return {{ successIds: [], failedIds: [] }};
    }}
}}

function saveProgress(successIds, failedIds) {{
    localStorage.setItem(PROGRESS_KEY, JSON.stringify({{
        successIds: Array.from(successIds),
        failedIds: Array.from(failedIds),
        updatedAt: new Date().toISOString(),
        total: TOTAL,
    }}));
}}

function resetBatchProgress() {{
    localStorage.removeItem(PROGRESS_KEY);
    console.log('Cleared batch progress (' + PROGRESS_KEY + ').');
}}

function isAddSuccess(result) {{
    if (!result || typeof result !== 'object') return false;
    if (result.code === 0 || result.code === '0') return true;
    if (result.message === 'success' || result.msg === 'success') return true;
    // Some Amap responses nest a numeric code under data
    if (result.data && typeof result.data === 'object' &&
        (result.data.code === 0 || result.data.code === '0')) {{
        return true;
    }}
    return false;
}}

async function addFavorite(item) {{
    const csrf = document.cookie.match(/x-csrf-token=([^;]+)/)?.[1] || '';
    if (!csrf) {{
        throw new Error('Missing x-csrf-token cookie. Are you logged into amap.com?');
    }}
    const body = new URLSearchParams();
    body.append('data[0][id]', item.id);
    body.append('data[0][data][item_id]', item.data.item_id);
    body.append('data[0][data][custom_address]', item.data.custom_address);
    body.append('data[0][data][custom_name]', item.data.custom_name);
    body.append('data[0][data][type]', String(item.data.type));
    body.append('data[0][data][address]', item.data.address);
    body.append('data[0][data][phone_numbers]', '');
    body.append('data[0][data][comment]', '');
    body.append('data[0][data][name]', item.data.name);
    body.append('data[0][data][point_x]', String(item.data.point_x));
    body.append('data[0][data][point_y]', String(item.data.point_y));
    body.append('data[0][data][top_time]', '');
    body.append('data[0][data][city_code]', String(item.data.city_code));
    body.append('data[0][data][custom_phone_numbers]', '');
    body.append('data[0][data][city_name]', item.data.city_name);
    body.append('data[0][data][tag]', item.data.tag || '');
    body.append('data[0][type]', '101');
    body.append('data[0][ver]', item.ver);

    const resp = await fetch('https://www.amap.com/service/fav/addFav', {{
        method: 'POST',
        headers: {{
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'x-csrf-token': csrf,
            'x-requested-with': 'XMLHttpRequest',
        }},
        body: body.toString(),
        credentials: 'include',
    }});
    if (!resp.ok) {{
        throw new Error('HTTP ' + resp.status);
    }}
    return await resp.json();
}}

async function batchAddFavorites(options = {{}}) {{
    const force = !!(options && options.force);
    const progress = force
        ? {{ successIds: [], failedIds: [] }}
        : loadProgress();
    const successIds = new Set(progress.successIds);
    const failedIds = new Set(progress.failedIds);

    if (force) {{
        resetBatchProgress();
        console.log('Force mode: cleared previous progress.');
    }}

    const pending = FAVORITES.filter(item => !successIds.has(item.id));
    console.log(
        'Starting batch: ' + TOTAL + ' total, ' +
        successIds.size + ' already done, ' +
        pending.length + ' pending, ' + (DELAY / 1000) + 's delay each...'
    );

    if (pending.length === 0) {{
        alert('全部收藏已导入完成（进度已保存）。\\n如需强制重跑，请执行 batchAddFavorites({{force:true}})');
        return;
    }}

    let success = 0, failed = 0, skipped = successIds.size;
    const startTime = Date.now();

    for (let i = 0; i < pending.length; i++) {{
        const item = pending[i];
        const done = skipped + i + 1;
        const pct = (done / TOTAL * 100).toFixed(1);
        try {{
            const r = await addFavorite(item);
            if (isAddSuccess(r)) {{
                success++;
                successIds.add(item.id);
                failedIds.delete(item.id);
                console.log('[' + done + '/' + TOTAL + '] ' + pct + '% OK: ' + item.data.name);
            }} else {{
                failed++;
                failedIds.add(item.id);
                console.warn('[' + done + '/' + TOTAL + '] ' + pct + '% FAIL: ' + item.data.name, r);
            }}
        }} catch (e) {{
            failed++;
            failedIds.add(item.id);
            console.error('[' + done + '/' + TOTAL + '] ' + pct + '% ERROR: ' + item.data.name, e.message);
        }}

        saveProgress(successIds, failedIds);

        if (i < pending.length - 1) {{
            await new Promise(r => setTimeout(r, DELAY));
        }}
    }}

    const elapsed = ((Date.now() - startTime) / 1000 / 60).toFixed(1);
    console.log('=== DONE === (elapsed: ' + elapsed + ' min)');
    console.log(
        'This run OK: ' + success +
        ', This run FAIL: ' + failed +
        ', Previously skipped: ' + skipped +
        ', Total success saved: ' + successIds.size +
        '/' + TOTAL
    );
    alert(
        '导入完成！已耗时: ' + elapsed + ' 分钟\\n' +
        '本轮成功: ' + success + '\\n' +
        '本轮失败: ' + failed + '\\n' +
        '累计成功: ' + successIds.size + '/' + TOTAL + '\\n\\n' +
        '失败项可再次执行 batchAddFavorites() 续跑\\n' +
        '刷新收藏页面查看结果 (F5)'
    );
}}

console.log(
    'Data loaded: ' + TOTAL + ' items. Type batchAddFavorites() to start ' +
    '(resumes from localStorage). resetBatchProgress() to clear.'
);
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(js_code)

    file_size = os.path.getsize(output_path)
    est_minutes = len(items) * delay / 60
    print(f"[DONE] Generated Amap injection script")
    print(f"       Output:  {os.path.abspath(output_path)} ({file_size} bytes)")
    print(f"       Items:   {len(items)}")
    print(f"       Delay:   {delay}s per item")
    print(f"       Default city fallback: {default_city_name} ({default_code})")
    print(f"       Est:     ~{est_minutes:.0f} minutes total")
    print()
    print("[NEXT STEPS]")
    print("  1. Open https://www.amap.com/ in your real Chrome and log in")
    print("  2. F12 → Console")
    print(f"  3. Paste ALL content of {output_path}")
    print("  4. Run: batchAddFavorites()")
    print("  5. If interrupted, re-run batchAddFavorites() to resume")
    print(f"  6. Wait ~{est_minutes:.0f} min until alert pops up")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate Amap batch-add JS script from GCJ-02 JSON."
    )
    parser.add_argument(
        "--input", "-i",
        default="baidu_favorites_gcj02.json",
        help="Input JSON from convert_coords.py (default: baidu_favorites_gcj02.json)",
    )
    parser.add_argument(
        "--output", "-o",
        default="amap_batch_add.js",
        help="Output JavaScript file (default: amap_batch_add.js)",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=2.5,
        help="Delay in seconds between requests (default: 2.5, increase if rate-limited)",
    )
    parser.add_argument(
        "--default-city",
        default="北京",
        help="Fallback city name when address has no known city (default: 北京)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"[ERROR] Input file not found: {args.input}")
        print("        Run convert_coords.py first to generate it.")
        sys.exit(1)

    generate_js(
        args.input,
        args.output,
        delay=args.delay,
        default_city=args.default_city,
    )
