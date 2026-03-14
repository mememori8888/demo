#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSVファイルの行数を素早くカウント
"""
import sys

file_path = "results/dental_new.csv"

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        line_count = sum(1 for _ in f)
    
    data_lines = line_count - 1  # ヘッダーを除く
    
    print(f"総行数（ヘッダー含む）: {line_count:,} 行")
    print(f"データ行数（ヘッダー除く）: {data_lines:,} 行")
    
except FileNotFoundError:
    print(f"❌ ファイルが見つかりません: {file_path}", file=sys.stderr)
    sys.exit(1)
