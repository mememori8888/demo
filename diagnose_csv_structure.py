#!/usr/bin/env python3
"""
CSVファイルの構造を診断して、改行問題を検出
"""
import csv

backup_file = 'results/dental_new_reviews_all_regions.csv.backup'

print("=== CSV構造診断 ===\n")

# 方法1: csv.DictReaderで正しく読み込む（改行を考慮）
total_reviews = 0
with_gid = 0
without_gid = 0

with open(backup_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    print(f"列名: {fieldnames}")
    print(f"列数: {len(fieldnames)}\n")
    
    for row in reader:
        total_reviews += 1
        gid = row.get('レビューGID', '').strip() if row.get('レビューGID') else ''
        if gid:
            with_gid += 1
        else:
            without_gid += 1
            if without_gid <= 5:
                print(f"レビューGID が空の行 {total_reviews}:")
                print(f"  レビューID: {row.get('レビューID', '')[:50]}")
                print(f"  レビュー本文: {row.get('レビュー本文', '')[:100]}...")
                print(f"  全フィールド数: {len(row)}")
                print()

print(f"=== csv.DictReader での読み込み結果 ===")
print(f"総レビュー数: {total_reviews}")
print(f"レビューGID あり: {with_gid}")
print(f"レビューGID なし: {without_gid}")

# 方法2: 単純な行数カウント
with open(backup_file, 'r', encoding='utf-8') as f:
    line_count = sum(1 for line in f) - 1  # ヘッダー除く

print(f"\n=== ファイルの物理的な行数 ===")
print(f"総行数（ヘッダー除く）: {line_count}")
print(f"\n差分: {line_count - total_reviews} 行")
print(f"\n結論: レビュー本文に改行が含まれていて、")
print(f"      物理的な行数({line_count}行)と実際のレビュー数({total_reviews}レビュー)が異なります")
