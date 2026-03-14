#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
介護施設取得用のスクレイピングスクリプト

目的:
    Bright Data Web Unlocker APIを使用して、Google Mapsから
    「介護施設」のリストを取得する。
    
    既存のfacility_BrightData_20.pyと同じ方式を採用

入力:
    - settings/address.csv: カラム [都道府県, 市区町村]

出力:
    - results/care_facilities.csv: 取得した介護施設のリスト
      [施設名, 住所, 電話番号, GoogleMap URL, 施設ID]

機能:
    - Web Unlocker API（/request エンドポイント）
    - 重複チェック（既存データとのマージ）
    - クラス設計で保守性を確保
"""

import os
import csv
import json
import time
import logging
import requests
import pandas as pd
import re
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import quote

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# パス設定
BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / 'results'
RESULTS_DIR.mkdir(exist_ok=True)
SETTINGS_DIR = BASE_DIR / 'settings'

# ファイルパス
INPUT_FILE = SETTINGS_DIR / 'address.csv'
OUTPUT_FILE = RESULTS_DIR / 'care_facilities.csv'

# API設定
API_TOKEN = '715d38ba-930d-45ce-b62f-efa0a9dc3d3a'
DATASET_ID = 'gd_m8ebnr0q2qlklc02fz'  # Google Maps Discovery

# 対象地域（コスト削減のため限定）
TARGET_PREFECTURES = ['大阪府']

# キーワードリスト
CARE_KEYWORDS = ['介護施設']


class CaresFacilityFetcher:
    """介護施設を取得するクラス（Web Scraper API - Discovery使用）"""
    
    def __init__(self, api_token: str, dataset_id: str):
        self.api_token = api_token
        self.dataset_id = dataset_id
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        self.existing_facilities = {}
        self.next_facility_id = 1
        self.gid_to_id_map = {}  # GID → 施設ID のマッピング
        
    def load_existing_facilities(self, output_path: Path) -> None:
        """既存の施設データを読み込む（重複チェック用）"""
        if not output_path.exists():
            logging.info(f"📄 既存ファイルなし: {output_path.name}")
            return
        
        try:
            # UTF-8 BOM付きファイルに対応
            with open(output_path, newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                max_id = 0
                
                for row in reader:
                    facility_id = row.get('施設ID', '')
                    facility_gid = row.get('施設GID', '')
                    place_url = row.get('GoogleMap', '')
                    
                    # 施設IDの最大値を取得
                    if facility_id:
                        try:
                            fid = int(facility_id)
                            if fid > max_id:
                                max_id = fid
                        except ValueError:
                            pass
                    
                    # GIDで重複チェック
                    if facility_gid:
                        self.existing_facilities[facility_gid] = row
                    # URLでも重複チェック
                    elif place_url:
                        self.existing_facilities[place_url] = row
            
            # 次のIDを設定
            self.next_facility_id = max_id + 1
            logging.info(f"✅ 既存施設 {len(self.existing_facilities)} 件を読み込みました")
            logging.info(f"   次の施設ID: {self.next_facility_id}")
        except Exception as e:
            logging.error(f"❌ 既存ファイル読み込みエラー: {e}")
            self.next_facility_id = 1
    
    def read_address_csv(self, input_path: Path, keywords: List[str], target_prefectures: List[str]) -> List[Dict[str, str]]:
        """
        address.csvを読み込み、検索クエリリストを作成
        
        Args:
            input_path: address.csvのパス
            keywords: 検索キーワードリスト（例: ['介護施設', '老人ホーム']）
            target_prefectures: 対象都道府県リスト（例: ['東京都', '神奈川県']）
        
        Returns:
            検索クエリリスト
        """
        if not input_path.exists():
            logging.error(f"❌ 入力ファイルが見つかりません: {input_path}")
            return []
        
        queries = []
        try:
            with open(input_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader)  # ヘッダー行をスキップ（a,b）
                
                for row in reader:
                    if len(row) < 2:
                        continue
                    
                    prefecture = row[0].strip()  # 都道府県
                    city = row[1].strip()  # 市区町村
                    
                    # 対象都道府県のみフィルタ
                    if prefecture not in target_prefectures:
                        continue
                    
                    # 各キーワードごとにクエリを生成
                    for keyword in keywords:
                        queries.append({
                            'prefecture': prefecture,
                            'city': city,
                            'keyword': keyword,
                            'location': f"{prefecture} {city}",
                            'query': f"{prefecture} {city} {keyword}"
                        })
            
            logging.info(f"✅ {len(queries)} 件の検索クエリを生成しました")
            logging.info(f"   対象: {', '.join(target_prefectures)}")
            logging.info(f"   キーワード: {', '.join(keywords)}")
            return queries
        except Exception as e:
            logging.error(f"❌ address.csv読み込みエラー: {e}")
            return []
    
    def search_facilities(self, queries: List[str]) -> List[Dict]:
        """
        Google Maps Discovery検索を実行して施設リストを取得
        
        Args:
            queries: 検索クエリリスト（文字列のリスト）
        
        Returns:
            施設データのリスト
        """
        # Discovery API用の入力フォーマット
        input_data = []
        for query_str in queries:
            input_data.append({
                "country": "JP",  # 日本（ISO国コード：大文字）
                "keyword": query_str,  # 例: "大阪府 大阪市 介護施設"
                "lat": "",  # 緯度経度は指定しない（キーワード検索）
                "long": "",
                "zoom_level": ""
            })
        
        # /scrape エンドポイント（countryパラメータで日本語レスポンスを制御）
        url = f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={self.dataset_id}&notify=false&include_errors=true&type=discover_new&discover_by=location"
        
        payload = {"input": input_data}
        
        logging.info(f"🔍 検索開始: {len(input_data)} クエリ")
        
        try:
            resp = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=300  # 5分タイムアウト
            )
            
            # 202: 非同期処理（スナップショットID返却）
            if resp.status_code == 202:
                data = resp.json()
                snapshot_id = data.get('snapshot_id')
                if snapshot_id:
                    logging.info(f"📋 スナップショットID: {snapshot_id}")
                    logging.info(f"⏳ 処理完了を待機中...")
                    facilities = self._wait_and_download(snapshot_id)
                    return facilities
                else:
                    logging.error(f"❌ snapshot_idが取得できませんでした")
                    return []
            
            # 200: 同期処理（直接結果返却）
            elif resp.status_code == 200:
                data = resp.json()
                
                # スナップショットIDが返される場合
                if isinstance(data, dict) and 'snapshot_id' in data:
                    snapshot_id = data['snapshot_id']
                    logging.info(f"📋 スナップショットID: {snapshot_id}")
                    logging.info(f"⏳ 処理完了を待機中...")
                    facilities = self._wait_and_download(snapshot_id)
                    return facilities
                
                # 直接結果が返される場合
                elif isinstance(data, list):
                    logging.info(f"✅ {len(data)} 件取得")
                    return data
                
                else:
                    logging.warning(f"⚠️ 予期しないレスポンス形式: {type(data)}")
                    return []
            
            else:
                logging.error(f"❌ API エラー: {resp.status_code}")
                logging.error(f"Response: {resp.text}")
                return []
                
        except Exception as e:
            logging.error(f"❌ エラー: {e}")
            return []
    
    def _wait_and_download(self, snapshot_id: str, max_wait_minutes: int = 30) -> List[Dict]:
        """スナップショット完了を待機してダウンロード"""
        progress_url = f"https://api.brightdata.com/datasets/v3/progress/{snapshot_id}"
        download_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json"
        
        start_time = time.time()
        max_wait_seconds = max_wait_minutes * 60
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait_seconds:
                logging.error(f"❌ タイムアウト ({max_wait_minutes} 分経過)")
                return []
            
            try:
                # プログレスチェック
                resp = requests.get(progress_url, headers={"Authorization": f"Bearer {self.api_token}"})
                resp.raise_for_status()
                progress = resp.json()
                
                status = progress.get('status')
                records = progress.get('records', 0)
                
                logging.info(f"📊 Status: {status}, Records: {records} (経過: {int(elapsed)}秒)")
                
                if status == 'ready':
                    # ダウンロード
                    logging.info(f"📥 ダウンロード中...")
                    download_resp = requests.get(download_url, headers={"Authorization": f"Bearer {self.api_token}"})
                    download_resp.raise_for_status()
                    data = download_resp.json()
                    
                    if isinstance(data, list):
                        logging.info(f"✅ {len(data)} 件取得完了")
                        return data
                    else:
                        logging.warning(f"⚠️ 予期しないデータ形式")
                        return []
                
                elif status == 'failed':
                    logging.error(f"❌ 処理失敗: {progress}")
                    return []
                
                time.sleep(10)  # 10秒ごとにチェック
                
            except Exception as e:
                logging.error(f"⚠️ エラー: {e}")
                time.sleep(10)
    
    def parse_facility_data(self, raw_data: List[Dict]) -> List[Dict]:
        """
        APIレスポンスを施設データに変換（公式フォーマット対応）
        
        Args:
            raw_data: APIから取得した生データ
        
        Returns:
            施設データリスト
        """
        facilities = []
        skipped_duplicate = 0
        skipped_no_name = 0
        skipped_no_gid = 0
        
        for item in raw_data:
            # 施設名
            facility_name = item.get('name', '')
            
            if not facility_name:
                skipped_no_name += 1
                continue
            
            # 施設GID（fid_location優先、既存コードと同じ優先順位）
            facility_gid = (
                item.get('fid_location') or  # 0x形式（公式レスポンスで確認）
                item.get('place_id') or      # ChIJ形式
                item.get('cid') or           # CID数値
                item.get('cid_location') or
                ''
            )
            
            if not facility_gid:
                logging.warning(f"⚠️ GIDなし: {facility_name}")
                skipped_no_gid += 1
                continue
            
            gid = str(facility_gid)
            
            # 重複チェック
            if gid in self.existing_facilities:
                skipped_duplicate += 1
                continue
            
            # 電話番号
            phone_raw = item.get('phone_number', '')
            phone = self._format_phone(phone_raw)
            
            # 住所
            address = item.get('address', '')
            
            # 郵便番号と都道府県の抽出
            postal_code, prefecture = self._extract_postal_and_prefecture(address)
            
            # 市区町村と残りの住所
            city, remaining_address = self._parse_address(address, postal_code, prefecture)
            
            # ウェブサイト
            website = item.get('open_website', '')
            
            # GoogleマップURL
            place_url = item.get('url', '')
            
            # 評価
            rating = item.get('rating', '')
            
            # レビュー数
            reviews_count = item.get('reviews_count', 0)
            
            # カテゴリ
            category = item.get('category', '')
            all_categories = item.get('all_categories', [])
            if all_categories and isinstance(all_categories, list):
                category = ';'.join(all_categories)
            
            # 緯度経度（公式レスポンスは lon を使用）
            latitude = item.get('lat', '')
            longitude = item.get('lon', '')  # 注意: longitude ではなく lon
            
            # 営業ステータス
            permanently_closed = item.get('permanently_closed', False)
            temporarily_closed = item.get('temporarily_closed', False)
            
            if permanently_closed:
                status = '閉業'
            elif temporarily_closed:
                status = '一時休業'
            else:
                status = '営業中'
            
            # 施設IDを割り当て
            if gid in self.gid_to_id_map:
                facility_id = self.gid_to_id_map[gid]
            else:
                facility_id = self.next_facility_id
                self.gid_to_id_map[gid] = facility_id
                self.next_facility_id += 1
            
            facilities.append({
                '施設ID': facility_id,
                '施設名': facility_name,
                '電話番号': phone,
                '郵便番号': postal_code,
                '都道府県': prefecture,
                '市区町村': city,
                '住所': remaining_address,
                'web': website,
                'GoogleMap': place_url,
                'ランク': rating,
                'レビュー数': reviews_count,
                'カテゴリ': category,
                '緯度': latitude,
                '経度': longitude,
                '施設GID': gid,
                '営業ステータス': status
            })
            
            # 既存施設に追加（メモリ上で重複チェック用）
            self.existing_facilities[gid] = True
        
        logging.info(f"✅ {len(facilities)} 件の新規施設を抽出")
        if skipped_duplicate > 0:
            logging.info(f"   重複スキップ: {skipped_duplicate} 件")
        if skipped_no_name > 0:
            logging.info(f"   施設名なしスキップ: {skipped_no_name} 件")
        if skipped_no_gid > 0:
            logging.info(f"   GIDなしスキップ: {skipped_no_gid} 件")
        
        return facilities
    
    def _format_phone(self, phone_raw: str) -> str:
        """電話番号をフォーマット（先頭0を保持）"""
        if not phone_raw:
            return ''
        
        # 数字のみ抽出
        digits = re.sub(r'\D', '', phone_raw)
        
        if len(digits) == 10:
            # 03-1234-5678
            formatted = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11:
            if digits.startswith(('070', '080', '090')):
                # 090-1234-5678
                formatted = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
            else:
                # 0120-123-456
                formatted = f"{digits[:4]}-{digits[4:7]}-{digits[7:]}"
        else:
            formatted = phone_raw
        
        # 先頭が0の場合、ゼロ幅スペースを追加（Excel対策）
        if formatted and formatted[0] == '0':
            return f"\u200b{formatted}"
        return formatted
    
    def _extract_postal_and_prefecture(self, address: str) -> tuple:
        """郵便番号と都道府県を抽出"""
        if not address:
            return '', ''
        
        postal_match = re.search(r'〒?(\d{3}-?\d{4})', address)
        postal = postal_match.group(1) if postal_match else ''
        
        # 郵便番号にゼロ幅スペースを追加（Excel対策）
        if postal and postal[0] == '0':
            postal = f"\u200b{postal}"
        
        # 郵便番号を除去した後の文字列で都道府県を検索
        address_no_postal = address.replace(f"〒{postal}", '').replace(postal, '').strip()
        prefecture_match = re.search(r'^(.{2,4}(?:都|道|府|県))', address_no_postal)
        prefecture = prefecture_match.group(1) if prefecture_match else ''
        
        return postal, prefecture
    
    def _parse_address(self, address: str, postal_code: str, prefecture: str) -> tuple:
        """市区町村と残りの住所を分割"""
        if not address:
            return '', ''
        
        # 郵便番号と都道府県を除去（ゼロ幅スペースも考慮）
        remaining = address.replace(f"〒{postal_code}", '').replace(postal_code, '').replace(prefecture, '').strip()
        remaining = remaining.replace('\u200b', '')  # ゼロ幅スペースを除去
        
        # 市区町村を抽出
        city_match = re.search(r'^([^0-9]+?(?:市|区|町|村))', remaining)
        if city_match:
            city = city_match.group(1)
            remaining = remaining.replace(city, '', 1).strip()
            return city, remaining
        
        return '', remaining
    
    def save_facilities(self, facilities: List[Dict], output_path: Path) -> None:
        """施設データをCSVに保存（既存データに追記・既存コード形式）"""
        if not facilities:
            logging.warning("⚠️ 保存する新規データがありません")
            return
        
        try:
            # 新規データをCSV形式に変換
            if output_path.exists() and output_path.stat().st_size > 0:
                # 既存ファイルに追記
                with open(output_path, 'a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        '施設ID', '施設名', '電話番号', '郵便番号', '都道府県', '市区町村', 
                        '住所', 'web', 'GoogleMap', 'ランク', 'レビュー数', 'カテゴリ', 
                        '緯度', '経度', '施設GID', '営業ステータス'
                    ])
                    for facility in facilities:
                        writer.writerow(facility)
                logging.info(f"✅ {len(facilities)} 件を追記しました: {output_path}")
            else:
                # 新規作成（ヘッダー付き）
                with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        '施設ID', '施設名', '電話番号', '郵便番号', '都道府県', '市区町村', 
                        '住所', 'web', 'GoogleMap', 'ランク', 'レビュー数', 'カテゴリ', 
                        '緯度', '経度', '施設GID', '営業ステータス'
                    ])
                    writer.writeheader()
                    for facility in facilities:
                        writer.writerow(facility)
                logging.info(f"✅ {len(facilities)} 件を新規作成しました: {output_path}")
        except Exception as e:
            logging.error(f"❌ 保存エラー: {e}")
    
    def run(self, keywords: List[str], target_prefectures: List[str], limit_per_query: int = 100) -> None:
        """
        メイン処理を実行
        
        Args:
            keywords: 検索キーワードリスト
            target_prefectures: 対象都道府県リスト
            limit_per_query: 各クエリの取得上限（未使用：Discovery APIは自動で取得）
        """
        logging.info("=" * 60)
        logging.info("🏥 介護施設取得スクリプト開始")
        logging.info("=" * 60)
        
        # 1. 既存データ読み込み
        self.load_existing_facilities(OUTPUT_FILE)
        
        # 2. 検索クエリ読み込み
        queries = self.read_address_csv(INPUT_FILE, keywords, target_prefectures)
        if not queries:
            logging.error("❌ 検索クエリが見つかりません。処理を終了します。")
            return
        
        logging.info(f"📋 クエリ数: {len(queries)} 件")
        
        # 3. Discovery APIで検索実行
        all_facilities = self.search_facilities(queries)
        
        logging.info(f"\n{'='*60}")
        logging.info(f"📊 取得完了")
        logging.info(f"   総取得件数: {len(all_facilities):,} 件")
        logging.info(f"{'='*60}\n")
        
        # 4. データ解析（重複除外）
        facilities = self.parse_facility_data(all_facilities)
        
        # 5. 保存
        self.save_facilities(facilities, OUTPUT_FILE)
        
        logging.info("=" * 60)
        logging.info("✅ 処理完了")
        logging.info("=" * 60)


def main():
    """エントリーポイント"""
    # APIトークン（指定されたトークンを使用）
    api_token = API_TOKEN
    
    # 環境変数で上書きしたい場合のみ
    env_token = os.getenv('BRIGHTDATA_API_TOKEN_OVERRIDE')
    if env_token:
        api_token = env_token
        logging.info(f"🔑 環境変数のトークンを使用: {api_token[:20]}...")
    
    if not api_token:
        logging.error("❌ APIトークンが設定されていません。")
        return
    
    # フェッチャーを初期化
    fetcher = CaresFacilityFetcher(api_token=api_token, dataset_id=DATASET_ID)
    
    # 実行
    fetcher.run(
        keywords=CARE_KEYWORDS,
        target_prefectures=TARGET_PREFECTURES,
        limit_per_query=100  # Discovery APIでは自動取得
    )


if __name__ == '__main__':
    main()
