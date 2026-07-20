#!/usr/bin/env python3
"""Smoke-test Bright Data SERP Google Reviews request variants."""
import argparse
import json
import os
from urllib.parse import quote

import requests


API_ENDPOINT = "https://api.brightdata.com/request"


def extract_count(value):
    if isinstance(value, dict):
        for key in ("reviews", "review_results"):
            items = value.get(key)
            if isinstance(items, list):
                return len(items), sorted(value.keys())
        body = value.get("body")
        if isinstance(body, str):
            try:
                return extract_count(json.loads(body))
            except ValueError:
                return 0, sorted(value.keys())
        return 0, sorted(value.keys())
    return 0, []


def request_variant(api_token, zone_name, label, url, fmt):
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        API_ENDPOINT,
        headers=headers,
        json={"zone": zone_name, "url": url, "format": fmt},
        timeout=30,
    )
    print(f"## {label}")
    print(f"status={response.status_code} content_type={response.headers.get('Content-Type')}")
    print(f"url={url}")
    preview = response.text[:500].replace("\n", "\\n")
    print(f"preview={preview}")
    try:
        parsed = response.json()
    except ValueError:
        print("json_parse=failed")
        return
    count, keys = extract_count(parsed)
    print(f"keys={keys}")
    print(f"review_count={count}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fid", required=True)
    parser.add_argument("--zone-name", default=os.getenv("BRIGHTDATA_ZONE_NAME") or "serp_api2")
    parser.add_argument("--api-token", default=os.getenv("BRIGHTDATA_API_TOKEN"))
    args = parser.parse_args()
    if not args.api_token:
        raise SystemExit("BRIGHTDATA_API_TOKEN is required")

    fids = [
        ("target", args.fid),
        ("official_sample", "0x89c259a9b3117469:0xd134e199a405a163"),
    ]
    for prefix, fid in fids:
        encoded = quote(fid, safe="")
        variants = [
            ("raw_brd_json_1", f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore&brd_json=1", "raw"),
            ("raw_brd_json_1_encoded", f"https://www.google.com/reviews?fid={encoded}&hl=ja&sort=qualityScore&brd_json=1", "raw"),
            ("json_brd_json_1", f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore&brd_json=1", "json"),
        ]
        for label, url, fmt in variants:
            request_variant(args.api_token, args.zone_name, f"{prefix}:{label}", url, fmt)


if __name__ == "__main__":
    main()
