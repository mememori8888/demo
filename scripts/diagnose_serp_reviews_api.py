#!/usr/bin/env python3
"""Smoke-test Bright Data SERP Google Reviews request variants."""
import argparse
import json
import os
from urllib.parse import quote

import requests


API_ENDPOINT = "https://api.brightdata.com/request"


def find_review_lists(value):
    review_lists = []
    if isinstance(value, dict):
        for key in ("reviews", "review_results", "user_reviews"):
            items = value.get(key)
            if isinstance(items, list):
                review_lists.append(items)
        body = value.get("body")
        if isinstance(body, str):
            try:
                review_lists.extend(find_review_lists(json.loads(body)))
            except ValueError:
                pass
        for item in value.values():
            if item is body:
                continue
            review_lists.extend(find_review_lists(item))
    elif isinstance(value, list):
        for item in value:
            review_lists.extend(find_review_lists(item))
    return review_lists


def extract_count(value):
    review_lists = find_review_lists(value)
    count = len(review_lists[0]) if review_lists else 0
    keys = sorted(value.keys()) if isinstance(value, dict) else []
    return count, keys


def request_variant(
    api_token,
    zone_name,
    label,
    url,
    fmt,
    data_format=None,
    method=None,
    direct=None,
    extra_headers=None,
):
    print(f"## {label}", flush=True)
    print(f"url={url}", flush=True)
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    try:
        payload = {"zone": zone_name, "url": url, "format": fmt}
        if data_format:
            payload["data_format"] = data_format
        if method:
            payload["method"] = method
        if direct is not None:
            payload["direct"] = direct
        response = requests.post(
            API_ENDPOINT,
            headers=headers,
            json=payload,
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
    request_variant(
        args.api_token,
        args.zone_name,
        "official_search_sample_json_parsed",
        "https://www.google.com/search?q=pizza",
        "json",
        "parsed",
    )
    for prefix, fid in fids:
        encoded = quote(fid, safe="")
        variants = [
            ("official_reviews_sample_raw_direct_literal", "https://www.google.com/reviews?fid=pizza&", "raw", None, "GET", True),
            ("json_no_brd", f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore", "json"),
            ("json_parsed_no_brd", f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore", "json", "parsed"),
            ("raw_direct_no_brd", f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore", "raw", None, "GET", True),
            ("json_no_brd_encoded", f"https://www.google.com/reviews?fid={encoded}&hl=ja&sort=qualityScore", "json"),
            ("raw_brd_json_1", f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore&brd_json=1", "raw"),
            ("raw_direct_brd_json_1", f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore&brd_json=1", "raw", None, "GET", True),
            ("raw_brd_json_1_encoded", f"https://www.google.com/reviews?fid={encoded}&hl=ja&sort=qualityScore&brd_json=1", "raw"),
            ("json_brd_json_1", f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore&brd_json=1", "json"),
            ("json_parsed_brd_json_1", f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore&brd_json=1", "json", "parsed"),
            ("maps_place_data_raw_brd_json_1", f"https://www.google.com/maps/place/data=!3m1!4b1!4m2!3m1!1s{fid}?brd_json=1", "raw"),
            ("maps_place_data_json_brd_json_1", f"https://www.google.com/maps/place/data=!3m1!4b1!4m2!3m1!1s{fid}?brd_json=1", "json"),
            ("maps_place_data_json_parsed_brd_json_1", f"https://www.google.com/maps/place/data=!3m1!4b1!4m2!3m1!1s{fid}?brd_json=1", "json", "parsed"),
        ]
        for variant in variants:
            label, url, fmt = variant[:3]
            data_format = variant[3] if len(variant) > 3 else None
            method = variant[4] if len(variant) > 4 else None
            direct = variant[5] if len(variant) > 5 else None
            request_variant(
                args.api_token,
                args.zone_name,
                f"{prefix}:{label}",
                url,
                fmt,
                data_format,
                method,
                direct,
            )
        request_variant(
            args.api_token,
            args.zone_name,
            f"{prefix}:raw_header_json",
            f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore",
            "raw",
            extra_headers={"x-unblock-data-format": "json"},
        )
        request_variant(
            args.api_token,
            args.zone_name,
            f"{prefix}:json_header_json",
            f"https://www.google.com/reviews?fid={fid}&hl=ja&sort=qualityScore",
            "json",
            extra_headers={"x-unblock-data-format": "json"},
        )

    if args.maps_url:
        maps_url = args.maps_url
        separator = "&" if "?" in maps_url else "?"
        variants = [
            ("maps_url_raw", maps_url, "raw"),
            ("maps_url_raw_brd_json_1", f"{maps_url}{separator}brd_json=1", "raw"),
            ("maps_url_json_brd_json_1", f"{maps_url}{separator}brd_json=1", "json"),
            ("maps_url_json_parsed_brd_json_1", f"{maps_url}{separator}brd_json=1", "json", "parsed"),
        ]
        for variant in variants:
            label, url, fmt = variant[:3]
            data_format = variant[3] if len(variant) > 3 else None
            request_variant(args.api_token, args.zone_name, label, url, fmt, data_format)


if __name__ == "__main__":
    main()
