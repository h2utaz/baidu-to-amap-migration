#!/usr/bin/env python3
"""
Baidu Maps Favorites Extractor
================================
Extracts all favorites/collections from Baidu Maps web by intercepting
the internal favdata API responses using Playwright.

This script launches an independent Chromium instance with a temporary
profile — it does NOT touch or modify the user's real Chrome configuration.

Prerequisites:
    pip install playwright
    playwright install chromium

Usage:
    python3 extract_baidu.py [--output baidu_favorites_raw.json]

What it extracts per favorite:
    - name:         Location name (from extdata.name)
    - address:      Street address (from extdata.content)
    - bd_lng:       BD-09 Mercator X coordinate (integer, divide by 100k for approx lng)
    - bd_lat:       BD-09 Mercator Y coordinate (integer, divide by 100k for approx lat)
    - tags:         Category tags (e.g., ['吃', '美食', '北京市'])
"""

import json
import os
import sys
import time
import tempfile
import argparse
from playwright.sync_api import sync_playwright


def extract_favorites(output_path="baidu_favorites_raw.json", headless=False):
    """
    Launch Playwright, intercept Baidu Maps favdata API, extract favorites.

    Args:
        output_path: Path to save the extracted JSON.
        headless: If True, run browser in headless mode (less reliable for login).
    """
    temp_profile = tempfile.mkdtemp(prefix="baidu_extract_")
    print(f"[INFO] Temporary profile: {temp_profile}")
    print("[INFO] This profile will be deleted after extraction. No impact on your Chrome.")

    p = sync_playwright().start()

    try:
        context = p.chromium.launch_persistent_context(
            temp_profile,
            headless=headless,
            viewport={"width": 1280, "height": 900},
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-sync",
                "--disable-extensions",
            ],
        )

        page = context.pages[0] if context.pages else context.new_page()

        # Collect all favdata API response bodies
        favdata_responses = []

        def on_response(response):
            if "favdata" in response.url and response.status == 200:
                try:
                    body = response.body()
                    favdata_responses.append(body)
                    print(f"[API] Captured favdata response: {len(body)} bytes")
                except Exception:
                    pass

        page.on("response", on_response)

        # Navigate to favorites page
        print("\n[STEP 1] Opening Baidu Maps favorites page...")
        page.goto("https://map.baidu.com/fav/", timeout=60000, wait_until="domcontentloaded")
        time.sleep(3)

        # Wait for user login
        print("[STEP 2] Waiting for login...")
        if not headless:
            print("         A Chromium window opened. Please log in to Baidu Maps there.")
            print("         Script will auto-detect login and continue.")

        for i in range(120):
            url = page.url
            if "fav" in url and "login" not in url.lower() and "passport" not in url.lower():
                print(f"[INFO] Login detected. Proceeding...")
                break
            time.sleep(1)

        # Refresh to trigger favdata API calls with fresh auth
        print("\n[STEP 3] Refreshing to trigger API calls...")
        page.goto("https://map.baidu.com/fav/", timeout=30000, wait_until="networkidle")
        time.sleep(10)

        print(f"\n[INFO] Captured {len(favdata_responses)} favdata API responses")

        # Parse all responses
        all_favorites = []
        for blob in favdata_responses:
            try:
                data = json.loads(blob)
                items = data.get("sync", {}).get("newdata", [])
                for item in items:
                    if item.get("action") == "del":
                        continue
                    d = item.get("detail", {}).get("data")
                    if not d or d is False:
                        continue
                    if d.get("type") != "10":
                        continue

                    extdata = d.get("extdata", {})
                    sourcedata = d.get("sourcedata", {})

                    fav = {
                        "name": extdata.get("name", sourcedata.get("name", "")),
                        "address": extdata.get("content", sourcedata.get("addr", "")),
                        "bd_lng": str(extdata.get("geoptx", 0)),
                        "bd_lat": str(extdata.get("geopty", 0)),
                        "tags": [t.get("name", "") for t in d.get("tags", [])],
                    }
                    all_favorites.append(fav)
            except Exception as e:
                print(f"[WARN] Parse error: {e}")

        # Save output
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_favorites, f, ensure_ascii=False, indent=2)

        file_size = os.path.getsize(output_path)
        print(f"\n[DONE] Extracted {len(all_favorites)} favorites")
        print(f"       Saved to: {os.path.abspath(output_path)} ({file_size} bytes)")

        # Show samples
        for fav in all_favorites[:5]:
            print(f"       - {fav['name']} (lng={fav['bd_lng']}, lat={fav['bd_lat']})")

        return output_path

    finally:
        context.close()
        p.stop()
        # Clean up temp profile
        import shutil
        shutil.rmtree(temp_profile, ignore_errors=True)
        print(f"[INFO] Temporary profile deleted: {temp_profile}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract favorites from Baidu Maps web."
    )
    parser.add_argument(
        "--output", "-o",
        default="baidu_favorites_raw.json",
        help="Output JSON file path (default: baidu_favorites_raw.json)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (may fail if login is required)",
    )
    args = parser.parse_args()

    extract_favorites(output_path=args.output, headless=args.headless)
