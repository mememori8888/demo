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
    "関連度ランク",
    "関連度取得ソート",
    "関連度取得日時",
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


def has_facility_key(row):
    return bool((row.get("施設ID") or "").strip() or (row.get("施設GID") or "").strip())


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
    drop_empty_facility_rows = os.environ.get("DROP_EMPTY_FACILITY_ROWS", "false").lower() == "true"
    min_merged_rows = int(os.environ.get("MIN_MERGED_ROWS", "0") or "0")
    dropped_existing = 0
    dropped_incoming = 0

    merged = {}
    order = []
    for index, row in enumerate(read_rows(output), start=1):
        normalized = normalize_row(row)
        if drop_empty_facility_rows and not has_facility_key(normalized):
            dropped_existing += 1
            continue
        key = review_key(normalized, index)
        if key not in merged:
            order.append(key)
            merged[key] = normalized

    next_id = next_review_id(merged.values())
    new_keys = []
    for filename in sorted(glob.glob(batch_pattern, recursive=True)):
        for row in read_rows(filename):
            normalized = normalize_row(row)
            if drop_empty_facility_rows and not has_facility_key(normalized):
                dropped_incoming += 1
                continue
            key = review_key(normalized, len(order) + 1)
            if key in merged:
                merged[key] = merge_row(merged[key], normalized)
                continue
            normalized["レビューID"] = str(next_id)
            next_id += 1
            order.append(key)
            merged[key] = normalized
            new_keys.append(key)

    rows = [merged[key] for key in order]
    if min_merged_rows and len(rows) < min_merged_rows:
        raise RuntimeError(f"Merged rows {len(rows)} is below MIN_MERGED_ROWS={min_merged_rows}")
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    if drop_empty_facility_rows:
        print(f"Dropped rows without facility key: existing={dropped_existing}, incoming={dropped_incoming}")

    # 既存ファイルに無かった新規追加分のみ（増分）
    new_rows = [merged[key] for key in new_keys]
    return rows, new_rows


def write_increment_file(increment_file, new_rows):
    """今回のマージで新規追加された行のみを別ファイルに書き出す（増分出力）。"""
    increment = Path(increment_file)
    increment.parent.mkdir(parents=True, exist_ok=True)
    with increment.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(new_rows)


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
    rows, new_rows = merge_batches(output_file, batch_pattern)

    if os.environ.get("MERGE_TO_ALL_REGIONS", "false").lower() == "true":
        merge_to_all_regions(os.environ["ALL_REGIONS_FILE"], rows)

    increment_file = os.environ.get("INCREMENT_FILE", "").strip()
    if increment_file:
        write_increment_file(increment_file, new_rows)
        print(f"Incremental rows: {len(new_rows)} -> {increment_file}")

    print(f"Merged rows: {len(rows)}")


if __name__ == "__main__":
    main()
