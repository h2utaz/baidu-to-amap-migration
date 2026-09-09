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
import shutil
import sys
import tempfile
import argparse
from playwright.sync_api import sync_playwright


def _favorite_key(fav):
    """Stable key for deduplicating the same favorite across multiple API responses."""
    return (fav["name"], fav["address"], fav["bd_lng"], fav["bd_lat"])


def _parse_favorites(favdata_responses):
    """Parse favdata response bodies into a deduplicated favorite list."""
    all_favorites = []
    seen = set()
    skipped_types = {}

    for blob in favdata_responses:
        try:
            data = json.loads(blob)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"[WARN] Parse error: {e}")
            continue

        items = data.get("sync", {}).get("newdata", [])
        for item in items:
            if item.get("action") == "del":
                continue
            d = item.get("detail", {}).get("data")
            if not d or d is False:
                continue

            item_type = d.get("type")
            if item_type != "10":
                skipped_types[str(item_type)] = skipped_types.get(str(item_type), 0) + 1
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
            key = _favorite_key(fav)
            if key in seen:
                continue
            seen.add(key)
            all_favorites.append(fav)

    if skipped_types:
        summary = ", ".join(f"type={t}:{n}" for t, n in sorted(skipped_types.items()))
        print(f"[INFO] Skipped non-POI items: {summary}")

    return all_favorites


def _looks_logged_in(page):
    """
    Require both a non-login favorites URL and an auth cookie.
    URL-only checks false-positive on the unauthenticated /fav/ page.
    """
    url = page.url.lower()
    if "fav" not in url or "login" in url or "passport" in url:
        return False
    cookies = page.context.cookies()
    auth_names = {"BDUSS", "STOKEN", "BAIDUID"}
    return any(c.get("name") in auth_names for c in cookies)


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

    context = None
    playwright = None

    try:
        playwright = sync_playwright().start()
        context = playwright.chromium.launch_persistent_context(
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
            if "favdata" not in response.url or response.status != 200:
                return
            try:
                body = response.body()
            except Exception as e:
                print(f"[WARN] Failed to read favdata body: {e}")
                return
            favdata_responses.append(body)
            print(f"[API] Captured favdata response: {len(body)} bytes")

        page.on("response", on_response)

        # Navigate to favorites page
        print("\n[STEP 1] Opening Baidu Maps favorites page...")
        page.goto("https://map.baidu.com/fav/", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Wait for user login
        print("[STEP 2] Waiting for login...")
        if not headless:
            print("         A Chromium window opened. Please log in to Baidu Maps there.")
            print("         Script will auto-detect login (URL + auth cookie) and continue.")

        logged_in = False
        for _ in range(120):
            if _looks_logged_in(page):
                print("[INFO] Login detected (favorites URL + auth cookie). Proceeding...")
                logged_in = True
                break
            page.wait_for_timeout(1000)

        if not logged_in:
            print("[ERROR] Login not detected within 120s.")
            print("        Confirm you completed login in the Chromium window, then re-run.")
            sys.exit(1)

        # Refresh to trigger favdata API calls with fresh auth
        print("\n[STEP 3] Refreshing to trigger API calls...")
        page.goto("https://map.baidu.com/fav/", timeout=30000, wait_until="networkidle")
        try:
            page.wait_for_response(
                lambda r: "favdata" in r.url and r.status == 200,
                timeout=30000,
            )
        except Exception:
            print("[WARN] No favdata response within 30s; waiting a bit longer...")
            page.wait_for_timeout(10000)

        print(f"\n[INFO] Captured {len(favdata_responses)} favdata API responses")

        all_favorites = _parse_favorites(favdata_responses)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_favorites, f, ensure_ascii=False, indent=2)

        file_size = os.path.getsize(output_path)
        print(f"\n[DONE] Extracted {len(all_favorites)} favorites (deduplicated)")
        print(f"       Saved to: {os.path.abspath(output_path)} ({file_size} bytes)")

        for fav in all_favorites[:5]:
            print(f"       - {fav['name']} (lng={fav['bd_lng']}, lat={fav['bd_lat']})")

        if not all_favorites:
            print("[WARN] 0 favorites extracted. Re-check login and try again.")
            sys.exit(2)

        return output_path

    finally:
        if context is not None:
            try:
                context.close()
            except Exception as e:
                print(f"[WARN] Failed to close browser context: {e}")
        if playwright is not None:
            try:
                playwright.stop()
            except Exception as e:
                print(f"[WARN] Failed to stop Playwright: {e}")
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
