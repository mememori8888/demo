#!/usr/bin/env python3
"""Fill review relevance rank columns by matching SERP API reviews to review GIDs."""
import argparse
import csv
import datetime as dt
import glob
import html
import json
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote

import requests


FIELDNAMES = [
    "レビューID",
    "施設ID",
    "施設GID",
    "レビュワー評価",
    "レビュワー名",
    "レビュー日時",
    "レビュー本文",
    "オーナー返信",
    "レビュー表示順位",
    "レビュー取得ソート",
    "関連度ランク",
    "関連度取得ソート",
    "関連度取得日時",
    "レビュー要約",
    "レビューGID",
]

API_ENDPOINT = "https://api.brightdata.com/request"
REVIEWS_PER_PAGE = 10
RELEVANCE_SORT = "qualityScore"


def read_rows(path):
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return []
    for encoding in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"CSVを読み込めませんでした: {path}")


def write_rows(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: (row.get(column) or "").strip() for column in FIELDNAMES})


def detect_fid(row):
    for column in ("施設FID", "FID", "fid", "Facility FID", "facility_fid"):
        value = (row.get(column) or "").strip()
        if re.match(r"^0x[0-9a-f]+:0x[0-9a-f]+$", value, re.IGNORECASE):
            return value

    url = html.unescape((row.get("GoogleMap") or row.get("googlemap") or "").strip())
    if not url:
        return ""
    decoded = unquote(url)
    match = re.search(r"!1s([^!/?&]+)", decoded)
    if match:
        return match.group(1)
    match = re.search(r"(0x[0-9a-f]+:0x[0-9a-f]+)", decoded, re.IGNORECASE)
    return match.group(1) if match else ""


def load_facilities(path):
    facilities = {}
    for row in read_rows(path):
        facility_id = (row.get("施設ID") or row.get("post_id") or row.get("ID") or "").strip()
        facility_gid = (row.get("施設GID") or row.get("GID") or row.get("gid") or "").strip()
        fid = detect_fid(row)
        if not fid:
            continue
        for key in (facility_gid, facility_id):
            if key and key not in facilities:
                facilities[key] = {
                    "facility_id": facility_id,
                    "facility_gid": facility_gid,
                    "facility_name": (row.get("施設名") or "").strip(),
                    "fid": fid,
                }
    return facilities


def load_recent_review_facilities(patterns):
    facility_keys = set()
    review_gids = set()
    files = []
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        files.extend(matches if matches else [pattern])

    for filename in files:
        for row in read_rows(filename):
            facility_gid = (row.get("施設GID") or "").strip()
            facility_id = (row.get("施設ID") or "").strip()
            review_gid = (row.get("レビューGID") or "").strip()
            if facility_gid:
                facility_keys.add(facility_gid)
            elif facility_id:
                facility_keys.add(facility_id)
            if review_gid:
                review_gids.add(review_gid)
    return facility_keys, review_gids, files


def parse_response_body(response_json):
    if isinstance(response_json, dict) and "body" in response_json:
        body = response_json.get("body")
    else:
        body = response_json
    if isinstance(body, str):
        if body.startswith(")]}',"):
            body = body[5:]
        try:
            return json.loads(body)
        except ValueError as exc:
            raise RuntimeError(
                f"SERP APIレスポンスのbodyがJSONとして解析できません "
                f"(body先頭300文字='{body[:300]}'): {exc}"
            ) from exc
    return body


def extract_reviews(response_data):
    if isinstance(response_data, dict):
        reviews = response_data.get("reviews") or response_data.get("review_results") or []
        return reviews if isinstance(reviews, list) else []
    return []


def review_gid(review):
    for key in ("review_id", "reviewId", "reviewid", "id"):
        value = review.get(key) if isinstance(review, dict) else ""
        if value:
            return str(value).strip()
    return ""


