#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSVファイルのGoogleMap列をリダイレクト後のURLで更新するスクリプト (requests版)
Seleniumを使わず、高速なrequestsライブラリのみで動作

元のCSVファイルを直接上書きします

GitHub Actions対応:
- 進捗を保存し、中断から再開可能
- エラー時のリトライ機能
- タイムアウト制限対応（処理時間制限）
"""

import csv
import logging
import argparse
import os
import sys
import shutil
import json
import re
from datetime import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

PROGRESS_FILE = "update_urls_progress.json"

def get_redirected_url(original_url, timeout=5, max_retries=2):
    """
    requestsでリダイレクト後のURLを取得（リトライ機能付き）
    大量データ処理用に最適化: タイムアウト5秒、リトライ2回
    Google Mapsの2段階リダイレクト対応（cid形式→詳細URL）
    
    メカニズム:
    1. HTTPリダイレクト（301/302）を自動追跡: allow_redirects=True
    2. response.url で最終的なURLを取得
    3. cid形式の場合、HTMLから正規URLを抽出
    
    Args:
        original_url: 元のURL
        timeout: タイムアウト秒数
        max_retries: 最大リトライ回数
    
    Returns:
        (redirected_url, error)
    """
    for attempt in range(max_retries):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8'
            }
            
            # GETリクエストで完全なリダイレクトを追跡
            response = requests.get(
                original_url,
                allow_redirects=True,
                timeout=timeout,
                headers=headers
            )
            
            final_url = response.url
            
            # Google Mapsの中間URL（cid形式）を検出
            if '?cid=' in final_url or '?q=' in final_url or '&cid=' in final_url:
                # HTMLから正規URL（/place/形式）を抽出
                # meta refreshタグやcanonical URLを探す
                html_content = response.text
                
                # 1. canonical URLを探す
                canonical_match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html_content)
                if canonical_match:
                    canonical_url = canonical_match.group(1)
                    if '/place/' in canonical_url:
                        return canonical_url, None
                
                # 2. meta refreshを探す
                refresh_match = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^;]+;url=([^"\']+)["\']', html_content, re.IGNORECASE)
                if refresh_match:
                    refresh_url = refresh_match.group(1)
                    if '/place/' in refresh_url:
                        return refresh_url, None
                
                # 3. og:urlを探す
                og_url_match = re.search(r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']', html_content)
                if og_url_match:
                    og_url = og_url_match.group(1)
                    if '/place/' in og_url:
                        return og_url, None
                
                # 詳細URLが見つからない場合はcid形式を返す
                return final_url, None
            
            # Google Mapsの正式なURLか確認
            if 'google.com/maps' in final_url:
                return final_url, None
            
            return original_url, "Google MapsのURLではありません"
            
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            return original_url, "タイムアウト"
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            return original_url, f"リクエストエラー: {str(e)}"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            return original_url, f"予期しないエラー: {str(e)}"
    
    return original_url, "最大リトライ回数超過"


def process_single_row(row_data, googlemap_col_name, delay=0, skip_col_name=None, dry_run=False):
    """
    1行分のデータを処理（リダイレクトURL取得）
    
    Args:
        row_data: (row_index, row_dict) のタプル
        googlemap_col_name: GoogleMap列の名前
        delay: 各リクエスト間の待機時間
        skip_col_name: スキップ判定用の列名（この列が空の場合スキップ）
        dry_run: dryrunモード（実際のHTTPリクエストを行わない）
    
    Returns:
        (row_index, new_url, error)
    """
    row_index, row_dict = row_data
    
    # スキップ列のチェック（指定されている場合）
    if skip_col_name:
        skip_col_value = row_dict.get(skip_col_name, '').strip()
        # 空文字列またはhttpを含まない場合はスキップ
        if not skip_col_value or 'http' not in skip_col_value.lower():
            return row_index, None, f"スキップ: {skip_col_name}列が空またはURLなし"
    
    original_url = row_dict.get(googlemap_col_name, '').strip()
    
    if not original_url or original_url == '':
        return row_index, original_url, "URLが空"
    
    # dryrunモードではHTTPリクエストをスキップ
    if dry_run:
        title = row_dict.get('title', row_dict.get('name', 'N/A'))
        return row_index, f"[DRY-RUN:{title}]", None
    
    try:
        redirected_url, error = get_redirected_url(original_url)
        
        if delay > 0:
            time.sleep(delay)
        
        if error:
            return row_index, original_url, error
        
        return row_index, redirected_url, None
        
    except Exception as e:
        return row_index, original_url, str(e)


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


def load_progress(progress_file):
    """進捗ファイルを読み込み"""
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"進捗ファイル読み込みエラー: {e}")
    return {"processed_rows": [], "updated_urls": {}, "errors": {}}


def save_progress(progress_file, progress_data):
    """進捗ファイルを保存"""
    try:
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"進捗ファイル保存エラー: {e}")


def save_checkpoint(input_file, rows, headers, progress_data):
    """チェックポイント保存（CSVとプログレス）"""
    try:
        # CSVを更新
        with open(input_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        
        # 進捗を保存
        save_progress(PROGRESS_FILE, progress_data)
        logging.info("💾 チェックポイント保存完了")
    except Exception as e:
        logging.error(f"チェックポイント保存エラー: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='CSVファイルのGoogleMap列をリダイレクト後のURLで更新 (requests版 - 高速)'
    )
    parser.add_argument(
        '--input',
        required=True,
        help='入力CSVファイルパス（このファイルを直接更新します）'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0,
        help='各リクエスト間の待機時間（秒）'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=20,
        help='並列実行数（デフォルト: 20、大量データ処理時は50-100推奨）'
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
        '--timeout',
        type=int,
        default=5,
        help='各リクエストのタイムアウト秒数（デフォルト: 5、大量データ処理用に最適化）'
    )
    parser.add_argument(
        '--max-runtime',
        type=int,
        help='最大実行時間（秒）。GitHub Actionsのタイムアウト対策'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='前回の進捗から再開'
    )
    parser.add_argument(
        '--checkpoint-interval',
        type=int,
        default=50,
        help='チェックポイント保存間隔（件数）'
    )
    parser.add_argument(
        '--skip-if-empty',
        type=str,
        help='指定した列が空の場合、その行をスキップ（例: web）'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='実際の更新を行わず、処理対象とスキップ件数のみを表示'
    )
    
    args = parser.parse_args()
    
    start_time = time.time()
    
    # dryrunモード確認
    if args.dry_run:
        logging.info("=== DRY RUN モード ===")
        logging.info("実際のURL更新は行いません")
    
    # 進捗を読み込み
    progress_data = load_progress(PROGRESS_FILE) if args.resume else {"processed_rows": [], "updated_urls": {}, "errors": {}}
    
    if args.resume and progress_data["processed_rows"]:
        logging.info(f"📂 前回の進捗を読み込みました: {len(progress_data['processed_rows'])}件処理済み")
    
    # 入力ファイルの存在確認
    if not os.path.exists(args.input):
        logging.error(f"❌ 入力ファイルが見つかりません: {args.input}")
        sys.exit(1)
    
    # バックアップ作成（初回のみ）
    backup_path = None
    if not args.no_backup and not args.resume:
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
    
    # スキップ列のチェック
    skip_col_name = args.skip_if_empty
    if skip_col_name and skip_col_name not in headers:
        logging.warning(f"⚠️  指定されたスキップ列 '{skip_col_name}' が見つかりません")
        logging.warning(f"利用可能な列: {', '.join(headers)}")
        skip_col_name = None
    elif skip_col_name:
        logging.info(f"✓ スキップ列を設定: '{skip_col_name}' が空またはhttpを含まない行はスキップします")
    
    # 処理対象の行を準備
    rows_to_process = []
    processed_rows_set = set(progress_data.get("processed_rows", []))
    already_redirected_count = 0
    
    for i, row in enumerate(rows):
        # 既に処理済みの行はスキップ
        if args.resume and i in processed_rows_set:
            continue
            
        url = row.get(googlemap_col_name, '').strip()
        if url and url != '':
            # 既にリダイレクト後の詳細URLの場合はスキップ
            if '/place/' in url and ('@' in url or 'data=' in url):
                already_redirected_count += 1
                continue
            rows_to_process.append((i, row))
    
    total = len(rows_to_process)
    
    if already_redirected_count > 0:
        logging.info(f"✓ 既にリダイレクト済み: {already_redirected_count:,}件（スキップ）")
    
    # 開始行・終了行の指定がある場合
    if args.start_row or args.end_row:
        start_idx = (args.start_row - 1) if args.start_row else 0
        end_idx = args.end_row if args.end_row else len(rows_to_process)
        rows_to_process = rows_to_process[start_idx:end_idx]
        logging.info(f"✓ 行範囲指定: {start_idx + 1}行目 〜 {end_idx}行目")
    
    # 最大件数の制限
    if args.limit and args.limit < len(rows_to_process):
        rows_to_process = rows_to_process[:args.limit]
        logging.info(f"✓ 処理件数を{args.limit}件に制限")
    
    logging.info(f"🚀 {len(rows_to_process)}件のURL更新を開始します（並列数: {args.workers}）")
    if args.max_runtime:
        logging.info(f"⏱️  最大実行時間: {args.max_runtime}秒 ({args.max_runtime/3600:.1f}時間)")
    
    # 処理時間の見積もり
    estimated_time_per_request = args.timeout + 1  # タイムアウト + オーバーヘッド
    estimated_total_time = (len(rows_to_process) * estimated_time_per_request) / args.workers
    logging.info(f"📊 推定処理時間: {estimated_total_time/60:.1f}分 ({estimated_total_time/3600:.1f}時間)")
    if args.max_runtime and estimated_total_time > args.max_runtime:
        logging.warning(f"⚠️  推定時間が最大実行時間を超える可能性があります")
        logging.warning(f"   推奨: --workers {int((len(rows_to_process) * estimated_time_per_request) / args.max_runtime) + 5} 以上")
    
    # 並列処理
    updated_urls = progress_data.get("updated_urls", {})
    errors = progress_data.get("errors", {})
    processed_rows = progress_data.get("processed_rows", [])
    skipped_count = 0
    
    should_stop = False
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_single_row, row_data, googlemap_col_name, args.delay, skip_col_name, args.dry_run): row_data
            for row_data in rows_to_process
        }
        
        completed = 0
        checkpoint_counter = 0
        
        for future in as_completed(futures):
            # タイムアウトチェック
            if args.max_runtime:
                elapsed = time.time() - start_time
                if elapsed > args.max_runtime:
                    logging.warning(f"⚠️  最大実行時間（{args.max_runtime}秒）に達しました。処理を中断します")
                    should_stop = True
                    # 残りのfutureをキャンセル
                    for f in futures:
                        f.cancel()
                    break
            
            row_index, new_url, error = future.result()
            completed += 1
            checkpoint_counter += 1
            
            # 処理済みとしてマーク
            if row_index not in processed_rows:
                processed_rows.append(row_index)
            
            if error:
                # スキップメッセージの場合は特別扱い
                if error.startswith("スキップ:"):
                    skipped_count += 1
                    logging.debug(f"[{completed}/{len(rows_to_process)}] 行{row_index + 2}: {error}")
                else:
                    errors[str(row_index)] = error
                    logging.warning(f"[{completed}/{len(rows_to_process)}] 行{row_index + 2}: エラー - {error}")
            elif new_url is None:
                # スキップされた行（new_urlがNone）
                skipped_count += 1
                logging.debug(f"[{completed}/{len(rows_to_process)}] 行{row_index + 2}: スキップ")
            else:
                original_url = rows[row_index].get(googlemap_col_name, '')
                if new_url != original_url:
                    updated_urls[str(row_index)] = new_url
                    rows[row_index][googlemap_col_name] = new_url
                    facility_name = rows[row_index].get('施設名', rows[row_index].get('title', ''))
                    logging.info(f"[{completed}/{len(rows_to_process)}] 🔄 リダイレクト検出 - 行{row_index + 2}")
                    logging.info(f"  施設: {facility_name}")
                    logging.info(f"  元URL: {original_url[:80]}..." if len(original_url) > 80 else f"  元URL: {original_url}")
                    logging.info(f"  新URL: {new_url[:80]}..." if len(new_url) > 80 else f"  新URL: {new_url}")
                else:
                    logging.debug(f"[{completed}/{len(rows_to_process)}] ✓ 変更なし - 行{row_index + 2}")
            
            # チェックポイント保存（dryrunモードではスキップ）
            if not args.dry_run and checkpoint_counter >= args.checkpoint_interval:
                progress_data = {
                    "processed_rows": processed_rows,
                    "updated_urls": updated_urls,
                    "errors": errors
                }
                save_checkpoint(args.input, rows, headers, progress_data)
                checkpoint_counter = 0
            
            # 進捗表示
            if completed % 10 == 0:
                redirected = len(updated_urls)
                logging.info(f"📊 進捗: {completed}/{len(rows_to_process)} ({completed/len(rows_to_process)*100:.1f}%) | 🔄 リダイレクト: {redirected}件")
    
    # 最終チェックポイント保存（dryrunモードではスキップ）
    if not args.dry_run:
        progress_data = {
            "processed_rows": processed_rows,
            "updated_urls": updated_urls,
            "errors": errors
        }
        save_checkpoint(args.input, rows, headers, progress_data)
    
    # 結果サマリー
    logging.info("\n" + "=" * 60)
    if args.dry_run:
        logging.info("🔍 DRY RUN モード - 結果プレビュー")
    elif should_stop:
        logging.info("⚠️  タイムアウトにより処理を中断しました")
        logging.info("💡 --resume オプションで続きから再開できます")
    else:
        logging.info("✅ 処理完了!")
        # 完了したら進捗ファイルを削除
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
            logging.info("🗑️  進捗ファイルを削除しました")
    
    logging.info("=" * 60)
    if args.dry_run:
        # dryrunモードの統計
        processing_count = len(rows_to_process) - skipped_count
        logging.info(f"📊 DRY RUN 結果:")
        logging.info(f"  - 総行数: {len(rows_to_process)}件")
        logging.info(f"  - 処理対象: {processing_count}件")
        logging.info(f"  - スキップ: {skipped_count}件")
        if skip_col_name:
            logging.info(f"  - スキップ条件: {skip_col_name}列が空またはhttpなし")
        logging.info("")
        logging.info("⚠️  注: 実際のURL更新は行われていません")
    else:
        no_change_count = len(rows_to_process) - len(updated_urls) - len(errors) - skipped_count
        logging.info(f"📊 結果サマリー:")
        logging.info(f"  - 処理対象: {len(rows_to_process)}件")
        logging.info(f"  - 🔄 リダイレクト発生: {len(updated_urls)}件")
        logging.info(f"  - ✓ 変更なし: {no_change_count}件")
        logging.info(f"  - ⏭️  スキップ: {skipped_count}件")
        logging.info(f"  - ❌ エラー: {len(errors)}件")
    
    if not args.dry_run:
        if errors:
            logging.info(f"\n⚠️  エラー詳細:")
            error_items = list(errors.items())[:10]
            for row_index, error in error_items:
                logging.info(f"  行{int(row_index) + 2}: {error}")
            if len(errors) > 10:
                logging.info(f"  ... 他 {len(errors) - 10} 件のエラー")
        
        logging.info(f"\n💾 更新されたファイル: {args.input}")
        if backup_path:
            logging.info(f"📦 バックアップ: {backup_path}")
    
    if should_stop:
        sys.exit(2)  # タイムアウト終了コード


if __name__ == '__main__':
    main()
