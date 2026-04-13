#!/usr/bin/env python3
"""
dental_new.csvのgooglemap列のURLからレビューを取得するスクリプト（Web Scraper API版）
reviews_BrightData_50.pyの出力形式に合わせる
"""
import json
import csv
import os
import sys
import time
import re
import requests
import logging
from pathlib import Path
from typing import List, Dict, Optional

# パス設定
BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / 'results'

# ▼▼▼ 修正箇所: 必ず Path() で囲むように変更 ▼▼▼
# 入力ファイル（dental_new.csv）
INPUT_CSV = Path(os.getenv('INPUT_CSV', 'results/dental_new.csv'))
if not INPUT_CSV.is_absolute():
    INPUT_CSV = BASE_DIR / INPUT_CSV

# 出力ファイル（レビューCSV）
OUTPUT_CSV = Path(os.getenv('OUTPUT_CSV', 'results/dental_new_reviews.csv'))
if not OUTPUT_CSV.is_absolute():
    OUTPUT_CSV = BASE_DIR / OUTPUT_CSV

# 増分ファイル（新規レビューのみ）
update_csv_env = os.getenv('UPDATE_CSV', '')
if update_csv_env:
    UPDATE_CSV = Path(update_csv_env)
    if not UPDATE_CSV.is_absolute():
        UPDATE_CSV = BASE_DIR / UPDATE_CSV
else:
    UPDATE_CSV = None
# ▲▲▲ 修正ここまで ▲▲▲

# 処理範囲の設定（並列処理用）
START_ROW = int(os.getenv('START_ROW', '1'))  # 1-based
END_ROW = int(os.getenv('END_ROW', '0')) if os.getenv('END_ROW') else None  # 0=全件

# API設定（Web Scraper API）
API_TOKEN = os.getenv('BRIGHTDATA_API_TOKEN')
DATASET_ID = os.getenv('BRIGHTDATA_DATASET_ID', 'gd_luzfs1dn2oa0teb81')  # Google Maps Reviews dataset
DAYS_BACK = int(os.getenv('DAYS_BACK', '10'))  # デフォルト10日分
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))  # API 1回あたりの処理件数
MAX_WAIT_MINUTES = int(os.getenv('MAX_WAIT_MINUTES', '60'))  # スナップショット待機時間


def is_disallowed_update_output(path: Path) -> bool:
    """不要な中間ファイルの出力を抑止する。"""
    return bool(re.match(r'^reviews_batch_\d+\.csv$', path.name.lower()))


if UPDATE_CSV and is_disallowed_update_output(UPDATE_CSV):
    print(f"INFO: 増分CSV '{UPDATE_CSV.name}' は出力対象外のため生成をスキップします。")
    UPDATE_CSV = None


def setup_logging():
    """ログ設定を初期化"""
    log_dir = RESULTS_DIR / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True) # parents=Trueを追加
    log_file_path = log_dir / 'dental_reviews.log'
    
    # 既存のハンドラーをクリア
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    logging.basicConfig(
        filename=str(log_file_path),
        filemode='a',  # 追記モード
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s'
    )
    # コンソールにも出力
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console)


def validate_api_token():
    """APIトークンを検証する"""
    logging.info("🔍 APIトークン検証中...")
    
    if not API_TOKEN:
        logging.error("❌ エラー: BRIGHTDATA_API_TOKEN環境変数が設定されていません")
        logging.error("解決策: GitHub Secrets で BRIGHTDATA_API_TOKEN を設定してください")
        raise ValueError("BRIGHTDATA_API_TOKEN not set")
    
    # トークンの形式を確認（最小限の検証）
    if len(API_TOKEN) < 10:
        logging.error(f"❌ エラー: APIトークンが短すぎます（長さ: {len(API_TOKEN)}）")
        raise ValueError("API token format invalid")
    
    # APIへの接続テスト
    try:
        logging.info("🧪 BrightData API への接続テスト中...")
        headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json",
        }
        
        test_url = "https://api.brightdata.com/datasets/v3/progress/test"
        response = requests.get(test_url, headers=headers, timeout=10)
        
        logging.info(f"  HTTP Status: {response.status_code}")
        
        if response.status_code == 401:
            logging.error("❌ エラー: APIトークンが無効です（401 Unauthorized）")
            logging.error("確認事項:")
            logging.error("  - トークンが正しくコピーされているか")
            logging.error("  - トークンの有効期限を確認してください")
            logging.error("  - 別のアカウントのトークンでないか確認")
            raise ValueError("API token unauthorized")
        
        if response.status_code == 403:
            logging.error("❌ エラー: APIへのアクセスが拒否されています（403 Forbidden）")
            logging.error("確認事項:")
            logging.error("  - アカウントの権限を確認")
            logging.error("  - データセットへのアクセス権限を確認")
            raise ValueError("API token forbidden")
        
        if response.status_code >= 500:
            logging.warning(f"⚠️ BrightData API が応答しません（{response.status_code}）")
            logging.warning("  → 暫定的に続行します（API復旧を待ちます）")
            return True
        
        # 2xx ステータス = OK
        logging.info("✅ APIトークン検証成功")
        return True
        
    except requests.exceptions.Timeout:
        logging.error("❌ エラー: BrightData API への接続がタイムアウトしました")
        logging.error("確認事項:")
        logging.error("  - ネットワーク接続を確認")
        logging.error("  - ファイアウォール設定を確認")
        raise
    except requests.exceptions.ConnectionError as e:
        logging.error(f"❌ エラー: BrightData API への接続に失敗しました: {e}")
        logging.error("確認事項:")
        logging.error("  - ネットワーク接続を確認")
        logging.error("  - API エンドポイントが正しいか確認")
        raise
    except Exception as e:
        logging.error(f"❌ エラー: API 検証中に予期しないエラー: {e}")
        logging.error(f"詳細: {type(e).__name__}: {str(e)}")
        return False  # 通常は続行（本当に重大なエラーのみで停止）