def fetch_relevance_reviews(api_token, zone_name, fid, rank_limit, timeout):
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    reviews = []
    pages = max(1, math.ceil(rank_limit / REVIEWS_PER_PAGE))

    for page in range(pages):
        start = page * REVIEWS_PER_PAGE
        url = f"https://www.google.com/reviews?fid={fid}&start={start}&sort={RELEVANCE_SORT}&hl=ja"
        payload = {"zone": zone_name, "url": url, "format": "raw"}
        response = requests.post(API_ENDPOINT, headers=headers, json=payload, timeout=timeout)
        if response.status_code != 200:
            raise RuntimeError(
                f"SERP API HTTP {response.status_code} (zone={zone_name}): {response.text[:300]}"
            )
        try:
            response_json = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"SERP APIのレスポンスがJSONではありません (zone={zone_name}, "
                f"content-type={response.headers.get('Content-Type')}, "
                f"body先頭300文字='{response.text[:300]}'): {exc}"
            ) from exc
        parsed = parse_response_body(response_json)
        page_reviews = extract_reviews(parsed)
        if not page_reviews:
            if page == 0:
                outer_keys = sorted(response_json.keys()) if isinstance(response_json, dict) else None
                outer_meta = {
                    k: response_json.get(k)
                    for k in ("status_code", "status", "url", "warning", "error", "headers")
                    if isinstance(response_json, dict) and k in response_json
                }
                if isinstance(parsed, dict):
                    diag = f"keys={sorted(parsed.keys())}"
                else:
                    diag = f"type={type(parsed).__name__} value={str(parsed)[:200]}"
                print(
                    f"WARN fid={fid}: SERP APIレスポンスからレビューを抽出できませんでした "
                    f"(body {diag}, response全体のキー={outer_keys}, "
                    f"メタ情報={outer_meta}, raw先頭500文字='{response.text[:500]}')"
                )
            break
        reviews.extend(page_reviews)
        if len(page_reviews) < REVIEWS_PER_PAGE:
            break
        time.sleep(0.1)

    return reviews[:rank_limit]


def fetch_facility_rank_map(api_token, zone_name, facility, rank_limit, timeout):
    top_reviews = fetch_relevance_reviews(api_token, zone_name, facility["fid"], rank_limit, timeout)
    ranks = {}
    for index, review in enumerate(top_reviews, start=1):
        gid = review_gid(review)
        if gid and gid not in ranks:
            ranks[gid] = index
    return {
        "facility": facility,
        "ranks": ranks,
        "request_count": max(1, math.ceil(rank_limit / REVIEWS_PER_PAGE)),
        "top_count": len(top_reviews),
    }


def row_matches_facility(row, facility):
    row_facility_id = (row.get("施設ID") or "").strip()
    row_facility_gid = (row.get("施設GID") or "").strip()
    facility_id = (facility.get("facility_id") or "").strip()
    facility_gid = (facility.get("facility_gid") or "").strip()
    return bool(
        (facility_gid and row_facility_gid == facility_gid)
        or (facility_id and row_facility_id == facility_id)
    )


def enrich_review_file(review_file, facilities, target_facility_keys, rank_maps, fetched_at):
    rows = read_rows(review_file)
    for row in rows:
        for column in FIELDNAMES:
            row.setdefault(column, "")

    targeted_gid_or_id = set()
    for facility in facilities:
        if facility.get("facility_gid"):
            targeted_gid_or_id.add(facility["facility_gid"])
        if facility.get("facility_id"):
            targeted_gid_or_id.add(facility["facility_id"])

    for row in rows:
        facility_key = (row.get("施設GID") or row.get("施設ID") or "").strip()
        if facility_key in targeted_gid_or_id or facility_key in target_facility_keys:
            row["関連度ランク"] = ""
            row["関連度取得ソート"] = ""
            row["関連度取得日時"] = ""

    matched = 0
    ranks_by_facility = []
    for result in rank_maps:
        ranks_by_facility.append((result["facility"], result["ranks"]))

    for row in rows:
        gid = (row.get("レビューGID") or "").strip()
        if not gid:
            continue
        for facility, ranks in ranks_by_facility:
            if gid in ranks and row_matches_facility(row, facility):
                row["関連度ランク"] = str(ranks[gid])
                row["関連度取得ソート"] = RELEVANCE_SORT
                row["関連度取得日時"] = fetched_at
                matched += 1
                break

    write_rows(review_file, rows)
    return matched, len(rows)


