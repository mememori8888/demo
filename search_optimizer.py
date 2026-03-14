#!/usr/bin/env python3
"""
Search Optimizer & Heatmap Generator

このスクリプトは2つの主要な機能を提供します：
1. 検索最適化: 既存の施設データを分析し、エリアごとの最適なリクエスト回数を計算します。
2. ヒートマップ生成: 施設データからヒートマップ表示用のデータを生成します。

Usage:
    python search_optimizer.py --facility-file results/dental.csv --address-file settings/address.csv --output results/optimized_search.csv
    python search_optimizer.py --heatmap-only --facility-file results/dental.csv
"""

import argparse
import csv
import os
import logging
import pandas as pd
import json
from collections import defaultdict

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_facility_data(facility_file):
    """施設データを読み込み、エリアごとの件数を集計する"""
    if not os.path.exists(facility_file):
        logging.error(f"施設ファイルが見つかりません: {facility_file}")
        return None, None

    logging.info(f"施設データを読み込んでいます: {facility_file}")
    
    try:
        df = pd.read_csv(facility_file)
        logging.info(f"読み込み完了: {len(df)} 件")
        return df
    except Exception as e:
        logging.error(f"ファイル読み込みエラー: {e}")
        return None

def generate_heatmap_data(df, output_file=None):
    """
    ヒートマップ用のデータを生成する
    - 緯度経度があるデータを抽出
    - エリアごとの集計
    """
    logging.info("ヒートマップデータを生成中...")
    
    # 緯度経度があるデータのみ抽出
    if '緯度' in df.columns and '経度' in df.columns:
        valid_coords = df.dropna(subset=['緯度', '経度'])
        logging.info(f"有効な座標データ: {len(valid_coords)} / {len(df)} 件")
        
        # ヒートマップ用CSVを出力（緯度、経度、重み付け用スコアなど）
        if output_file:
            heatmap_csv = output_file
        else:
            # 入力ファイル名_heatmap.csv
            base_name = "heatmap_data"
            heatmap_csv = f"results/{base_name}.csv"
            
        # 必要なカラムのみ抽出
        cols = ['施設名', '緯度', '経度', '住所']
        if 'ランク' in df.columns:
            cols.append('ランク')
        if 'レビュー数' in df.columns:
            cols.append('レビュー数')
            
        # 存在するカラムのみ
        out_cols = [c for c in cols if c in valid_coords.columns]
        
        valid_coords[out_cols].to_csv(heatmap_csv, index=False, encoding='utf-8')
        logging.info(f"ヒートマップCSVを保存しました: {heatmap_csv}")
        
        # エリアごとの集計（都道府県・市区町村）
        if '都道府県' in df.columns and '市区町村' in df.columns:
            area_counts = df.groupby(['都道府県', '市区町村']).size().reset_index(name='count')
            area_csv = heatmap_csv.replace('.csv', '_area_counts.csv')
            area_counts.to_csv(area_csv, index=False, encoding='utf-8')
            logging.info(f"エリア別集計を保存しました: {area_csv}")
            
    else:
        logging.error("緯度・経度カラムが見つかりません")

def optimize_search_requests(df, address_file, output_file):
    """
    既存データ数に基づいてリクエスト回数を最適化する
    """
    logging.info("検索リクエストを最適化中...")
    
    if not os.path.exists(address_file):
        logging.error(f"住所ファイルが見つかりません: {address_file}")
        return

    # 1. エリアごとの施設数を集計
    facility_counts = defaultdict(int)
    
    # データフレームから集計
    # 住所カラムから都道府県・市区町村を抽出するか、既存のカラムを使用
    if '都道府県' in df.columns and '市区町村' in df.columns:
        for _, row in df.iterrows():
            key = f"{row['都道府県']} {row['市区町村']}".strip()
            facility_counts[key] += 1
            # スペースなしのキーも保存（マッチング率向上のため）
            key_nospace = f"{row['都道府県']}{row['市区町村']}".strip()
            facility_counts[key_nospace] += 1
    else:
        logging.warning("都道府県・市区町村カラムがないため、住所カラムから簡易集計します")
        for _, row in df.iterrows():
            addr = str(row.get('住所', ''))
            # 簡易的なマッチング（改善の余地あり）
            facility_counts[addr[:10]] += 1

    # 2. address.csvを読み込み、リクエスト回数を決定
    optimized_list = []
    
    with open(address_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row: continue
            
            # 行全体を結合して住所とする（例: "北海道 札幌市"）
            address_query = " ".join(row).strip()
            address_key = address_query.replace(" ", "") # スペース除去してマッチング
            
            # 既存件数を取得
            # 完全一致 -> スペースなし一致 -> 部分一致 の順で探す
            count = facility_counts.get(address_query)
            if count is None:
                count = facility_counts.get(address_key)
            
            # それでも見つからない場合、facility_countsのキーに含まれているか探す
            if count is None:
                for k, v in facility_counts.items():
                    if k in address_key or address_key in k:
                        count = v
                        break
            
            estimated_count = count if count is not None else 0
            
            # リクエスト回数決定ロジック (SEARCH_OPTIMIZATION.mdに基づく)
            # | 既存施設数 | リクエスト回数 |
            # |------------|----------------|
            # | 0件        | 0 (スキップ)   |
            # | 1-20件     | 1              |
            # | 21-40件    | 2              |
            # | 41-60件    | 3              |
            # | 61-80件    | 4              |
            # | 81件以上   | 5              |
            
            if estimated_count == 0:
                req_count = 0 # スキップ（または新規開拓のために1にする戦略もあり）
                # ここではドキュメント通りスキップとするが、オプションで変更可能にすべき
            elif estimated_count <= 20:
                req_count = 1
            elif estimated_count <= 40:
                req_count = 2
            elif estimated_count <= 60:
                req_count = 3
            elif estimated_count <= 80:
                req_count = 4
            else:
                req_count = 5
                
            optimized_list.append({
                'address': address_query,
                'existing_count': estimated_count,
                'request_count': req_count
            })

    # 結果出力
    if not output_file:
        output_file = 'results/optimized_search_requests.csv'
        
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['address', 'existing_count', 'request_count'])
        writer.writeheader()
        writer.writerows(optimized_list)
        
    logging.info(f"最適化結果を保存しました: {output_file}")
    
    # 統計表示
    total_req = sum(item['request_count'] for item in optimized_list)
    skipped = sum(1 for item in optimized_list if item['request_count'] == 0)
    logging.info(f"総エリア数: {len(optimized_list)}")
    logging.info(f"スキップ対象: {skipped} エリア")
    logging.info(f"総リクエスト数: {total_req}")

def main():
    parser = argparse.ArgumentParser(description='Search Optimizer')
    
    # モード選択
    parser.add_argument('--heatmap-only', action='store_true', help='ヒートマップ生成モード')
    
    # ファイルパス
    parser.add_argument('--facility-file', required=True, help='既存の施設データCSV')
    parser.add_argument('--address-file', help='検索対象の住所リストCSV（最適化モードで必須）')
    parser.add_argument('--output', help='出力ファイルパス')
    
    args = parser.parse_args()
    
    # 施設データ読み込み
    df = load_facility_data(args.facility_file)
    if df is None:
        return

    if args.heatmap_only:
        # ヒートマップ生成モード
        generate_heatmap_data(df, args.output)
    else:
        # 検索最適化モード
        if not args.address_file:
            logging.error("最適化モードには --address-file が必要です")
            return
        optimize_search_requests(df, args.address_file, args.output)

if __name__ == "__main__":
    main()