def validate_environment():
    """実行環境全体を検証する"""
    logging.info("🔍 実行環境検証中...")
    logging.info(f"  Input CSV: {INPUT_CSV}")
    logging.info(f"  Output CSV: {OUTPUT_CSV}")
    logging.info(f"  Dataset ID: {DATASET_ID}")
    logging.info(f"  Days Back: {DAYS_BACK}")
    logging.info(f"  Batch Size: {BATCH_SIZE}")
    logging.info(f"  Max Wait Minutes: {MAX_WAIT_MINUTES}")
    
    # 入力ファイル確認
    if not INPUT_CSV.exists():
        logging.error(f"❌ エラー: 入力CSVファイルが見つかりません: {INPUT_CSV}")
        raise FileNotFoundError(f"Input CSV not found: {INPUT_CSV}")
    
    input_lines = sum(1 for _ in open(INPUT_CSV))
    logging.info(f"✅ 入力CSV: {input_lines}行")
    
    # 出力ディレクトリ確認
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    logging.info(f"✅ 出力ディレクトリ: {OUTPUT_CSV.parent}")
    
    logging.info("✅ 環境検証完了")


class BrightDataWebScraperReviews:
    """BrightData Web Scraper API でレビューを取得"""
    
    def __init__(self, api_token: str, dataset_id: str):
        self.api_token = api_token
        self.dataset_id = dataset_id
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        self.base_url = "https://api.brightdata.com/datasets/v3"
    
    def trigger_snapshot(self, urls_with_params: List[Dict]) -> str:
        """
        スナップショット収集をトリガー（/scrape エンドポイント使用、公式ドキュメント準拠）
        """
        # 公式ドキュメント通りの /scrape エンドポイント
        trigger_url = f"{self.base_url}/scrape"
        params = {
            "dataset_id": self.dataset_id,
            "notify": "false",
            "include_errors": "true"
        }
        
        # 空のフィールドを削除（APIエラー回避）
        clean_params = []
        for item in urls_with_params:
            clean_item = {k: v for k, v in item.items() if v != "" and v is not None}
            clean_params.append(clean_item)
        
        # 公式ドキュメント通りの形式: {"input": [...]}
        payload = {"input": clean_params}
        
        # デバッグ: 送信するJSONを出力
        logging.info(f"📤 Sending payload: {json.dumps(payload, ensure_ascii=False)[:500]}...")
        logging.info(f"📤 Number of items: {len(clean_params)}")
        logging.info(f"📤 Request URL: {trigger_url}?{requests.compat.urlencode(params)}")
        
        # リトライ設定
        max_retries = 3
        retry_delays = [5, 10, 20]  # 秒
        
        for attempt in range(max_retries):
            try:
                logging.info(f"🔄 Triggering snapshot (attempt {attempt + 1}/{max_retries})...")
                
                resp = requests.post(
                    trigger_url,
                    params=params,
                    headers=self.headers,
                    data=json.dumps(payload),  # json.dumps を使用（公式に準拠）
                    timeout=120
                )
                
                # ▼▼▼ エラー情報を詳細に出力 ▼▼▼
                logging.info(f"  Response Status: {resp.status_code}")
                
                if resp.status_code >= 400:
                    logging.error(f"❌ API Error Status: {resp.status_code}")
                    logging.error(f"  Response Body: {resp.text[:1000]}")
                    
                    # ステータスコード別の詳細ログ
                    if resp.status_code == 401:
                        logging.error("  → 認証エラー: APIトークンが無効です")
                    elif resp.status_code == 403:
                        logging.error("  → 権限エラー: 要求されたリソースへのアクセス権限がありません")
                    elif resp.status_code == 429:
                        logging.error("  → レート制限: API呼び出し回数が上限に達しました")
                        logging.error("  → 対策: BATCH_SIZE を減らすか、待機時間を増やしてください")
                    elif resp.status_code >= 500:
                        logging.error(f"  → サーバーエラー: BrightData API がエラーを返しました")
                        logging.error(f"  → この場合はリトライが有効になる可能性があります")
                
                resp.raise_for_status()
                snapshot_id = resp.json()["snapshot_id"]
                logging.info(f"✅ Snapshot triggered: {snapshot_id}")
                # ▲▲▲ ここまで ▲▲▲
                
                # 成功後も少し待機（サーバー負荷軽減）
                time.sleep(2)
                return snapshot_id
                
            except requests.exceptions.HTTPError as e:
                http_error_msg = f"HTTP Error {e.response.status_code}: {str(e)}"
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logging.warning(f"⚠️ Trigger failed: {http_error_msg}")
                    logging.warning(f"   Response: {e.response.text[:300]}")
                    logging.warning(f"   Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logging.error(f"❌ Failed to trigger snapshot after {max_retries} attempts")
                    logging.error(f"   Last error: {http_error_msg}")
                    logging.error(f"   Response: {e.response.text[:500]}")
                    raise
            except requests.exceptions.Timeout as e:
                logging.error(f"❌ Request timeout: {e}")
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logging.warning(f"   Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    raise
            except requests.exceptions.ConnectionError as e:
                logging.error(f"❌ Connection error: {e}")
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logging.warning(f"   Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    raise
            except Exception as e:
                logging.error(f"❌ Failed to trigger snapshot: {type(e).__name__}: {e}")
                raise
    
    def wait_for_snapshot(self, snapshot_id: str, max_wait_minutes: int = 60) -> bool:
        """
        スナップショット完了まで待機（/progress エンドポイント使用）
        詳細なログ出力付き
        """
        progress_url = f"{self.base_url}/progress/{snapshot_id}"
        start_time = time.time()
        max_wait_seconds = max_wait_minutes * 60
        interval = 15  # ポーリング間隔（秒）
        
        logging.info("")
        logging.info("⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳")
        logging.info(f"📊 スナップショット待機開始")
        logging.info(f"  Snapshot ID: {snapshot_id}")
        logging.info(f"  最大待機時間: {max_wait_minutes}分 ({max_wait_seconds}秒)")
        logging.info(f"  ポーリング間隔: {interval}秒")
        logging.info("⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳⏳")
        logging.info("")
        
        last_status = None
        check_count = 0
        
        while True:
            elapsed = time.time() - start_time
            check_count += 1
            
            if elapsed > max_wait_seconds:
                logging.error("")
                logging.error("❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌")
                logging.error(f"❌ タイムアウト: {max_wait_minutes}分以上経過しました")
                logging.error(f"  経過時間: {int(elapsed)}秒 ({int(elapsed/60)}分{int(elapsed%60)}秒)")
                logging.error(f"  確認回数: {check_count}回")
                logging.error("❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌")
                logging.error("")
                return False
            
            try:
                resp = requests.get(
                    progress_url,
                    headers={"Authorization": f"Bearer {self.api_token}"},
                    timeout=60
                )
                
                # 5xx エラーは一時的なものとしてリトライ
                if resp.status_code >= 500:
                    logging.warning(f"⚠️ 【確認#{check_count}】 サーバーエラー (HTTP {resp.status_code})")
                    logging.warning(f"  経過: {int(elapsed)}秒 → {interval}秒後に再試行")
                    time.sleep(interval)
                    continue
                
                resp.raise_for_status()
                data = resp.json()
                status = data.get("status")
                
                # ステータス変化または定期的にログ出力
                is_status_changed = (status != last_status)
                is_periodic_log = (int(elapsed) % 30 == 0)
                
                if is_status_changed:
                    logging.info(f"📈 【確認#{check_count}】 ステータス変化: {status}")
                    logging.info(f"  経過時間: {int(elapsed)}秒 ({int(elapsed/60)}分{int(elapsed%60)}秒)")
                    last_status = status
                elif is_periodic_log:
                    logging.info(f"💭 【確認#{check_count}】 処理中: {status}")
                    logging.info(f"  経過時間: {int(elapsed)}秒 ({int(elapsed/60)}分{int(elapsed%60)}秒)")
                    
                    # 進捗情報が含まれている場合は表示
                    if "progress" in data:
                        progress_info = data.get("progress")
                        logging.info(f"  進捗: {progress_info}")
                    if "record_size" in data:
                        record_size = data.get("record_size")
                        logging.info(f"  レコード数: {record_size}")
                
                if status == "ready":
                    logging.info("")
                    logging.info("✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅")
                    logging.info(f"✅ スナップショット完成！")
                    logging.info(f"  確認回数: {check_count}回")
                    logging.info(f"  総経過時間: {int(elapsed)}秒 ({int(elapsed/60)}分{int(elapsed%60)}秒)")
                    logging.info("✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅")
                    logging.info("")
                    time.sleep(3)  # 完了後も少し待機
                    return True
                    
                elif status == "failed":
                    error_msg = data.get("error_message", "Unknown error")
                    logging.error("")
                    logging.error("❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌")
                    logging.error(f"❌ スナップショット失敗: {error_msg}")
                    logging.error(f"  確認回数: {check_count}回")
                    logging.error(f"  経過時間: {int(elapsed)}秒 ({int(elapsed/60)}分{int(elapsed%60)}秒)")
                    logging.error("❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌")
                    logging.error("")
                    return False
                
                # collecting / digesting / その他 → まだ処理中
                time.sleep(interval)
                
            except requests.exceptions.RequestException as e:
                # 502 / Connection broken などは一時的エラーとしてリトライ
                logging.warning(f"⚠️ 【確認#{check_count}】 通信エラー: {type(e).__name__}")
                logging.warning(f"  エラー: {str(e)[:100]}")
                logging.warning(f"  経過: {int(elapsed)}秒 → {interval}秒後に再試行")
                time.sleep(interval)
                continue
            except Exception as e:
                logging.error(f"❌ 【確認#{check_count}】 予期しないエラー: {type(e).__name__}: {e}")
                logging.error(f"  経過: {int(elapsed)}秒 → {interval}秒後に再試行")
                time.sleep(interval)
                continue
    
    def get_snapshot_data(self, snapshot_id: str, retries: int = 5) -> List[Dict]:
        """
        スナップショットデータを取得（リトライ機能付き）
        """
        snapshot_url = f"{self.base_url}/snapshot/{snapshot_id}?format=json"
        interval = 10  # リトライ間隔（秒）
        
        for attempt in range(1, retries + 1):
            try:
                logging.info(f"📥 Downloading snapshot data (attempt {attempt}/{retries})...")
                resp = requests.get(
                    snapshot_url,
                    headers={"Authorization": f"Bearer {self.api_token}"},
                    timeout=60
                )
                
                # 5xx エラーは一時的なものとしてリトライ
                if resp.status_code >= 500:
                    logging.warning(f"⚠️ Snapshot download {resp.status_code} (attempt {attempt}/{retries})")
                    if attempt < retries:
                        time.sleep(interval)
                        continue
                    else:
                        raise requests.exceptions.HTTPError(f"Failed after {retries} attempts")
                
                resp.raise_for_status()
                data = resp.json()
                
                # デバッグ: 実際のレスポンスを完全に出力
                logging.info(f"📊 Response type: {type(data)}")
                logging.info(f"📝 Full response (first 2000 chars): {json.dumps(data, ensure_ascii=False)[:2000]}")
                
                if isinstance(data, list):
                    logging.info(f"✅ Retrieved {len(data)} items from snapshot")
                    if len(data) > 0:
                        # 最初のアイテムのキーを確認
                        logging.info(f"📋 First item keys: {list(data[0].keys())}")
                        logging.info(f"📝 First item (full): {json.dumps(data[0], ensure_ascii=False, indent=2)}")
                        
                        # reviewsキーがあるか確認
                        if 'reviews' in data[0]:
                            logging.info(f"✨ Found 'reviews' key in first item, contains {len(data[0]['reviews'])} reviews")
                    return data
                elif isinstance(data, dict):
                    logging.warning(f"⚠️ Response is dict, keys: {list(data.keys())}")
                    logging.info(f"📝 Response (full): {json.dumps(data, ensure_ascii=False, indent=2)[:2000]}")
                    
                    # reviewsキーやdataキーがあるか確認
                    if 'reviews' in data:
                        logging.info(f"✨ Found 'reviews' key at top level, contains {len(data['reviews'])} items")
                        return data['reviews']
                    elif 'data' in data:
                        logging.info(f"✨ Found 'data' key at top level, contains {len(data['data'])} items")
                        return data['data']
                    elif 'results' in data:
                        logging.info(f"✨ Found 'results' key at top level, contains {len(data['results'])} items")
                        return data['results']
                    else:
                        logging.warning(f"⚠️ No known data key found, returning empty list")
                        return []
                else:
                    logging.warning(f"⚠️ Unexpected response format: {type(data)}")
                    return []
                    
            except requests.exceptions.RequestException as e:
                logging.warning(f"⚠️ Snapshot download error: {e} (attempt {attempt}/{retries})")
                if attempt < retries:
                    time.sleep(interval)
                    continue
                else:
                    logging.error(f"❌ Failed to download snapshot after {retries} attempts")
                    return []
            except Exception as e:
                logging.error(f"❌ Unexpected error during snapshot download: {e}")
                if attempt < retries:
                    time.sleep(interval)
                    continue
                else:
                    return []
        
        return []  # すべてのリトライが失敗した場合
    
    def process_batch(self, urls_with_params: List[Dict], batch_id: str = "0") -> List[Dict]:
        """
        バッチ処理: トリガー → 待機 → データ取得
        詳細なログ出力付き
        """
        logging.info("")
        logging.info("🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀")
        logging.info(f"🚀 バッチ処理開始: ID={batch_id}")
        logging.info(f"  処理対象: {len(urls_with_params)}件")
        logging.info("🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀")
        
        start_time = time.time()
        
        try:
            # ステップ1: トリガー
            logging.info("")
            logging.info("[Step 1/3] APIをトリガー中...")
            logging.info(f"  URL数: {len(urls_with_params)}")
            logging.info(f"  最初のURL（サンプル）: {urls_with_params[0].get('url', 'N/A')[:60] if urls_with_params else 'N/A'}")
            
            trigger_start = time.time()
            snapshot_id = self.trigger_snapshot(urls_with_params)
            trigger_elapsed = time.time() - trigger_start
            
            logging.info(f"✅ APIトリガー完了 ({trigger_elapsed:.1f}秒)")
            logging.info(f"  Snapshot ID: {snapshot_id}")
            
            # ステップ2: 待機
            logging.info("")
            logging.info("[Step 2/3] スナップショット処理待機中...")
            
            wait_start = time.time()
            if not self.wait_for_snapshot(snapshot_id, max_wait_minutes=MAX_WAIT_MINUTES):
                logging.error(f"❌ バッチ {batch_id}: スナップショット処理失敗")
                elapsed = time.time() - start_time
                logging.error(f"  総処理時間: {int(elapsed)}秒")
                return []
            wait_elapsed = time.time() - wait_start
            
            logging.info(f"✅ スナップショット処理完了 ({wait_elapsed:.1f}秒)")
            
            # ステップ3: データ取得
            logging.info("")
            logging.info("[Step 3/3] データダウンロード中...")
            
            download_start = time.time()
            reviews = self.get_snapshot_data(snapshot_id, retries=5)
            download_elapsed = time.time() - download_start
            
            logging.info(f"✅ データダウンロード完了 ({download_elapsed:.1f}秒)")
            logging.info(f"  取得レビュー数: {len(reviews)}件")
            
            # バッチ完了サマリー
            elapsed = time.time() - start_time
            logging.info("")
            logging.info("========== バッチ完了サマリー ==========")
            logging.info(f"  バッチID: {batch_id}")
            logging.info(f"  入力URL数: {len(urls_with_params)}件")
            logging.info(f"  出力レビュー数: {len(reviews)}件")
            logging.info(f"  処理時間: {int(elapsed)}秒 ({int(elapsed/60)}分{int(elapsed%60)}秒)")
            logging.info(f"    - APIトリガー: {trigger_elapsed:.1f}秒")
            logging.info(f"    - 待機: {wait_elapsed:.1f}秒")
            logging.info(f"    - ダウンロード: {download_elapsed:.1f}秒")
            logging.info("======================================")
            logging.info("")
            
            return reviews
            
        except Exception as e:
            elapsed = time.time() - start_time
            logging.error("")
            logging.error("❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌")
            logging.error(f"❌ バッチ処理エラー (batch_id={batch_id})")
            logging.error(f"  エラー: {type(e).__name__}: {str(e)[:100]}")
            logging.error(f"  処理時間: {int(elapsed)}秒")
            logging.error("❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌")
            logging.error("")
            raise
        
        # 3. データ取得
        reviews = self.get_snapshot_data(snapshot_id)
        
        return reviews


def load_dental_csv():
    """dental_new.csvを読み込み、処理対象のエントリを返す"""
    if not INPUT_CSV.exists():
        logging.error(f'入力CSVファイルが見つかりません: {INPUT_CSV}')
        return []
    
    entries = []
    with open(INPUT_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)
    
    if not all_rows:
        logging.error('CSVファイルが空です')
        return []
    
    total_rows = len(all_rows)
    
    # 処理範囲の決定
    # START_ROW=1 → all_rows[0]（最初のデータ行）
    start_idx = START_ROW - 1  # 1-based → 0-based
    if END_ROW:
        end_idx = END_ROW  # END_ROW行目まで（END_ROW番目まで含む）
    else:
        end_idx = total_rows
    
    logging.info(f'CSVファイル: {INPUT_CSV}')
    logging.info(f'総行数: {total_rows}')
    logging.info(f'処理範囲: 行{START_ROW}～{END_ROW if END_ROW else "最終行"} ({end_idx - start_idx}行)')
    
    # スキップ判定に使う列名（環境変数から取得、デフォルトは 'web'）
    skip_column = os.getenv('SKIP_COLUMN', 'web')
    if not skip_column or skip_column.strip() == '':
        skip_column = 'web'
    logging.info(f'=========================================')
    logging.info(f'🔍 スキップ判定列: [{skip_column}]')
    logging.info(f'=========================================')
    
    for idx, row in enumerate(all_rows[start_idx:end_idx], start=START_ROW):
        facility_id = (row.get('施設ID', '') or row.get('post_id', '')).strip()
        facility_name = row.get('施設名', '').strip()
        gid = row.get('施設GID', '').strip()
        skip_value = row.get(skip_column, '').strip()
        googlemap_url = (row.get('GoogleMap', '') or row.get('googlemap', '')).strip()
        
        # 指定された列が空の場合はスキップ
        if not skip_value:
            logging.info(f'行{idx}: {skip_column}列が空のためスキップ - {facility_name}')
            continue
        
        if not googlemap_url:
            logging.warning(f'行{idx}: GoogleMap URLがありません - {facility_name}')
            continue
        
        entries.append({
            'row_number': idx,
            'facility_id': facility_id,
            'facility_name': facility_name,
            'gid': gid,
            'url': googlemap_url
        })
    
    logging.info(f'処理対象: {len(entries)}施設')
    return entries


def load_existing_reviews():
    """既存のレビューファイルを読み込む（ファイルがなければ新規作成）"""
    if not OUTPUT_CSV.exists():
        logging.info(f'レビューファイルが見つかりません: {OUTPUT_CSV}')
        logging.info('新規ファイルを作成します')
        
        # 新規ファイルをヘッダー付きで作成
        try:
            OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
            with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['レビューID', '施設ID', '施設GID', 'レビュワー評価', 'レビュワー名',
                               'レビュー日時', 'レビュー本文', 'レビュー要約', 'レビューGID'])
            logging.info(f'新規ファイルを作成しました: {OUTPUT_CSV}')
        except Exception as e:
            logging.error(f'ファイル作成に失敗: {e}')
            return [], set(), 100
        
        return [], set(), 100
    
    reviews = []
    gid_set = set()
    max_review_id = 100
    
    with open(OUTPUT_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        has_facility_gid = '施設GID' in fieldnames if fieldnames else False
        if not has_facility_gid:
            logging.warning('既存レビューファイルに施設GID列がありません')
        
        for row in reader:
            if not has_facility_gid:
                row['施設GID'] = ''
            reviews.append(row)
            
            gid = row.get('レビューGID', '') or ''
            if gid and isinstance(gid, str):
                gid_set.add(gid.strip())
            
            # 最大レビューIDを取得
            try:
                review_id_str = row.get('レビューID', '0') or '0'
                if review_id_str and isinstance(review_id_str, str):
                    review_id = int(review_id_str.strip())
                    if review_id > max_review_id:
                        max_review_id = review_id
            except (ValueError, TypeError):
                pass
    
    logging.info(f'既存レビュー: {len(reviews)}件')
    logging.info(f'ユニークGID: {len(gid_set)}')
    logging.info(f'最大レビューID: {max_review_id}')
    return reviews, gid_set, max_review_id


def extract_review_data_from_api(review_item: Dict, facility_id: str, facility_gid: str) -> Optional[Dict]:
    """
    Web Scraper APIから取得したレビューデータを抽出（公式レスポンス形式対応）
    """
    try:
        # Web Scraper API の実際のレスポンスフィールド名に合わせる
        # review_id: レビューID
        review_id = (review_item.get('review_id') or '').strip()
        
        # reviewer_name: レビュワー名
        reviewer_name = (review_item.get('reviewer_name') or '').strip()
        
        # review_rating: 評価（1-5）
        rating = review_item.get('review_rating', '')
        
        # review_date: レビュー日時
        timestamp = (review_item.get('review_date') or '').strip()
        
        # review: レビュー本文
        text = (review_item.get('review') or '').strip()
        
        # その他の有用な情報
        response_of_owner = (review_item.get('response_of_owner') or '').strip()
        number_of_likes = review_item.get('number_of_likes', 0)
        
        return {
            'review_id': review_id,
            'review_gid': review_id,  # レビューGID（review_idと同じ）
            'facility_id': facility_id,
            'facility_gid': facility_gid,
            'reviewer_name': reviewer_name,
            'rating': rating,
            'timestamp': timestamp,
            'text': text,
            'response_of_owner': response_of_owner,
            'number_of_likes': number_of_likes
        }
    
    except Exception as e:
        logging.warning(f'レビューデータ抽出失敗: {e}')
        return None


def match_reviews_with_existing(fetched_reviews: List[Dict], existing_gid_set: set, next_review_id: int) -> tuple:
    """
    取得したレビューと既存のGIDセットを照合
    """
    new_reviews = []
    skipped = 0
    current_id = next_review_id
    
    for review in fetched_reviews:
        review_gid = review.get('review_id', '').strip()
        
        if review_gid in existing_gid_set:
            skipped += 1
        else:
            new_reviews.append({
                'assigned_review_id': current_id,
                'facility_id': review.get('facility_id', ''),
                'facility_gid': review.get('facility_gid', ''),
                'reviewer_name': review.get('reviewer_name', ''),
                'rating': review.get('rating', ''),
                'timestamp': review.get('timestamp', ''),
                'text': review.get('text', ''),
                'review_gid': review_gid
            })
            current_id += 1
    
    return new_reviews, skipped, current_id


def save_reviews_to_csv(csv_file_path: Path, reviews: List[Dict]):
    """レビューをCSVファイルに保存"""
    if not reviews:
        return
    
    fieldnames = ['レビューID', '施設ID', '施設GID', 'レビュワー評価', 'レビュワー名',
                  'レビュー日時', 'レビュー本文', 'レビュー要約', 'レビューGID']
    
    csv_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for review in reviews:
            if 'assigned_review_id' in review:
                # 新規レビュー
                writer.writerow({
                    'レビューID': str(review.get('assigned_review_id', '')).strip(),
                    '施設ID': str(review.get('facility_id', '')).strip(),
                    '施設GID': str(review.get('facility_gid', '')).strip(),
                    'レビュワー評価': str(review.get('rating', '')).strip(),
                    'レビュワー名': str(review.get('reviewer_name', '')).strip(),
                    'レビュー日時': str(review.get('timestamp', '')).strip(),
                    'レビュー本文': str(review.get('text', '')).strip(),
                    'レビュー要約': '',  # 要約は空
                    'レビューGID': str(review.get('review_gid', '')).strip()
                })
            else:
                # 既存レビュー
                writer.writerow({
                    'レビューID': str(review.get('レビューID', '')).strip(),
                    '施設ID': str(review.get('施設ID', '')).strip(),
                    '施設GID': str(review.get('施設GID', '')).strip(),
                    'レビュワー評価': str(review.get('レビュワー評価', '')).strip(),
                    'レビュワー名': str(review.get('レビュワー名', '')).strip(),
                    'レビュー日時': str(review.get('レビュー日時', '')).strip(),
                    'レビュー本文': str(review.get('レビュー本文', '')).strip(),
                    'レビュー要約': str(review.get('レビュー要約', '')).strip(),
                    'レビューGID': str(review.get('レビューGID', '')).strip()
                })


def main():
    """メイン処理"""
    # ▼▼▼ setup_logging() とバリデーションは呼び出し元で実施するため、ここでは不要 ▼▼▼
    # print('='*80)
    # print('dental_new.csv レビュー取得ツール (Web Scraper API)')
    # print('='*80)
    # setup_logging()
    # if not API_TOKEN:
    #     logging.error('❌ BRIGHTDATA_API_TOKEN environment variable not set')
    #     sys.exit(1)
    # ▲▲▲ ここまで ▲▲▲
    
    logging.info(f'入力CSV: {INPUT_CSV}')
    logging.info(f'出力CSV: {OUTPUT_CSV}')
    if UPDATE_CSV:
        logging.info(f'増分CSV: {UPDATE_CSV}')
    logging.info(f'Dataset ID: {DATASET_ID}')
    logging.info(f'Days back: {DAYS_BACK}')
    logging.info(f'Batch size: {BATCH_SIZE}')
    logging.info(f'処理範囲: 行{START_ROW}～{END_ROW if END_ROW else "最終行"}')
    
    # dental_new.csvを読み込み
    try:
        entries = load_dental_csv()
    except Exception as e:
        logging.error(f"❌ CSV読み込みエラー: {e}")
        raise
    
    if not entries:
        logging.error('処理対象がありません')
        sys.exit(1)
    
    # 既存レビューを読み込み
    try:
        existing_reviews, existing_gid_set, max_review_id = load_existing_reviews()
    except Exception as e:
        logging.error(f"❌ 既存レビュー読み込みエラー: {e}")
        raise
    
    next_review_id = max_review_id + 1
    
    # BrightData Web Scraper APIクライアント
    try:
        client = BrightDataWebScraperReviews(API_TOKEN, DATASET_ID)
    except Exception as e:
        logging.error(f"❌ APIクライアント初期化エラー: {e}")
        raise
    
    # バッチに分割
    batches = []
    facility_map = {}  # URL -> 施設情報のマッピング
    
    for i in range(0, len(entries), BATCH_SIZE):
        batch_entries = entries[i:i + BATCH_SIZE]
        urls_with_params = []
        
        for entry in batch_entries:
            url = entry['url']
            # 公式ドキュメント準拠: url と days_limit を指定
            payload = {
                "url": url,
                "days_limit": DAYS_BACK  # 公式では days_limit を使用
            }
            urls_with_params.append(payload)
            facility_map[url] = entry
        
        batches.append(urls_with_params)
    
    logging.info(f'📦 {len(batches)}個のAPIチャンクを作成しました（1チャンク={BATCH_SIZE}件）')
    logging.info(f'{"="*80}\n')
    
    # 統計情報
    stats = {
        'total_facilities': len(entries),
        'total_fetched_reviews': 0,
        'new_reviews': 0,
        'skipped_reviews': 0,
        'new_reviews_list': [],
        'failed_batches': 0,
        'successful_batches': 0
    }
    
    # 全体処理の開始時刻
    main_start_time = time.time()
    
    # チャンクごとに処理
    for batch_idx, urls_with_params in enumerate(batches, start=1):
        batch_start_time = time.time()
        
        # 進捗情報の表示
        progress_pct = (batch_idx - 1) * 100 // len(batches)
        remaining_batches = len(batches) - batch_idx
        elapsed = batch_start_time - main_start_time
        
        if batch_idx > 1 and elapsed > 0:
            avg_time_per_batch = elapsed / (batch_idx - 1)
            est_remaining = avg_time_per_batch * remaining_batches
        else:
            est_remaining = 0
        
        logging.info("")
        logging.info(f"{'─'*80}")
        logging.info(f"📊 全体進捗: {batch_idx}/{len(batches)} チャンク [{progress_pct}%]")
        logging.info(f"  経過時間: {int(elapsed)}秒")
        if est_remaining > 0:
            logging.info(f"  予想残り: {int(est_remaining)}秒 ({int(est_remaining/60)}分)")
        logging.info(f"{'─'*80}")
        
        logging.info(f'\n🔄 APIチャンク {batch_idx}/{len(batches)} 処理開始')
        logging.info(f'   URL数: {len(urls_with_params)}件')
        
        try:
            # APIからレビュー取得
            reviews = client.process_batch(urls_with_params, batch_id=str(batch_idx))
            
            if not reviews:
                logging.warning(f'❌ APIチャンク {batch_idx} でレビューが取得できませんでした')
                stats['failed_batches'] += 1
                logging.info(f'   結果: 失敗 (リビュー取得0件)')
                continue
            
            logging.info(f'✅ APIチャンク {batch_idx}: {len(reviews)}件のレビュー取得完了')
            
            # レビュー処理カウンタ
            batch_new_count = 0
            batch_skip_count = 0
            batch_error_count = 0
            
            # レビューを施設別に分類
            for review_item in reviews:
                # エラーレスポンスの場合はスキップ
                if review_item.get('error') or review_item.get('error_code'):
                    batch_error_count += 1
                    continue
                
                # place_urlまたはurlキーで施設を特定（input.urlから取得）
                input_data = review_item.get('input', {})
                place_url = (
                    input_data.get('url', '') or 
                    review_item.get('place_url', '') or 
                    review_item.get('url', '') or 
                    review_item.get('query', {}).get('place_url', '')
                )
                
                if not place_url or place_url not in facility_map:
                    batch_error_count += 1
                    continue
                
                facility = facility_map[place_url]
                facility_id = facility['facility_id']
                facility_gid = facility['gid']
                
                # レビューデータを抽出
                review_data = extract_review_data_from_api(review_item, facility_id, facility_gid)
                if not review_data:
                    batch_error_count += 1
                    continue
                
                stats['total_fetched_reviews'] += 1
                
                # 既存のGIDと照合
                review_gid = review_data.get('review_id', '')
                if review_gid in existing_gid_set:
                    batch_skip_count += 1
                    stats['skipped_reviews'] += 1
                else:
                    new_review = {
                        'assigned_review_id': next_review_id,
                        'facility_id': facility_id,
                        'facility_gid': facility_gid,
                        'reviewer_name': review_data.get('reviewer_name', ''),
                        'rating': review_data.get('rating', ''),
                        'timestamp': review_data.get('timestamp', ''),
                        'text': review_data.get('text', ''),
                        'review_gid': review_gid
                    }
                    stats['new_reviews_list'].append(new_review)
                    existing_gid_set.add(review_gid)
                    batch_new_count += 1
                    stats['new_reviews'] += 1
                    next_review_id += 1
            
            # バッチ処理完了ログ
            batch_elapsed = time.time() - batch_start_time
            stats['successful_batches'] += 1
            
            logging.info(f"")
            logging.info(f"✅ APIチャンク {batch_idx} 完了")
            logging.info(f'   処理時間: {batch_elapsed:.1f}秒')
            logging.info(f'   新規: {batch_new_count}件 | スキップ: {batch_skip_count}件 | エラー: {batch_error_count}件')
            logging.info(f'   累計新規: {stats["new_reviews"]}件 | 累計スキップ: {stats["skipped_reviews"]}件')
            if batch_error_count > 0:
                logging.info('   注記: エラー件数はAPI応答内の個別エラーレコード数です（チャンク失敗件数ではありません）')
            
            # チャンクごとに保存
            if stats['new_reviews_list']:
                all_reviews = existing_reviews + stats['new_reviews_list']
                save_reviews_to_csv(OUTPUT_CSV, all_reviews)
                logging.info(f'💾 途中保存完了: {len(all_reviews)}件 → {OUTPUT_CSV}')
            
        except Exception as e:
            batch_elapsed = time.time() - batch_start_time
            stats['failed_batches'] += 1
            logging.error(f'❌ APIチャンク {batch_idx} 処理エラー')
            logging.error(f'   エラー: {type(e).__name__}: {str(e)[:100]}')
            logging.error(f'   処理時間: {batch_elapsed:.1f}秒')
            import traceback
            traceback.print_exc()
    
    # 最終レポート
    total_elapsed = time.time() - main_start_time
    
    logging.info(f"\n{'='*80}")
    logging.info("🎉 全チャンク処理完了")
    logging.info(f"{'='*80}")
    logging.info(f"処理概要:")
    logging.info(f"  総処理時間: {int(total_elapsed)}秒 ({int(total_elapsed/60)}分{int(total_elapsed%60)}秒)")
    logging.info(f"  処理施設数: {stats['total_facilities']}")
    logging.info(f"  チャンク統計:")
    logging.info(f"    成功: {stats['successful_batches']}/{len(batches)}")
    logging.info(f"    失敗: {stats['failed_batches']}/{len(batches)}")
    logging.info(f"")
    logging.info(f"レビュー統計:")
    logging.info(f"  取得総数: {stats['total_fetched_reviews']}件")
    logging.info(f"  新規レビュー: {stats['new_reviews']}件")
    logging.info(f"  スキップ（既存）: {stats['skipped_reviews']}件")
    
    if stats['total_fetched_reviews'] > 0:
        new_rate = stats['new_reviews'] / stats['total_fetched_reviews'] * 100
        logging.info(f"  新規率: {new_rate:.1f}%")
    
    if total_elapsed > 0:
        reviews_per_min = stats['total_fetched_reviews'] / (total_elapsed / 60)
        logging.info(f"  処理速度: {reviews_per_min:.1f}件/分")
    
    logging.info(f"{'='*80}")
    
    # 全レビューを保存
    if stats['new_reviews_list'] or existing_reviews:
        all_reviews = existing_reviews + stats['new_reviews_list']
        save_reviews_to_csv(OUTPUT_CSV, all_reviews)
        logging.info(f'\n💾 最終出力ファイル: {OUTPUT_CSV}')
        logging.info(f'   既存: {len(existing_reviews)}件')
        logging.info(f'   新規: {len(stats["new_reviews_list"])}件')
        logging.info(f'   合計: {len(all_reviews)}件')
    
    # 増分ファイル（新規レビューのみ）を保存
    if UPDATE_CSV and stats['new_reviews_list']:
        # UPDATE_CSVもPathオブジェクトになっているので安全
        save_reviews_to_csv(UPDATE_CSV, stats['new_reviews_list'])
        logging.info(f'\n📄 増分ファイル: {UPDATE_CSV}')
        logging.info(f'   新規レビュー: {len(stats["new_reviews_list"])}件')
    
    logging.info(f'\n{"="*80}')


if __name__ == '__main__':
    try:
        # ロギング初期化
        setup_logging()
        
        logging.info("="*50)
        logging.info("🚀 dental_reviews_fetch started")
        logging.info("="*50)
        
        # 実行環境検証
        validate_environment()
        
        # APIトークン検証
        validate_api_token()
        
        # メイン処理実行
        logging.info("")
        logging.info("📊 データ処理開始...")
        main()
        
        logging.info("")
        logging.info("="*50)
        logging.info("✅ 処理完了しました")
        logging.info("="*50)
        
    except KeyboardInterrupt:
        logging.warning('\n⚠️ ユーザーによる中断')
        sys.exit(130)
    
    except FileNotFoundError as e:
        logging.error(f'\n❌ ファイルエラー: {e}')
        sys.exit(2)
    
    except ValueError as e:
        logging.error(f'\n❌ 設定エラー: {e}')
        sys.exit(3)
    
    except Exception as e:
        logging.error(f'\n❌ 予期しないエラーが発生しました: {e}')
        logging.error(f'エラー型: {type(e).__name__}')
        import traceback
        logging.error('詳細:')
        for line in traceback.format_exc().split('\n'):
            if line:
                logging.error(f'  {line}')
        sys.exit(1)