def write_summary(path, rank_maps, recent_review_gids, matched, total_rows, failed):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "施設ID",
                "施設GID",
                "施設名",
                "施設FID",
                "SERP取得件数",
                "SERPリクエスト数",
                "期間内レビュー上位10一致数",
                "エラー",
            ],
        )
        writer.writeheader()
        for result in rank_maps:
            facility = result["facility"]
            recent_matches = sum(1 for gid in result["ranks"] if gid in recent_review_gids)
            writer.writerow({
                "施設ID": facility.get("facility_id", ""),
                "施設GID": facility.get("facility_gid", ""),
                "施設名": facility.get("facility_name", ""),
                "施設FID": facility.get("fid", ""),
                "SERP取得件数": result.get("top_count", 0),
                "SERPリクエスト数": result.get("request_count", 0),
                "期間内レビュー上位10一致数": recent_matches,
                "エラー": "",
            })
        for item in failed:
            facility = item["facility"]
            writer.writerow({
                "施設ID": facility.get("facility_id", ""),
                "施設GID": facility.get("facility_gid", ""),
                "施設名": facility.get("facility_name", ""),
                "施設FID": facility.get("fid", ""),
                "SERP取得件数": 0,
                "SERPリクエスト数": 0,
                "期間内レビュー上位10一致数": 0,
                "エラー": item["error"],
            })
    print(f"Summary: {path}")
    print(f"Review rows: {total_rows}, matched relevance ranks: {matched}, failed facilities: {len(failed)}")


def main():
    parser = argparse.ArgumentParser(description="SERP APIで関連度上位レビューを取得し、レビューCSVに関連度ランクを付与します。")
    parser.add_argument("--review-file", required=True)
    parser.add_argument("--facility-file", required=True)
    parser.add_argument("--recent-review-glob", action="append", required=True)
    parser.add_argument("--summary-file", default="results/relevance_rank_summary.csv")
    parser.add_argument("--rank-limit", type=int, default=10)
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--api-token", default=os.getenv("BRIGHTDATA_API_TOKEN"))
    parser.add_argument("--zone-name", default=os.getenv("BRIGHTDATA_ZONE_NAME") or os.getenv("ZONE_NAME") or "serp_api2")
    args = parser.parse_args()

    if not args.api_token:
        raise SystemExit("BRIGHTDATA_API_TOKEN が設定されていません。")
    if args.rank_limit < 1:
        raise SystemExit("--rank-limit は1以上を指定してください。")
    if args.max_workers < 1:
        raise SystemExit("--max-workers は1以上を指定してください。")

    target_keys, recent_review_gids, recent_files = load_recent_review_facilities(args.recent_review_glob)
    if not target_keys:
        print("期間内レビューがないため、SERP APIの関連度取得はスキップします。")
        return

    facility_lookup = load_facilities(args.facility_file)
    target_facilities = []
    seen_fids = set()
    for key in sorted(target_keys):
        facility = facility_lookup.get(key)
        if not facility or not facility.get("fid") or facility["fid"] in seen_fids:
            continue
        seen_fids.add(facility["fid"])
        target_facilities.append(facility)

    if not target_facilities:
        raise SystemExit("期間内レビューのある施設に対応するFIDが見つかりませんでした。")

    print(f"Recent review files: {len(recent_files)}")
    print(f"Facilities with recent reviews: {len(target_keys)}")
    print(f"Facilities to query by SERP API: {len(target_facilities)}")
    print(f"Rank limit: {args.rank_limit}, sort: {RELEVANCE_SORT}")

    rank_maps = []
    failed = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(
                fetch_facility_rank_map,
                args.api_token,
                args.zone_name,
                facility,
                args.rank_limit,
                args.timeout,
            ): facility
            for facility in target_facilities
        }
        for future in as_completed(futures):
            facility = futures[future]
            try:
                result = future.result()
                rank_maps.append(result)
                print(f"OK {facility.get('facility_id')} {facility.get('facility_name')} top={result['top_count']}")
            except Exception as exc:
                failed.append({"facility": facility, "error": str(exc)})
                print(f"NG {facility.get('facility_id')} {facility.get('facility_name')}: {exc}")

    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    matched, total_rows = enrich_review_file(
        args.review_file,
        target_facilities,
        target_keys,
        rank_maps,
        fetched_at,
    )
    write_summary(args.summary_file, rank_maps, recent_review_gids, matched, total_rows, failed)

    if failed:
        raise SystemExit(f"SERP API関連度取得に失敗した施設があります: {len(failed)}件")


if __name__ == "__main__":
    main()
