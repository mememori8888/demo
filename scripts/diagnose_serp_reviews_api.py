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


def request_variant(api_token, zone_name, label, url, fmt, extra_headers=None):
    print(f"## {label}", flush=True)
    print(f"url={url}", flush=True)
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    try:
        response = requests.post(
            API_ENDPOINT,
            headers=headers,
            json={"zone": zone_name, "url": url, "format": fmt},
            timeout=60,
        )
    except Exception as exc:
        print(f"request_error={type(exc).__name__}: {exc}", flush=True)
        return
    print(f"status={response.status_code} content_type={response.headers.get('Content-Type')}")
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
    parser.add_argument("--maps-url", default="")
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
            ("json_no_brd", f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore", "json"),
            ("json_no_brd_encoded", f"https://www.google.com/reviews?fid={encoded}&hl=ja&sort=qualityScore", "json"),
            ("raw_brd_json_1", f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore&brd_json=1", "raw"),
            ("raw_brd_json_1_encoded", f"https://www.google.com/reviews?fid={encoded}&hl=ja&sort=qualityScore&brd_json=1", "raw"),
            ("json_brd_json_1", f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore&brd_json=1", "json"),
        ]
        for label, url, fmt in variants:
            request_variant(args.api_token, args.zone_name, f"{prefix}:{label}", url, fmt)
        request_variant(
            args.api_token,
            args.zone_name,
            f"{prefix}:raw_header_json",
            f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore",
            "raw",
            {"x-unblock-data-format": "json"},
        )
        request_variant(
            args.api_token,
            args.zone_name,
            f"{prefix}:json_header_json",
            f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore",
            "json",
            {"x-unblock-data-format": "json"},
        )

    if args.maps_url:
        maps_url = args.maps_url
        separator = "&" if "?" in maps_url else "?"
        variants = [
            ("maps_url_raw", maps_url, "raw"),
            ("maps_url_raw_brd_json_1", f"{maps_url}{separator}brd_json=1", "raw"),
            ("maps_url_json_brd_json_1", f"{maps_url}{separator}brd_json=1", "json"),
        ]
        for label, url, fmt in variants:
            request_variant(args.api_token, args.zone_name, label, url, fmt)


if __name__ == "__main__":
    main()
