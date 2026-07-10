#!/usr/bin/env python3
"""Merge review batch CSVs into an existing review CSV without dropping rows."""
import csv
import glob
import os
from pathlib import Path


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
    "レビュー要約",
    "レビューGID",
]


def read_rows(path):
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [row for row in reader if any((v or "").strip() for v in row.values())]


def normalize_row(row):
    return {column: (row.get(column) or "").strip() for column in FIELDNAMES}


def review_key(row, fallback_index):
    gid = (row.get("レビューGID") or "").strip()
    if gid:
        return f"gid:{gid}"
    review_id = (row.get("レビューID") or "").strip()
    if review_id:
        return f"id:{review_id}"
    return f"row:{fallback_index}"


def merge_row(existing, incoming):
    merged = dict(existing)
    for column, value in incoming.items():
        value = (value or "").strip()
        if not value:
            continue
        if column in ("レビューID", "レビュー要約") and (merged.get(column) or "").strip():
            continue
        merged[column] = value
    return merged


def next_review_id(rows):
    max_id = 100
    for row in rows:
        try:
            max_id = max(max_id, int((row.get("レビューID") or "").strip() or "0"))
        except ValueError:
            pass
    return max_id + 1


def merge_batches(output_file, batch_pattern):
    output = Path(output_file)
    output.parent.mkdir(parents=True, exist_ok=True)

    merged = {}
    order = []
    for index, row in enumerate(read_rows(output), start=1):
        normalized = normalize_row(row)
        key = review_key(normalized, index)
        if key not in merged:
            order.append(key)
            merged[key] = normalized

    next_id = next_review_id(merged.values())
    for filename in sorted(glob.glob(batch_pattern, recursive=True)):
        for row in read_rows(filename):
            normalized = normalize_row(row)
            key = review_key(normalized, len(order) + 1)
            if key in merged:
                merged[key] = merge_row(merged[key], normalized)
                continue
            normalized["レビューID"] = str(next_id)
            next_id += 1
            order.append(key)
            merged[key] = normalized

    rows = [merged[key] for key in order]
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def merge_to_all_regions(all_regions_file, rows):
    all_regions = Path(all_regions_file)
    existing = {}
    order = []
    for index, row in enumerate(read_rows(all_regions), start=1):
        normalized = normalize_row(row)
        key = review_key(normalized, index)
        if key not in existing:
            order.append(key)
            existing[key] = normalized

    for row in rows:
        key = review_key(row, len(order) + 1)
        if key in existing:
            existing[key] = merge_row(existing[key], row)
        else:
            order.append(key)
            existing[key] = row

    all_regions.parent.mkdir(parents=True, exist_ok=True)
    with all_regions.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(existing[key] for key in order)


def main():
    output_file = os.environ["OUTPUT_FILE"]
    batch_pattern = os.environ["BATCH_PATTERN"]
    rows = merge_batches(output_file, batch_pattern)

    if os.environ.get("MERGE_TO_ALL_REGIONS", "false").lower() == "true":
        merge_to_all_regions(os.environ["ALL_REGIONS_FILE"], rows)

    print(f"Merged rows: {len(rows)}")


if __name__ == "__main__":
    main()
