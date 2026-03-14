#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSVファイルのGoogleMap列をリダイレクト後のURLで更新するスクリプト
元のCSVファイルを直接上書きします
"""

import csv
import logging
import argparse
import os
import sys
import shutil
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ログ設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def setup_driver(max_retries=3):
    """Selenium WebDriverをセットアップ（リトライ機能付き）"""
    for attempt in range(max_retries):
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--window-size=1280,720')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            
            # 安定性のための追加オプション
            chrome_options.add_argument('--disable-setuid-sandbox')
            chrome_options.add_argument('--disable-infobars')
            chrome_options.add_argument('--disable-notifications')
            
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # ページ読み込み戦略を"eager"に（DOMロード後に処理 - リダイレクト検出に必要）
            chrome_options.page_load_strategy = 'eager'
            
            logging.info(f"🔧 Chromeブラウザを起動中... (試行 {attempt + 1}/{max_retries})")
            driver = webdriver.Chrome(options=chrome_options)
            logging.info(f"✅ ブラウザ起動成功 (セッションID: {driver.session_id[:8]}...)")
            
            # タイムアウト設定を短めに（重いページで待ちすぎない）
            driver.set_page_load_timeout(60)  # 60秒でタイムアウト
            driver.set_script_timeout(30)
            logging.info(f"✅ タイムアウト設定完了")
            
            return driver
            
        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries - 1:
                # DevToolsActivePort エラーの場合は少し待ってリトライ
                wait_time = 2 * (attempt + 1)  # 2秒, 4秒, 6秒
                logging.warning(f"ドライバー起動失敗 ({attempt + 1}/{max_retries}): {error_msg[:80]}")
                logging.info(f"  → {wait_time}秒後に再試行...")
                time.sleep(wait_time)
            else:
                logging.error(f"ドライバー起動失敗（最大リトライ回数到達）: {error_msg[:100]}")
                raise

def get_redirected_url(driver, original_url, max_wait=15, check_interval=2):
    """
    URLにアクセスしてリダイレクト後のURLを取得
    JavaScriptによるリダイレクトを待機
    """
    try:
        logging.debug(f"🌐 URL取得開始: {original_url[:80]}...")
        # タイムアウトを個別に処理
        try:
            logging.debug(f"📡 driver.get() 実行中...")
            driver.get(original_url)
            logging.debug(f"✅ driver.get() 完了")
        except Exception as page_load_error:
            # タイムアウトでもページは部分的に読み込まれている可能性がある
            if 'timeout' in str(page_load_error).lower():
                logging.debug(f"ページロードタイムアウト（部分的に処理続行）: {str(page_load_error)[:100]}")
            else:
                raise  # その他のエラーは再スロー
        
        time.sleep(2)  # 3秒→2秒に短縮
        
        initial_url = driver.current_url
        
        # sorryページはGoogleのブロック - 即座に失敗
        if 'sorry' in initial_url.lower():
            return None, "Googleにブロックされました (sorry page)"
        
        # consent画面も失敗扱い
        if 'consent.google.com' in initial_url:
            return None, "同意画面にリダイレクトされました"
        
        # 既にPlace URL形式なら成功（/place/を含む）
        if 'google.com/maps/place/' in initial_url:
            return initial_url, None
        
        waited = 2  # 初期待機を3→2秒に短縮
        retry_count = 0
        max_retries = 6  # 8→6に削減（トータル待機時間を短縮）
        
        while waited < max_wait and retry_count < max_retries:
            current_url = driver.current_url
            
            # sorryページチェック - 即座に失敗で抜ける
            if 'sorry' in current_url.lower():
                return None, "Googleにブロックされました (sorry page)"
            
            # consent画面チェック - 即座に失敗で抜ける
            if 'consent.google.com' in current_url:
                return None, "同意画面にリダイレクトされました"
            
            # URLが変わった場合
            if current_url != initial_url:
                # Place URL形式に変換されたか確認
                if 'google.com/maps/place/' in current_url:
                    return current_url, None
                # その他のURLも一応返す（予期しないリダイレクト先）
                else:
                    return current_url, None
            
            time.sleep(check_interval)
            waited += check_interval
            retry_count += 1
        
        # タイムアウト - 最後のURLを返す
        final_url = driver.current_url
        # ?cid= のままなら変換失敗として None を返す（変更なし扱いにしない）
        if '?cid=' in final_url or '/maps/place/' not in final_url:
            return None, f"タイムアウト: リダイレクト未完了 ({final_url[:60]})"
        return final_url, None
        
    except Exception as e:
        error_msg = f"URL取得エラー: {str(e)}"
        logging.error(error_msg)
        return None, error_msg

def process_single_row(row_data, googlemap_col_index, delay=2, skip_col_name=None, driver=None):
    """
    1行分のデータを処理（リダイレクトURL取得）
    指数バックオフでリトライ実装
    
    Args:
        row_data: (row_index, row_dict) のタプル
        googlemap_col_index: GoogleMap列のインデックス
        delay: 各リクエスト間の基本待機時間
        skip_col_name: スキップ判定用の列名（この列が空またはhttpを含まない場合スキップ）
        driver: 再利用するSelenium WebDriver（Noneの場合は新規作成）
    
    Returns:
        (row_index, new_url, error)
    """
    row_index, row_dict = row_data
    
    # スキップ列のチェック（指定されている場合）
    if skip_col_name:
        skip_col_value = row_dict.get(skip_col_name, '').strip()
        if not skip_col_value or 'http' not in skip_col_value.lower():
            return row_index, None, f"スキップ: {skip_col_name}列が空またはURLなし"
    
    original_url = row_dict.get('GoogleMap', '').strip()
    
    if not original_url or original_url == '':
        return row_index, original_url, "URLが空"
    
    # リダイレクトが必要なパターン: ?cid= または /place/data=
    # それ以外の/place/URLは既にリダイレクト済み
    if '?cid=' not in original_url and '/place/data=' not in original_url:
        return row_index, None, f"スキップ: 既にリダイレクト済み"
    
    # 指数バックオフでリトライ
    max_retries = 3
    driver_provided = driver is not None  # 外部から提供されたか
    driver_created = False  # この関数で作成したか
    
    for attempt in range(max_retries):
        try:
            # ドライバーが提供されていない、またはエラーで再作成が必要な場合
            if driver is None:
                driver = setup_driver()
                driver_created = True
            
            redirected_url, error = get_redirected_url(driver, original_url)
            
            # 成功した場合
            if not error:
                # 通常の待機時間
                if delay > 0:
                    time.sleep(delay)
                return row_index, redirected_url, None
            
            # sorryページまたは同意画面の場合は指数バックオフでリトライ
            if error and ('sorry' in error.lower() or '同意画面' in error):
                if attempt < max_retries - 1:
                    # 指数バックオフ: 3秒 → 6秒 → 12秒
                    backoff_delay = delay * (2 ** attempt)
                    logging.warning(f"行{row_index + 2}: {error} - {backoff_delay}秒後にリトライ ({attempt + 1}/{max_retries})")
                    time.sleep(backoff_delay)
                    continue
                else:
                    # 最大リトライ回数に達した
                    return row_index, original_url, f"{error} (リトライ{max_retries}回失敗)"
            else:
                # その他のエラーはリトライしない（タイムアウトエラーも含む）
                if delay > 0:
                    time.sleep(delay * 0.5)  # エラー時は半分の待機時間
                return row_index, original_url, error
            
        except Exception as e:
            error_str = str(e)
            # タイムアウトエラーは軽微なのでリトライせずスキップ
            if 'timeout' in error_str.lower() or 'timed out' in error_str.lower():
                logging.warning(f"行{row_index + 2}: タイムアウト - スキップして次へ")
                if delay > 0:
                    time.sleep(delay * 0.5)
                return row_index, original_url, f"タイムアウト: {error_str[:50]}"
            
            # DevToolsActivePort エラーは並列数が多すぎる - 長めに待機
            if 'DevToolsActivePort' in error_str or 'session not created' in error_str:
                if attempt < max_retries - 1:
                    backoff_delay = delay * (3 ** attempt)  # より長い待機: 3秒 → 9秒 → 27秒
                    logging.warning(f"行{row_index + 2}: ドライバー起動失敗 - {backoff_delay}秒後にリトライ ({attempt + 1}/{max_retries})")
                    time.sleep(backoff_delay)
                    continue
                else:
                    return row_index, original_url, f"ドライバー起動失敗: {error_str[:50]}"
            
            # その他の例外はリトライ
            if attempt < max_retries - 1:
                backoff_delay = delay * (2 ** attempt)
                logging.warning(f"行{row_index + 2}: 例外発生 - {backoff_delay}秒後にリトライ ({attempt + 1}/{max_retries}): {error_str[:50]}")
                time.sleep(backoff_delay)
                continue
            else:
                return row_index, original_url, f"例外: {error_str[:50]}"
        finally:
            # この関数で作成したドライバーのみ終了（提供されたものは終了しない）
            if driver_created and driver and attempt == max_retries - 1:
                try:
                    driver.quit()
                except:
                    pass
    
    return row_index, original_url, "リトライ上限到達"

def find_googlemap_column(headers):
    """GoogleMap列を検索"""
    googlemap_patterns = [
        'googlemap', 'google map', 'google_map', 'googleマップ', 
        'url', 'map_url', 'map url'
    ]
    
    for i, header in enumerate(headers):
        header_lower = header.lower().strip()
        if any(pattern in header_lower for pattern in googlemap_patterns):
            return i, header
    
    return None, None

def worker_with_driver(row_data_list, googlemap_col_index, delay, skip_col_name):
    """
    1つのドライバーで複数行を処理するワーカー関数
    メモリ不足を防ぐため、50件ごとにブラウザを再起動
    
    Args:
        row_data_list: 処理する行のリスト [(row_index, row_dict), ...]
        googlemap_col_index: GoogleMap列のインデックス
        delay: 待機時間
        skip_col_name: スキップ判定用の列名
    
    Returns:
        処理結果のリスト [(row_index, new_url, error), ...]
    """
    driver = None
    results = []
    RESTART_INTERVAL = 50  # 50件ごとにブラウザを再起動
    
    try:
        for i, row_data in enumerate(row_data_list):
            row_index = row_data[0]
            # 50件ごとまたは最初にブラウザを起動
            if i % RESTART_INTERVAL == 0:
                # 既存のドライバーがあれば終了
                if driver:
                    try:
                        driver.quit()
                        logging.info(f"🔄 ブラウザ再起動 ({i}/{len(row_data_list)}件処理済み)")
                    except:
                        pass
                    time.sleep(2)  # 少し待機してからリソース解放
                
                # 新しいドライバーを起動
                logging.info(f"🚀 新しいブラウザを起動 (行{row_index + 2})")
                driver = setup_driver()
            
            # 1行処理
            logging.debug(f"📝 行{row_index + 2} 処理開始")
            result = process_single_row(row_data, googlemap_col_index, delay, skip_col_name, driver)
            logging.debug(f"✅ 行{row_index + 2} 処理完了: {result[2] if result[2] else 'success'}")
            results.append(result)
    
    except Exception as e:
        logging.error(f"ワーカーエラー: {str(e)[:100]}")
        # エラーが発生した場合、残りの行はエラーとして返す
        for row_data in row_data_list[len(results):]:
            results.append((row_data[0], None, f"ワーカーエラー: {str(e)[:50]}"))
    
    finally:
        # 最後にドライバーを終了
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    return results

def find_googlemap_column(headers):
    """GoogleMap関連の列を検索"""
    googlemap_patterns = [
        'googlemap', 'google map', 'google_map', 'googleマップ', 
        'url', 'map_url', 'map url'
    ]
    
    for i, header in enumerate(headers):
        header_lower = header.lower().strip()
        if any(pattern in header_lower for pattern in googlemap_patterns):
            return i, header
    
    return None, None

def main():
    parser = argparse.ArgumentParser(
        description='CSVファイルのGoogleMap列をリダイレクト後のURLで更新'
    )
    parser.add_argument(
        '--input',
        required=True,
        help='入力CSVファイルパス（このファイルを直接更新します）'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=2,
        help='各リクエスト間の待機時間（秒）'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='並列実行数'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='処理する最大件数（テスト用）'
    )
    parser.add_argument(
        '--start-row',
        type=int,
        help='処理開始行（1から開始、ヘッダー除く）'
    )
    parser.add_argument(
        '--end-row',
        type=int,
        help='処理終了行（指定行まで処理、ヘッダー除く）'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='バックアップを作成しない'
    )
    parser.add_argument(
        '--skip-if-empty',
        type=str,
        help='指定した列が空またはhttpを含まない場合、その行をスキップ（例: web）'
    )
    parser.add_argument(
        '--save-interval',
        type=int,
        default=100,
        help='中間保存の間隔（処理件数ごと、デフォルト: 100件）'
    )
    
    args = parser.parse_args()
    
    # 入力ファイルの存在確認
    if not os.path.exists(args.input):
        logging.error(f"❌ 入力ファイルが見つかりません: {args.input}")
        sys.exit(1)
    
    # バックアップ作成
    if not args.no_backup:
        backup_path = f"{args.input}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(args.input, backup_path)
        logging.info(f"📦 バックアップ作成: {backup_path}")
    
    # CSVファイルを読み込み
    logging.info(f"📖 ファイルを読み込んでいます: {args.input}")
    
    with open(args.input, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)
    
    logging.info(f"✓ {len(rows)}行のデータを読み込みました")
    
    # GoogleMap列を検索
    googlemap_col_index, googlemap_col_name = find_googlemap_column(headers)
    
    if googlemap_col_index is None:
        logging.error("❌ GoogleMap列が見つかりません")
        logging.error(f"利用可能な列: {', '.join(headers)}")
        sys.exit(1)
    
    logging.info(f"✓ GoogleMap列を発見: '{googlemap_col_name}' (インデックス: {googlemap_col_index})")
    
    # 処理対象の行を準備
    rows_to_process = []
    for i, row in enumerate(rows):
        url = row.get(googlemap_col_name, '').strip()
        if url and url != '':
            rows_to_process.append((i, row))
    
    total = len(rows_to_process)
    
    # 開始行・終了行の指定がある場合
    if args.start_row or args.end_row:
        start_idx = (args.start_row - 1) if args.start_row else 0
        end_idx = args.end_row if args.end_row else len(rows_to_process)
        
        # 範囲のバリデーション
        if start_idx < 0:
            start_idx = 0
        if end_idx > len(rows_to_process):
            end_idx = len(rows_to_process)
        
        rows_to_process = rows_to_process[start_idx:end_idx]
        logging.info(f"📌 処理範囲: {start_idx + 1}行目 〜 {end_idx}行目")
    
    if args.limit:
        rows_to_process = rows_to_process[:args.limit]
        logging.info(f"⚠️  テストモード: {args.limit}件のみ処理します")
    
    logging.info(f"🔄 {len(rows_to_process)}件のURLを処理します...")
    
    # 行をワーカー数に応じて分割（各ワーカーが複数行を処理）
    chunk_size = max(1, (len(rows_to_process) + args.workers - 1) // args.workers)  # 切り上げ
    row_chunks = []
    for i in range(0, len(rows_to_process), chunk_size):
        chunk = rows_to_process[i:i + chunk_size]
        if chunk:
            row_chunks.append(chunk)
    
    # ワーカー数を実際のチャンク数または指定数の小さい方に制限
    actual_workers = min(len(row_chunks), args.workers)
    logging.info(f"👷 {actual_workers}個のワーカーで並列処理（1ワーカーあたり約{chunk_size}件）")
    
    # 並列処理でリダイレクトURLを取得
    updated_urls = {}
    errors = []
    skipped_count = 0
    last_save = 0  # 最後に保存した処理数
    
    def save_progress():
        """現在の進捗をCSVに保存"""
        logging.info(f"\n💾 進捗を保存中... ({len(updated_urls)}件の更新)")
        # データを更新
        for row_index, new_url in updated_urls.items():
            rows[row_index][googlemap_col_name] = new_url
        
        # ファイルに書き込み
        with open(args.input, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        logging.info(f"✅ 保存完了 ({completed}/{len(rows_to_process)}件処理済み)\n")
    
    completed = 0
    
    with ThreadPoolExecutor(max_workers=actual_workers) as executor:
        # 各ワーカーにチャンクを割り当てて実行
        futures = {
            executor.submit(worker_with_driver, chunk, googlemap_col_index, args.delay, args.skip_if_empty): chunk
            for chunk in row_chunks
        }
        
        for future in as_completed(futures):
            chunk_results = future.result()
            
            # チャンクの結果を処理
            for row_index, new_url, error in chunk_results:
                completed += 1
                
                if error:
                    # スキップメッセージの場合は特別扱い
                    if error.startswith("スキップ:"):
                        skipped_count += 1
                        logging.debug(f"[{completed}/{len(rows_to_process)}] 行{row_index + 2}: {error}")
                    else:
                        errors.append((row_index + 2, rows[row_index].get(googlemap_col_name, ''), error))
                        logging.warning(f"[{completed}/{len(rows_to_process)}] 行{row_index + 2}: エラー - {error}")
                elif new_url is None:
                    # スキップされた行
                    skipped_count += 1
                    # スキップ理由をログ出力（デバッグ用）
                    logging.info(f"[{completed}/{len(rows_to_process)}] 行{row_index + 2}: {error}")
                else:
                    original = rows[row_index].get(googlemap_col_name, '')
                    if new_url != original:
                        updated_urls[row_index] = new_url
                        logging.info(f"[{completed}/{len(rows_to_process)}] 行{row_index + 2}: 更新完了")
                    else:
                        logging.info(f"[{completed}/{len(rows_to_process)}] 行{row_index + 2}: 変更なし")
                
                # 定期的に保存
                if completed - last_save >= args.save_interval:
                    save_progress()
                    last_save = completed
    
    # 最終保存（まだ保存されていない更新がある場合）
    if completed > last_save:
        logging.info(f"\n📝 最終保存中...")
        for row_index, new_url in updated_urls.items():
            rows[row_index][googlemap_col_name] = new_url
        
        with open(args.input, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        logging.info(f"✅ 最終保存完了")
    
    # 結果サマリー
    logging.info("\n" + "="*60)
    logging.info("✅ 処理完了")
    logging.info("="*60)
    logging.info(f"📊 処理結果:")
    logging.info(f"  - 総行数: {len(rows)}行")
    logging.info(f"  - 処理対象: {len(rows_to_process)}件")
    logging.info(f"  - 更新成功: {len(updated_urls)}件")
    logging.info(f"  - スキップ: {skipped_count}件")
    logging.info(f"  - エラー: {len(errors)}件")
    logging.info(f"  - 変更なし: {len(rows_to_process) - len(updated_urls) - len(errors) - skipped_count}件")
    
    if errors:
        logging.info(f"\n⚠️  エラーが発生した行:")
        for row_num, url, error in errors[:10]:  # 最初の10件のみ表示
            logging.info(f"  行{row_num}: {error}")
            logging.info(f"    URL: {url}")
        if len(errors) > 10:
            logging.info(f"  ... 他 {len(errors) - 10}件")
    
    if not args.no_backup:
        logging.info(f"\n💾 元のファイルはバックアップされています: {backup_path}")
    
    logging.info(f"\n📄 更新されたファイル: {args.input}")

if __name__ == '__main__':
    main()
