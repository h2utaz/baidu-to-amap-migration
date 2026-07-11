#!/usr/bin/env python3
"""
Baidu → GCJ-02 Coordinate Converter
=====================================
Two-step conversion: BD-09 Mercator → BD-09 lng/lat → GCJ-02

Step 1: BD-09 Mercator → BD-09 lng/lat
  Uses Baidu Maps' internal MC2LL conversion matrix (6 latitude bands × 10 polynomial
  coefficients). This is the same algorithm used in the Baidu Maps JavaScript API.

Step 2: BD-09 → GCJ-02
  Standard public formula using X_PI = π × 3000 / 180.
  GCJ-02 is the coordinate system used by Amap (Gaode) and most Chinese map services.

Input format (from extract_baidu.py):
  JSON array of objects with "bd_lng" and "bd_lat" fields (BD-09 Mercator integers).

Output format:
  JSON array of objects with "gcj02_lng" and "gcj02_lat" fields (decimal degrees).

Usage:
    python3 convert_coords.py [--input baidu_favorites_raw.json] [--output baidu_favorites_gcj02.json]
"""

import json
import math
import os
import argparse


# ── BD-09 Mercator → BD-09 lng/lat ──────────────────────────────────────────
# These constants are from the Baidu Maps JavaScript API (BMap.Convertor).
# They convert Baidu's internal tile-based Mercator coordinates to decimal degrees.

MCBAND = [12890594.86, 8362377.87, 5591021, 3481989.83, 1678043.12, 0]

MC2LL = [
    [1.410526172116255e-8, 0.00000898305509648872, -1.9939833816331,
     200.9824383106796, -187.2403703815547, 91.6087516669843,
     -23.38765649603339, 2.57121317296198, -0.03801003308653, 17337981.2],
    [-7.435856389565537e-9, 0.000008983055097726239, -0.78625201886289,
     96.32687599759846, -1.85204757529826, -59.36935905485877,
     47.40033549296737, -16.50741931063887, 2.28786674699375, 10260144.86],
    [-3.030883460898826e-8, 0.00000898305509983578, 0.30071316287616,
     59.74293618442277, 7.357984074871, -25.38371002664745,
     13.45380521110908, -3.29883767235584, 0.32710905363475, 6856817.37],
    [-1.981981304930552e-8, 0.000008983055099779535, 0.03278182852591,
     40.31678527705744, 0.65659298677277, -4.44255534477492,
     0.85341911805263, 0.12923347998204, -0.04625736007561, 4482777.06],
    [3.09191371068437e-9, 0.000008983055096812155, 0.00006995724062,
     23.10934304144901, -0.00023663490511, -0.6321817810242,
     -0.00663494467273, 0.03430082397953, -0.00466043876332, 2555164.4],
    [2.890871144776878e-9, 0.000008983055095805407, -3.068298e-8,
     7.47137025468032, -0.00000353937994, -0.02145144861037,
     -0.00001234426596, 0.00010322952773, -0.00000323890364, 826088.5],
]

X_PI = math.pi * 3000.0 / 180.0  # BD-09 → GCJ-02 constant


def bd_mercator_to_lnglat(x, y):
    """
    Convert Baidu internal Mercator coordinates to BD-09 decimal degrees.

    Uses the MC2LL polynomial matrix with 6 latitude bands.
    Each band has 10 coefficients forming a 6th-degree polynomial.

    Args:
        x: Baidu Mercator X coordinate (from extdata.geoptx)
        y: Baidu Mercator Y coordinate (from extdata.geopty)

    Returns:
        (longitude, latitude) in BD-09 decimal degrees
    """
    x, y = float(x), float(y)

    # Determine latitude band
    band_idx = 0
    for i in range(len(MCBAND)):
        if y >= MCBAND[i]:
            band_idx = i
            break

    p = MC2LL[band_idx]

    # Longitude: simple linear term
    lng = p[0] + p[1] * abs(x)

    # Latitude: 6th-degree polynomial
    lat_norm = abs(y) / p[9]
    lat = (p[2] + p[3] * lat_norm + p[4] * lat_norm ** 2 +
           p[5] * lat_norm ** 3 + p[6] * lat_norm ** 4 +
           p[7] * lat_norm ** 5 + p[8] * lat_norm ** 6)

    return lng, lat


def bd09_to_gcj02(bd_lng, bd_lat):
    """
    Convert BD-09 coordinates to GCJ-02 (Mars Coordinates).

    GCJ-02 is used by Amap (Gaode), Tencent Maps, and most Chinese LBS services.
    This is a standard public algorithm.

    Args:
        bd_lng: BD-09 longitude (decimal degrees)
        bd_lat: BD-09 latitude (decimal degrees)

    Returns:
        (longitude, latitude) in GCJ-02 decimal degrees
    """
    x = bd_lng - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * X_PI)
    return z * math.cos(theta), z * math.sin(theta)


def convert_file(input_path, output_path):
    """Convert all coordinates in a JSON file and save results."""
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    converted = []
    for fav in data:
        try:
            bd_lng, bd_lat = bd_mercator_to_lnglat(fav["bd_lng"], fav["bd_lat"])
            gcj_lng, gcj_lat = bd09_to_gcj02(bd_lng, bd_lat)
            converted.append({
                "name": fav.get("name", ""),
                "address": fav.get("address", ""),
                "gcj02_lng": round(gcj_lng, 6),
                "gcj02_lat": round(gcj_lat, 6),
                "tags": fav.get("tags", []),
            })
        except Exception as e:
            print(f"[WARN] Skipping {fav.get('name', 'unknown')}: {e}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(converted, f, ensure_ascii=False, indent=2)

    print(f"[DONE] Converted {len(converted)}/{len(data)} locations")
    print(f"       Input:  {os.path.abspath(input_path)}")
    print(f"       Output: {os.path.abspath(output_path)}")

    # Show samples
    print("\n[SAMPLES]")
    for fav in converted[:5]:
        print(f"  {fav['name']}")
        print(f"    GCJ-02: ({fav['gcj02_lng']}, {fav['gcj02_lat']})")

    return converted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert BD-09 Mercator coordinates to GCJ-02 for Amap."
    )
    parser.add_argument(
        "--input", "-i",
        default="baidu_favorites_raw.json",
        help="Input JSON from extract_baidu.py (default: baidu_favorites_raw.json)",
    )
    parser.add_argument(
        "--output", "-o",
        default="baidu_favorites_gcj02.json",
        help="Output JSON with GCJ-02 coordinates (default: baidu_favorites_gcj02.json)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"[ERROR] Input file not found: {args.input}")
        print("        Run extract_baidu.py first to generate it.")
        sys.exit(1)

    convert_file(args.input, args.output)
