"""
[Fundamental Fix 5 (Reverting to Sophi's URL)]
Log #30 confirms that the /search?q= URL (my idea) is being blocked and
returns empty JSON (no 'organic' or 'local_results').

Log #25 (the user's log) showed that the URL
https://www.google.com/maps/search/... (Sophi's idea) *WAS* working
for some queries (like "北海道 栗山町") and returned an 'organic' key.

My mistake was switching away from /maps/search/ in Fix 4.

This version reverts to Sophi's URL structure (/maps/search/)
while keeping the 'format: "json"' and the corrected GID logic
('map_id_encoded' priority) which was missing in Log #25.

- API URL: Keep as https://api.brightdata.com/request
- Payload: Keep as {"zone":..., "url":..., "format": "json"}
- ★ URL Construction: Revert to Sophi's
  https://www.google.com/maps/search/{query}/?hl=ja&gl=jp&start={start}&brd_json=1 format.
- ★ collect_places: Keep Sophi's recursive logic.
- ★ GID Logic: Keep 'map_id_encoded' as priority (This fixes the bug from Log #25).
- JSON Log Saving: Keep.
"""
import os
import requests
import json
import csv
import datetime
import re
from bs4 import BeautifulSoup
import logging
import time
import random
from math import ceil
from urllib.parse import quote
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# InsecureRequestWarning を無効にする
urllib3.disable_warnings(InsecureRequestWarning)

randomC = random.uniform(1, 5)


def update_mini(base_query, api_token, zone_name, file_path, facility_file, update_facility_path, exclude_gids_path,
                results_dir, fid_file_path=None, included_type=None, duplicate_analysis_path=None):
    
    def preserve_leading_zero_text(s: str) -> str:
        """
        0から始まる文字列（郵便番号、電話番号など）がCSVで開いたときに
        0落ちしないよう、ゼロ幅スペースを先頭に追加する
        """
        # s が None や数値の場合も考慮し、文字列に変換してからチェック
        s_str = str(s or "")
        if re.fullmatch(r"0\d+", s_str):
            return "\u200b" + s_str  # U+200B zero width space
        return s_str

    # helpers
    def get_address_component(p, key, default=""):
        """
        SERP APIの 'parsed_address' からコンポーネントを取得
        'parsed_address' がない場合は 'address' から正規表現で試みる
        """
        if "parsed_address" in p and isinstance(p["parsed_address"], dict):
            return p["parsed_address"].get(key, default)
        return default

    def extract_postal_code_and_prefecture(p, full_address):
        """
        郵便番号と都道府県を抽出する
        """
        if "parsed_address" in p and isinstance(p["parsed_address"], dict):
            pa = p["parsed_address"]
            postal = pa.get("postal_code", "")
            prefecture = pa.get("state", "")
            if postal or prefecture:
                return postal, prefecture

        # 'parsed_address' がない場合のフォールバック
        postal_match = re.search(r"〒(\d{3}-\d{4})", full_address)
        postal = postal_match.group(1) if postal_match else ""
        
        # 郵便番号を除去した後の文字列で都道府県を検索
        address_no_postal = full_address.replace(f"〒{postal}", "").strip()
        prefecture_match = re.search(r"^(.{2,4}(?:都|道|府|県))", address_no_postal)
        prefecture = prefecture_match.group(1) if prefecture_match else ""
        
        return postal, prefecture

    def parse_address_string(full_address, postal_code, prefecture):
        """
        'parsed_address' がない場合に、'address' 文字列から市区町村とそれ以降を分割
        """
        if not full_address:
            return "", ""
        
        # 郵便番号と都道府県を除去
        address_text = full_address.replace(f"〒{postal_code}", "").strip()
        if prefecture and address_text.startswith(prefecture):
            address_text = address_text[len(prefecture):].strip()

        # 市区町村レベルの正規表現
        # (例: 札幌市中央区, 郡上市, 蒲生郡竜王町, 北松浦郡佐々町)
        match = re.match(r"^([^市区町村]+(?:市|区|郡|町|村))(.*)", address_text)
        
        if match:
            city_town = match.group(1).strip()
            street_address = match.group(2).strip()
            
            # 郡の場合、町や村まで含める (例: 北松浦郡佐々町)
            if city_town.endswith('郡'):
                 # 続く文字列（street_address）から町・村を検索
                 match_gun = re.match(r"^([^町]+[町]|[^村]+[村])(.*)", street_address)
                 if match_gun:
                     city_town = f"{city_town}{match_gun.group(1).strip()}"
                     street_address = match_gun.group(2).strip()

            return city_town, street_address
        else:
            # マッチしない場合は、最初のスペースで分割を試みる
            parts = address_text.split(' ', 1)
            if len(parts) == 2:
                return parts[0], parts[1]
            else:
                return "", address_text # 分割失敗

    # ▼▼▼ collect_places 関数: organic キーから施設情報を直接取得 ▼▼▼
    def collect_places(parsed_response, out):
        """
        新しいスクレイパーAPIのレスポンスから施設情報を取得する。
        parsed_response: パース済みのJSON（辞書またはリスト）
        out: 施設情報を格納するリスト
        """
        if isinstance(parsed_response, list):
            # レスポンスが直接施設リストの場合
            for place in parsed_response:
                if isinstance(place, dict) and place not in out:
                    out.append(place)
        elif isinstance(parsed_response, dict):
            # organic キーから施設リストを取得（旧形式との互換性）
            if 'organic' in parsed_response:
                organic = parsed_response.get('organic', [])
                if isinstance(organic, list):
                    for place in organic:
                        if isinstance(place, dict) and place not in out:
                            out.append(place)
            # results キーから施設リストを取得
            elif 'results' in parsed_response:
                results = parsed_response.get('results', [])
                if isinstance(results, list):
                    for place in results:
                        if isinstance(place, dict) and place not in out:
                            out.append(place)
            # レスポンス自体が単一施設の場合
            elif 'title' in parsed_response or 'name' in parsed_response:
                if parsed_response not in out:
                    out.append(parsed_response)
    # ▲▲▲ collect_places 関数 ▲▲▲

    # -----------------------------------------------------------------------------
    # search_places 関数 (★ /request + google.com/maps/search/ + format: "json")
    # -----------------------------------------------------------------------------
    def search_places(api_token, zone_name, query, log_dir, max_requests=1):
        """
        BrightData APIを使用してGoogle Maps検索を実行
        
        USE_NEW_API = True: Google Maps full information scraper (hl_40597452)
        USE_NEW_API = False: Web Unlocker API (旧形式)
        
        環境変数 USE_NEW_API で切り替え可能 (デフォルト: True)
        max_requests: 1つの検索あたりの最大リクエスト数（ページ数）
        """
        # API形式の選択（環境変数またはデフォルト）
        # 注: 新API (hl_40597452) が利用可能になるまで旧APIをデフォルトに設定
        USE_NEW_API = os.environ.get('USE_NEW_API', 'false').lower() in ('true', '1', 'yes')
        
        if USE_NEW_API:
            logging.info("新しいBrightData Scraper API (hl_40597452) を使用")
            scraper_id = "hl_40597452"
            api_url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={scraper_id}"
        else:
            logging.info("旧BrightData Web Unlocker API を使用")
            api_url = "https://api.brightdata.com/request"

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        
        # ★ JSON応答（dict）をそのまま格納するリストに変更
        all_json_responses = []
        total_requests = 0
        
        # max_requests回のリクエストで最大20件×max_requests件取得
        for i in range(max_requests):
            start = i * 20
            
            # API形式に応じてペイロードを構築
            if USE_NEW_API:
                # 新しいスクレイパーAPI用のペイロード
                payload = [{
                    "query": query,
                    "start": start,
                    "num": 20,
                    "language": "ja",
                    "country": "jp"
                }]
            else:
                # 旧Web Unlocker API用のペイロード
                quoted_query = quote(query)
                search_url = f"https://www.google.com/maps/search/{quoted_query}/?hl=ja&gl=jp&start={start}&brd_json=1"
                payload = {
                    "zone": zone_name,
                    "url": search_url,
                    "format": "json"
                }
            
            total_requests += 1
            max_retries = 5
            page_success = False
            response_was_empty = False # 空の応答だったかどうかのフラグ
            
            for attempt in range(1, max_retries + 1):
                try:
                    # タイムアウトを 120秒 に延長 (Connect=10s, Read=120s)
                    resp = requests.post(api_url, headers=headers, json=payload, timeout=(10, 120))

                    log_preview = "(Empty Response)"
                    if resp.text:
                        log_preview = resp.text.replace('\n', ' ')
                        if len(log_preview) > 500: 
                            log_preview = log_preview[:500] + "..."
                    
                    # 応答のプレビューをコンソールに出力
                    log_message = f"API応答受信 (Query: {query}, start={start}, Status: {resp.status_code}): {log_preview}"
                    logging.debug(log_message)
                    print(f"DEBUG: {log_message}") # ★ コンソール表示を有効化

                    if resp.status_code == 200:
                        
                        if not resp.text or resp.text.strip() == "":
                            logging.warning(f"空の応答 (クエリ: {query}, start={start})。このページの結果はありません。")
                            print(f"WARNING: 空の応答 (クエリ: {query}, start={start})。")
                            page_success = True
                            response_was_empty = True 
                            break 
                        
                        try:
                            response_data = resp.json()
                            parsed_body = None
                            
                            # 新しいAPI: snapshot_id方式
                            if USE_NEW_API and isinstance(response_data, dict) and 'snapshot_id' in response_data:
                                snapshot_id = response_data['snapshot_id']
                                logging.info(f"スナップショットID取得: {snapshot_id}. データ取得を待機中...")
                                print(f"DEBUG: スナップショットID: {snapshot_id}. データ取得を待機中...")
                                
                                # スナップショット結果を取得（最大60秒待機）
                                snapshot_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json"
                                for wait_attempt in range(12):  # 5秒x12回 = 60秒
                                    time.sleep(5)
                                    snapshot_resp = requests.get(snapshot_url, headers=headers, timeout=(10, 120))
                                    if snapshot_resp.status_code == 200:
                                        snapshot_data = snapshot_resp.json()
                                        if isinstance(snapshot_data, list) and len(snapshot_data) > 0:
                                            parsed_body = snapshot_data[0] if len(snapshot_data) == 1 else snapshot_data
                                            break
                                    elif snapshot_resp.status_code == 202:
                                        # まだ処理中
                                        continue
                                    else:
                                        logging.error(f"スナップショット取得失敗: {snapshot_resp.status_code}")
                                        break
                                else:
                                    logging.error(f"スナップショット取得タイムアウト: {snapshot_id}")
                                    print(f"ERROR: スナップショット取得タイムアウト: {snapshot_id}")
                                    break
                            # 旧API: wrapper形式のレスポンス処理
                            elif not USE_NEW_API and isinstance(response_data, dict) and 'body' in response_data:
                                body = response_data.get('body', '')
                                if isinstance(body, str):
                                    # Google安全プレフィックスを削除
                                    if body.startswith(")]}'" ):
                                        body = body[4:].lstrip()
                                    parsed_body = json.loads(body)
                                else:
                                    parsed_body = body
                            else:
                                # 直接データが返された場合
                                parsed_body = response_data
                            
                            # 全体のレスポンスを保存
                            if parsed_body:
                                all_json_responses.append(parsed_body)
                            
                            # organic キーから施設情報を取得
                            places_count = 0
                            if isinstance(parsed_body, dict) and 'organic' in parsed_body:
                                organic = parsed_body.get('organic', [])
                                if isinstance(organic, list):
                                    places_count = len(organic)
                            elif isinstance(parsed_body, list):
                                # レスポンスがリスト形式の場合
                                places_count = len(parsed_body)
                            
                            if places_count > 0:
                                print(f"DEBUG: start={start} で {places_count} 件の施設を発見。")
                            else:
                                print(f"DEBUG: start={start} でJSONは受信しましたが、施設データが見つかりませんでした。")
                                response_was_empty = True
                            
                            page_success = True
                            break 
                        except requests.exceptions.JSONDecodeError as e:
                            logging.error(f"JSONパース失敗 (クエリ: {query}, start={start}): {e}. 応答全文: {resp.text}")
                            print(f"ERROR: JSONパース失敗 (クエリ: {query}, start={start}): {e}")
                            break 
                    
                    else:
                        logging.warning(f"APIリクエスト失敗 (試行 {attempt}/{max_retries}) クエリ: {query}, start={start}, ステータス: {resp.status_code}, 応答全文: {resp.text}")
                        print(f"WARNING: APIリクエスト失敗 (試行 {attempt}/{max_retries}) クエリ: {query}, start={start}, ステータス: {resp.status_code}")
                        if resp.status_code in [401, 403]:
                            logging.error(f"認証エラー (401/403)。APIトークンまたはゾーン名 '{zone_name}' を確認してください。")
                            print(f"ERROR: 認証エラー。APIトークンまたはゾーン名 '{zone_name}' を確認してください。")
                            break # 認証エラーはリトライ不要

                except requests.exceptions.RequestException as e:
                    # タイムアウトの場合もここでキャッチされる
                    logging.warning(f"リクエスト例外 (試行 {attempt}/{max_retries}) クエリ: {query}, start={start}: {e}")
                    print(f"WARNING: リクエスト例外 (試行 {attempt}/{max_retries}) クエリ: {query}, start={start}: {e}")

                delay = 2 ** attempt + random.uniform(0, 1)
                time.sleep(delay)
            
            if not page_success:
                logging.error(f"ページ取得失敗 (リトライ上限超過) クエリ: {query}, start={start}")
                print(f"ERROR: ページ取得失敗 (リトライ上限超過) クエリ: {query}, start={start}")
            
            # 空の応答だった場合、またはページ取得に失敗した場合は、次のページ(start=20など)に進まずループを抜ける
            if response_was_empty or not page_success:
                if response_was_empty and start > 0: # start=0 以外の場合のみ表示
                    print(f"DEBUG: start={start} でこれ以上データがないため、このクエリのページネーションを終了します。")
                if not page_success:
                    print(f"DEBUG: start={start} でページ取得に失敗したため、このクエリのページネーションを終了します。")
                break 

        # ★ all_json_responses (JSON[dict]のリスト) を返す
        return all_json_responses, total_requests


    # ログ設定
    log_dir = os.path.join(results_dir, 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file_path = os.path.join(log_dir, "app.log")
    
    # 既存のハンドラーをクリア（複数回実行時の重複を防止）
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # ログファイルを初期化（上書きモード）
    logging.basicConfig(filename=log_file_path, filemode='w', level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(message)s',
                        encoding='utf-8')

    # 除外GIDの読み込み
    exclude_gids = set()
    if exclude_gids_path and os.path.exists(exclude_gids_path):
        try:
            with open(exclude_gids_path, newline="", encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row:
                        exclude_gids.add(row[0])
            logging.info(f"除外GID読み込み: {len(exclude_gids)} 件")
            print(f"除外GID読み込み: {len(exclude_gids)} 件")
        except Exception as e:
            logging.error(f"除外GID読み込み失敗: {e}")
            print(f"エラー: 除外GID読み込み失敗: {e}")
    else:
        logging.warning(f"除外GIDファイルが見つからないか、指定されていません: {exclude_gids_path}")
        print(f"警告: 除外GIDファイルが見つからないか、指定されていません: {exclude_gids_path}")


    # 住所リストの読み込み
    adress_list = []
    if os.path.exists(file_path):
        with open(file_path, newline="", encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                next(reader) # ヘッダー行を読み飛ばす
            except StopIteration:
                pass # ファイルが空の場合は何もしない
            
            for row in reader:
                joined_string = ' '.join(row)
                adress_list.append(joined_string)
    
    if not adress_list:
        logging.error(f"{file_path} に1行以上のデータ行（ヘッダー除く）が必要です")
        print(f"警告: {file_path} に処理対象の住所データが見つかりません。")

    # 既存施設ファイルの読み込みとヘッダー書き込み
    existing_gids = set()
    gid_to_id_map = {}
    last_facility_id = 101
    
    print(f"DEBUG: 既存施設ファイル読み込み開始: {facility_file}")

    if os.path.exists(facility_file) and os.path.getsize(facility_file) > 0:
        try:
            # utf-8-sig を使用してBOM付きファイルにも対応
            with open(facility_file, newline="", encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                has_business_status = '営業ステータス' in fieldnames if fieldnames else False
                
                if not has_business_status:
                    print('⚠️  既存施設ファイルに営業ステータス列がありません。空列として扱います。')
                
                max_id = 0
                row_count = 0
                for r in reader:
                    row_count += 1
                    if not has_business_status:
                        r['営業ステータス'] = ''
                    
                    gid = r.get('施設GID') or ""
                    try:
                        fid_str = r.get('施設ID')
                        if fid_str:
                            fid = int(fid_str)
                        else:
                            fid = None
                            
                        if fid is not None:
                           if fid > max_id:
                               max_id = fid
                    except Exception:
                        fid = None
                    if gid:
                        existing_gids.add(gid)
                        if fid is not None:
                            gid_to_id_map[gid] = fid
            
            if max_id > 0:
                last_facility_id = max_id + 1
                print(f"DEBUG: 既存施設ファイル読み込み完了。行数: {row_count}, 最大ID: {max_id}, 次のID: {last_facility_id}")
            else:
                print(f"DEBUG: 既存施設ファイル読み込み完了。有効なIDが見つかりませんでした。次のID: {last_facility_id}")
        except Exception as e:
            logging.error(f"既存施設ファイル読み込み失敗: {e}")
            print(f"ERROR: 既存施設ファイル読み込み失敗: {e}")
            # エラー時は安全のため終了する（ID重複を防ぐため）
            if 'max_id' in locals() and max_id > 0:
                 last_facility_id = max_id + 1
                 print(f"WARNING: 読み込み中にエラーが発生しましたが、取得できた最大ID {max_id} を使用して続行します。")
            else:
                 print(f"CRITICAL ERROR: IDの取得に失敗しました。データの整合性を保つため処理を中断します。")
                 raise SystemExit(1)
    else:
        print(f"DEBUG: 既存施設ファイルが存在しないか空です: {facility_file}。新規作成します。")
        # ファイルが存在しないか空の場合、ヘッダーを書き込む
        try:
            with open(facility_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['施設ID', '施設名', '電話番号', '郵便番号', '都道府県', '市区町村', '住所', 'web',
                                'GoogleMap', 'ランク', 'カテゴリ', '緯度', '経度', '施設GID', '営業ステータス'])
        except Exception as e:
            logging.error(f"新規施設ファイルヘッダー書き込み失敗: {e}")
            raise SystemExit(1)

    # 並列処理用のロック
    progress_lock = threading.Lock()
    csv_lock = threading.Lock()
    update_csv_lock = threading.Lock()
    seen_gids_lock = threading.Lock()
    fid_csv_lock = threading.Lock()

    update_rows = []
    request_log = []
    fid_rows = []  # FID情報を格納
    duplicate_analysis_rows = []  # 重複分析用：全取得データ（重複含む）
    total_requests_agg = 0
    total = len(adress_list)
    completed = 0
    start_time = time.time()
    last_id_holder = {'val': last_facility_id}

    # --- 途中保存用の初期化 ---
    # update_facility_path の初期化（上書きモードでヘッダー作成）
    if update_facility_path:
        try:
            with open(update_facility_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['施設ID', '施設名', '電話番号', '郵便番号', '都道府県', '市区町村', '住所', 'web',
                                'GoogleMap', 'ランク', 'カテゴリ', '緯度', '経度', '施設GID', '営業ステータス'])
        except Exception as e:
            logging.error(f"増分ファイル初期化失敗: {e}")

    # duplicate_analysis_path の初期化（上書きモードでヘッダー作成）
    if duplicate_analysis_path:
        try:
            with open(duplicate_analysis_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['施設ID', '施設名', '電話番号', '郵便番号', '都道府県', '市区町村', '住所', 'web',
                                 'GoogleMap', 'ランク', 'カテゴリ', '緯度', '経度', '施設GID', '営業ステータス', '検索クエリ', 'ステータス'])
        except Exception as e:
            logging.error(f"重複分析ファイル初期化失敗: {e}")

    unsaved_rows = []
    unsaved_fid_rows = []
    unsaved_duplicate_rows = []
    BATCH_SIZE = 50

    def save_batch():
        nonlocal unsaved_rows, unsaved_fid_rows, unsaved_duplicate_rows
        if not unsaved_rows and not unsaved_fid_rows and not unsaved_duplicate_rows:
            return

        # 1. 施設データの重複排除とID付与
        batch_deduped_rows = []
        with seen_gids_lock:
            for r_list in unsaved_rows:
                if isinstance(r_list, tuple):
                    r_list = r_list[0]
                
                gid = r_list[13]
                if gid not in existing_gids:
                    if gid in gid_to_id_map:
                        r_list[0] = gid_to_id_map[gid]
                    else:
                        r_list[0] = last_id_holder['val']
                        gid_to_id_map[gid] = last_id_holder['val']
                        last_id_holder['val'] += 1
                    
                    batch_deduped_rows.append(r_list)
                    existing_gids.add(gid)
        
        # 2. facility_file への追記
        if batch_deduped_rows:
            try:
                with open(facility_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    for r in batch_deduped_rows:
                        writer.writerow(r)
            except Exception as e:
                logging.error(f"途中保存失敗 (facility_file): {e}")

            # 3. update_facility_path への追記
            if update_facility_path:
                try:
                    with open(update_facility_path, 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        for r in batch_deduped_rows:
                            writer.writerow(r)
                except Exception as e:
                    logging.error(f"途中保存失敗 (update_facility_path): {e}")

        # 4. FIDデータの保存
        if fid_file_path and unsaved_fid_rows:
            batch_fid_rows = []
            for fid_row in unsaved_fid_rows:
                gid = fid_row[1]
                if gid in gid_to_id_map:
                    fid_row[0] = gid_to_id_map[gid]
                else:
                    fid_row[0] = 0
                batch_fid_rows.append(fid_row)
            
            try:
                file_exists = os.path.exists(fid_file_path) and os.path.getsize(fid_file_path) > 0
                mode = 'a' if file_exists else 'w'
                with open(fid_file_path, mode, newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(['施設ID', '施設GID', '施設FID'])
                    for r in batch_fid_rows:
                        writer.writerow(r)
            except Exception as e:
                logging.error(f"途中保存失敗 (fid_file): {e}")

        # 5. 重複分析データの保存
        if duplicate_analysis_path and unsaved_duplicate_rows:
            try:
                with open(duplicate_analysis_path, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    for r in unsaved_duplicate_rows:
                        writer.writerow(r)
            except Exception as e:
                logging.error(f"途中保存失敗 (duplicate_analysis_path): {e}")

        if batch_deduped_rows:
            print(f"💾 途中保存: {len(batch_deduped_rows)} 件の新規施設データを保存しました。")
        
        # リセット
        unsaved_rows = []
        unsaved_fid_rows = []
        unsaved_duplicate_rows = []

    def process_address(addr, zone_name_for_thread):
        """
        単一の住所クエリを処理し、施設情報とレビュー情報を収集する
        """
        
        local_rows = []
        local_fid_rows = []  # FID情報を格納

        if 'a b' in addr:
            return local_rows, local_fid_rows, 0 # リクエスト数は0

        # ★ /request エンドポイントは クエリ全体を渡す
        search_query = f"{addr} {base_query}".strip()
        logging.info(f"開始: {search_query}")
        
        # MAX_REQUESTS 環境変数から最大リクエスト数を取得
        max_requests_per_query = int(os.environ.get('MAX_REQUESTS', '1'))
        
        # ★ json_responses は [dict, dict, ...] (ページごとのJSON応答のリスト)
        json_responses, query_request_count = search_places(
            api_token=api_token, 
            zone_name=zone_name_for_thread, 
            query=search_query, # "鳥取県 鳥取市 歯医者"
            log_dir=log_dir, # ★ log_dir を渡す
            max_requests=max_requests_per_query # ★ 最大リクエスト数を渡す
        ) 

        # ▼▼▼ 施設を抽出 ▼▼▼
        places = []
        if json_responses:
            for parsed_json in json_responses:
                collect_places(parsed_json, places)
        # ▲▲▲ 施設を抽出 ▲▲▲

        for p in places:
            if not p or not isinstance(p, dict):
                continue
            
            # --- ▼▼▼ GID取得ロジック (map_id_encoded 優先) ▼▼▼ ---
            facility_gid = (
                p.get("map_id_encoded") or # ★ ユーザー指定 (最優先)
                p.get("fid") or        
                p.get("map_id") or     
                p.get("data_id") or    
                p.get("cid") or        
                p.get("data_cid") or   
                p.get("place_id") or   
                p.get("feature_id") or 
                ""
            )
            # FID取得 (fid.csv用)
            facility_fid = p.get("fid") or ""
            # --- ▲▲▲ GID取得ロジック ▲▲▲ ---
            
            if not facility_gid:
                # GIDがないエントリはスキップ
                logging.warning(f"GID (map_id_encoded 等) が見つかりません (Query: {search_query}, Title: {p.get('title')})。この施設をスキップします。")
                continue
            
            gid = str(facility_gid) # GIDは数値の場合もあるため文字列に統一
            
            # ★ FID情報は常に記録（除外や重複に関係なく）
            if facility_fid:
                local_fid_rows.append([0, str(gid), str(facility_fid)])  # 施設IDは後で設定

            if gid in exclude_gids:
                continue
            
            with seen_gids_lock:
                if gid in existing_gids:
                    continue
                # local_rowsはタプル(row, duplicate_row)なので、最初の要素からGIDを取得
                if gid in (row_tuple[0][13] if isinstance(row_tuple, tuple) else row_tuple[13] for row_tuple in local_rows):
                    continue
                # この時点で、このGIDは新規として処理する
                # （ただし、existing_gids への追加はファイル書き込み後）

            facility_name = p.get("title") or p.get("name") or ""
            facility_tell_raw = p.get("phone") or p.get("telephone") or p.get("formatted_phone_number") or ""
            
            # 電話番号をフォーマット（数字のみ抽出して-を挿入）
            if facility_tell_raw:
                # 数字のみ抽出
                digits = re.sub(r'\D', '', facility_tell_raw)
                # 日本の電話番号形式に変換
                if len(digits) == 10:
                    # 市外局番3桁-市内局番3桁-加入者番号4桁 (例: 03-1234-5678)
                    facility_tell = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
                elif len(digits) == 11:
                    # 携帯電話または市外局番4桁 (例: 090-1234-5678 または 0120-123-456)
                    if digits.startswith(('070', '080', '090')):
                        facility_tell = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
                    else:
                        facility_tell = f"{digits[:4]}-{digits[4:7]}-{digits[7:]}"
                else:
                    # その他の形式はそのまま
                    facility_tell = facility_tell_raw
            else:
                facility_tell = ""
            
            facility_web = p.get("website") or p.get("link") or ""
            facility_gmap = p.get("google_maps_url") or p.get("map_link") or ""
            
            facility_rank = p.get("rating") or p.get("avg_rating") or ""
            
            facility_cat = p.get("type") or p.get("category") or p.get("category_list") or ""
            
            if isinstance(facility_cat, list):
                # category が [{'id': 'dental_clinic', 'title': '歯科医院'}] のようなリストの場合
                cat_titles = [c.get("title", "") if isinstance(c, dict) else str(c) for c in facility_cat]
                facility_cat = ";".join(filter(None, cat_titles)) # 空のタイトルを除外
            elif isinstance(facility_cat, dict):
                facility_cat = facility_cat.get("title", "")
            
            # 緯度・経度の取得をネストされた 'location' にも対応
            facility_lati = ""
            facility_long = ""
            if "location" in p and isinstance(p["location"], dict):
                facility_lati = p["location"].get("latitude", "")
                facility_long = p["location"].get("longitude", "")
            
            if not facility_lati:
                facility_lati = p.get("latitude") or p.get("lat") or ""
            if not facility_long:
                facility_long = p.get("longitude") or p.get("lng") or ""
            
            full_addr = p.get("address") or p.get("vicinity") or ""
            
            if not full_addr:
                 # 住所がない場合、元のクエリ（例：鳥取県 鳥取市）を暫定的に入れる
                 full_addr = addr

            facility_post, facility_pref = extract_postal_code_and_prefecture(p, full_addr)
            facility_city, facility_address = parse_address_string(full_addr, facility_post, facility_pref)

            facility_tell = preserve_leading_zero_text(facility_tell)
            facility_post = preserve_leading_zero_text(facility_post)
            
            # 営業ステータスの取得
            business_status = p.get("business_status") or ""
            if not business_status and "permanently_closed" in p:
                business_status = "閉業" if p.get("permanently_closed") else "営業中"
            elif not business_status:
                # opening_hoursから推測
                opening_hours = p.get("opening_hours", {})
                if isinstance(opening_hours, dict):
                    open_now = opening_hours.get("open_now")
                    if open_now is not None:
                        business_status = "営業中" if open_now else ""
            
            # business_statusの値を日本語に変換
            status_map = {
                "OPERATIONAL": "営業中",
                "CLOSED_TEMPORARILY": "一時休業",
                "CLOSED_PERMANENTLY": "閉業"
            }
            facility_status = status_map.get(business_status, business_status)
            
            row = [
                0,  # 施設ID (後で設定)
                str(facility_name), str(facility_tell), str(facility_post),
                str(facility_pref), str(facility_city), str(facility_address),
                str(facility_web), str(facility_gmap),
                str(facility_rank), str(facility_cat),
                str(facility_lati), str(facility_long), str(gid),
                str(facility_status)
            ]
            
            # 重複分析用：重複チェック前に全データを記録
            duplicate_row = row.copy()
            duplicate_row.append(addr)  # 検索クエリ（住所）を追加
            duplicate_row.append('除外GID' if gid in exclude_gids else ('既存' if gid in existing_gids else '新規'))
            local_rows.append((row, duplicate_row))
        
        return local_rows, local_fid_rows, query_request_count

    # 並列実行
    progress_path = os.path.join(results_dir, 'progress.txt')
    cpu = os.cpu_count() or 2
    IO_MULTIPLIER = int(os.environ.get("IO_MULTIPLIER", "3"))
    MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "10"))
    calc = max(1, cpu * IO_MULTIPLIER)
    
    if total == 0:
        workers = 1
    else:
        workers = min(MAX_WORKERS, calc, total)
    
    if workers == 1:
        print(f"並列処理を無効化 (MAX_WORKERS={workers})")
        all_rows = []
        if total == 0:
             print("処理対象の住所が0件のため、タスクをスキップします。")
        
        # adress_list を逆順で処理（テスト用）
        # for addr in reversed(adress_list):
        for addr in adress_list:
            # end end があったら処理を終了
            if 'end end' in addr:
                print(f"'end end' を検出したため、処理を終了します。")
                break
            
            try:
                local_rows, local_fid_rows, req_count = process_address(addr, zone_name)
                
                # process_address が返した local_rows を使って all_rows を更新
                for row_tuple in local_rows:
                    if isinstance(row_tuple, tuple):
                        all_rows.append(row_tuple[0])
                        duplicate_analysis_rows.append(row_tuple[1])
                        # 途中保存用
                        unsaved_rows.append(row_tuple[0])
                        unsaved_duplicate_rows.append(row_tuple[1])
                    else:
                        all_rows.append(row_tuple)
                        unsaved_rows.append(row_tuple)
                fid_rows.extend(local_fid_rows)
                unsaved_fid_rows.extend(local_fid_rows) # 途中保存用
                
                with progress_lock:
                    completed += 1
                    total_requests_agg += req_count
                    # request_log には、CSVに追加される件数 (len(local_rows)) を記録
                    request_log.append({'address': addr, 'requests': req_count, 'found': len(local_rows)})
                
                # 途中保存チェック
                if completed % BATCH_SIZE == 0:
                    save_batch()
                
                elapsed = time.time() - start_time
                if completed > 0:
                    eta = (elapsed / completed) * (total - completed)
                    # コンソール出力も、CSVに追加される件数 (len(local_rows)) を表示
                    print(f"[{completed}/{total}] {addr} (+{len(local_rows)} found / {req_count} req) elapsed={elapsed:.1f}s eta={eta:.1f}s")
                else:
                    print(f"[{completed}/{total}] {addr} (+{len(local_rows)} found / {req_count} req) elapsed={elapsed:.1f}s")

            except Exception as e:
                logging.error(f"エラー (クエリ: {addr} {base_query}): {e}", exc_info=True)
                print(f"[{completed}/{total}] {addr} ERROR ({e})")
                completed += 1 # エラーでもカウントを進める
            
            with open(progress_path, "w", encoding="utf-8") as pf:
                pf.write(f"total: {total}\n")
                pf.write(f"completed: {completed}\n")
    
    else:
        # このコードパスは MAX_WORKERS > 1 の場合にのみ実行される
        print(f"並列処理を開始 (MAX_WORKERS={workers})")
        all_rows = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process_address, addr, zone_name): addr for addr in adress_list}
            
            for future in as_completed(futures):
                addr = futures[future]
                try:
                    local_rows, local_fid_rows, req_count = future.result()
                    for row_tuple in local_rows:
                        if isinstance(row_tuple, tuple):
                            all_rows.append(row_tuple[0])
                            duplicate_analysis_rows.append(row_tuple[1])
                            # 途中保存用
                            unsaved_rows.append(row_tuple[0])
                            unsaved_duplicate_rows.append(row_tuple[1])
                        else:
                            all_rows.append(row_tuple)
                            unsaved_rows.append(row_tuple)
                    fid_rows.extend(local_fid_rows)
                    unsaved_fid_rows.extend(local_fid_rows) # 途中保存用
                    
                    with progress_lock:
                        completed += 1
                        total_requests_agg += req_count
                        request_log.append({'address': addr, 'requests': req_count, 'found': len(local_rows)})
                    
                    # 途中保存チェック
                    if completed % BATCH_SIZE == 0:
                        save_batch()

                except Exception as e:
                    logging.error(f"エラー (クエリ: {addr} {base_query}): {e}", exc_info=True)
                    print(f"[{completed}/{total}] {addr} ERROR ({e})")
                    completed += 1 # エラーでもカウントを進める
                    local_rows = [] # エラー時は空リストを設定
                    req_count = 0   # エラー時はリクエスト数0を設定
                
                elapsed = time.time() - start_time
                if completed > 0:
                    eta = (elapsed / completed) * (total - completed)
                    print(f"[{completed}/{total}] {addr} (+{len(local_rows)} found / {req_count} req) elapsed={elapsed:.1f}s eta={eta:.1f}s")
                else:
                     print(f"[{completed}/{total}] {addr} (+{len(local_rows)} found / {req_count} req) elapsed={elapsed:.1f}s")
                
                with open(progress_path, "w", encoding="utf-8") as pf:
                    pf.write(f"total: {total}\n")
                    pf.write(f"completed: {completed}\n")
    
    #
    # facility_file: write new facilities
    #
    
    # 残りのデータを保存
    save_batch()

    # 以下の既存書き込み処理は途中保存で完了しているためスキップ（統計情報のみ出力）
    
    # deduped_rows = []
    # all_fid_rows = []
    # with seen_gids_lock:
    #     for r_list in all_rows:
    #         # r_listがタプルの場合は最初の要素（row）を使用
    #         if isinstance(r_list, tuple):
    #             r_list = r_list[0]
    #         
    #         gid = r_list[13] # GIDは14番目（インデックス13）
    #         if gid not in existing_gids:
    #             if gid in gid_to_id_map: # 既にこの実行バッチでIDが割り当てられているか？
    #                 r_list[0] = gid_to_id_map[gid]
    #             else:
    #                 r_list[0] = last_id_holder['val'] # 新しいIDを割り当て
    #                 gid_to_id_map[gid] = last_id_holder['val']
    #                 last_id_holder['val'] += 1
    #             
    #             deduped_rows.append(r_list)
    #             existing_gids.add(gid) # メインの existing_gids セットにも追加
    #     
    #     # FID行にIDを割り当て（全施設、除外・重複含む）
    #     for fid_row in fid_rows:
    #         gid = fid_row[1]
    #         # 既存のマッピングを確認
    #         if gid in gid_to_id_map:
    #             fid_row[0] = gid_to_id_map[gid]
    #         else:
    #             # 既存ファイルから施設IDを取得（existing_gidsに含まれている場合）
    #             # 新しいIDは割り当てず、0のまま（後で確認可能）
    #             fid_row[0] = 0
    #         all_fid_rows.append(fid_row)

    #
    # update_facility_path: write updates (増分CSV)
    #
    # if update_facility_path:
    #     try:
    #         with open(update_facility_path, 'w', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
    #             writer.writerow(['施設ID', '施設名', '電話番号', '郵便番号', '都道府県', '市区町村', '住所', 'web',
    #                              'GoogleMap', 'ランク', 'カテゴリ', '緯度', '経度', '施設GID', '営業ステータス'])
    #             for r in deduped_rows:
    #                 writer.writerow(r)
    #         if deduped_rows:
    #             print(f"INFO: 増分ファイル '{update_facility_path}' に {len(deduped_rows)} 件の新規データを書き込みました。")
    #         else:
    #             print(f"INFO: 増分ファイル '{update_facility_path}' を作成しました（新規データ: 0件）。")
    #     except Exception as e:
    #         logging.error(f"増分ファイル書き込み失敗: {e}")
    #         print(f"ERROR: 増分ファイル書き込み失敗: {e}")
    # else:
    #     logging.warning("増分ファイル(update_facility_file)のパスが指定されていません。スキップします。")


    #
    # facility_file: write new facilities (append mode)
    #
    # appended_count = len(deduped_rows)
    
    # if appended_count > 0:
    #     try:
    #         with open(facility_file, 'a', newline='', encoding='utf-8') as f:
    #             # ヘッダーは既に存在するか、空ファイルの場合は書き込み済み
    #             writer = csv.writer(f)
    #             for r_list in deduped_rows:
    #                 writer.writerow(r_list)
    #         
    #         logging.info(f"facility_file に {appended_count} 件の新規データを追記しました。")
    #         print(f"INFO: facility_file に {appended_count} 件の新規データを追記しました。")
    #     except Exception as e:
    #         logging.error(f"facility_file への追記に失敗: {e}")
    #         print(f"ERROR: facility_file への追記に失敗: {e}")
    # else:
    #     logging.info("facility_file への追記データはありません (0件)。")
    #     print("INFO: facility_file への追記データはありません (0件)。")


    # write request_log
    # request_log_path = os.path.join(results_dir, f"request_counts_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    if False:  # request_counts 出力を無効化
        try:
            with open('', 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['address', 'requests', 'found'])
                writer.writeheader()
                for rec in request_log:
                    writer.writerow(rec)
        except Exception as e:
            logging.error(f"リクエストログの書き込み失敗: {e}")
            print(f"ERROR: リクエストログの書き込み失敗: {e}")


    #
    # fid_file_path: write FID mapping (既存データも含めて重複排除)
    #
    # if fid_file_path and all_fid_rows:
    #     try:
    #         # 既存fid.csvのデータを読み込む
    #         existing_fid_rows = []
    #         if os.path.exists(fid_file_path) and os.path.getsize(fid_file_path) > 0:
    #             with open(fid_file_path, 'r', encoding='utf-8') as f:
    #                 reader = csv.reader(f)
    #                 header = next(reader, None)
    #                 for row in reader:
    #                     if len(row) >= 3:
    #                         existing_fid_rows.append(row[:3])
    #         # 新規データと既存データを結合
    #         combined_rows = existing_fid_rows + [row[:3] for row in all_fid_rows]
    #         # 重複排除
    #         seen = set()
    #         unique_fid_rows = []
    #         for row in combined_rows:
    #             key = tuple(row)
    #             if key not in seen:
    #                 seen.add(key)
    #                 unique_fid_rows.append(row)
    #         with open(fid_file_path, 'w', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
    #             writer.writerow(['施設ID', '施設GID', '施設FID'])
    #             for fid_row in unique_fid_rows:
    #                 writer.writerow(fid_row)
    #         logging.info(f"fid_file に {len(unique_fid_rows)} 件の重複なしFIDマッピングを書き込みました（既存＋新規）。")
    #         print(f"INFO: fid_file に {len(unique_fid_rows)} 件の重複なしFIDマッピングを書き込みました（既存＋新規）。")
    #     except Exception as e:
    #         logging.error(f"fid_file への書き込みに失敗: {e}")
    #         print(f"ERROR: fid_file への書き込みに失敗: {e}")

    #
    # duplicate_analysis_path: write all data including duplicates (重複分析用)
    #
    if duplicate_analysis_path and duplicate_analysis_rows:
        # 行データは途中保存済みなので、ここでは統計情報のみ出力
        # try:
        #     with open(duplicate_analysis_path, 'w', newline='', encoding='utf-8') as f:
        #         writer = csv.writer(f)
        #         writer.writerow(['施設ID', '施設名', '電話番号', '郵便番号', '都道府県', '市区町村', '住所', 'web',
        #                          'GoogleMap', 'ランク', 'カテゴリ', '緯度', '経度', '施設GID', '営業ステータス', '検索クエリ', 'ステータス'])
        #         for r in duplicate_analysis_rows:
        #             writer.writerow(r)
            
            # 重複統計を計算
            gid_count = {}
            gid_to_name = {}  # GIDから施設名へのマッピング
            for r in duplicate_analysis_rows:
                gid = r[13]  # 施設GID
                facility_name = r[1]  # 施設名
                if gid in gid_count:
                    gid_count[gid] += 1
                else:
                    gid_count[gid] = 1
                    gid_to_name[gid] = facility_name
            
            duplicates = {gid: count for gid, count in gid_count.items() if count > 1}
            
            # 統計情報をファイルに出力
            stats_path = duplicate_analysis_path.replace('.csv', '_stats.csv')
            try:
                with open(stats_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['統計項目', '値'])
                    writer.writerow(['総取得データ件数（重複含む）', len(duplicate_analysis_rows)])
                    writer.writerow(['ユニーク施設数', len(gid_count)])
                    writer.writerow(['重複施設数', len(duplicates)])
                    # writer.writerow(['新規施設数', appended_count]) # appended_count は計算していない
                    writer.writerow(['既存施設数（再検出）', len([r for r in duplicate_analysis_rows if r[16] == '既存'])])
                    writer.writerow(['除外GID数', len([r for r in duplicate_analysis_rows if r[16] == '除外GID'])])
                    writer.writerow(['総リクエスト数', total_requests_agg])
                    writer.writerow(['処理住所数', total])
                    writer.writerow([])
                    writer.writerow(['重複施設ランキング', ''])
                    writer.writerow(['順位', 'GID', '施設名', '出現回数'])
                    
                    sorted_duplicates = sorted(duplicates.items(), key=lambda x: x[1], reverse=True)
                    for idx, (gid, count) in enumerate(sorted_duplicates, 1):
                        writer.writerow([idx, gid, gid_to_name.get(gid, ''), count])
                
                logging.info(f"統計情報ファイル '{stats_path}' を出力しました。")
                print(f"INFO: 統計情報ファイル '{stats_path}' を出力しました。")
            except Exception as e:
                logging.error(f"統計情報ファイル書き込み失敗: {e}")
                print(f"ERROR: 統計情報ファイル書き込み失敗: {e}")
            
            logging.info(f"重複分析ファイルに {len(duplicate_analysis_rows)} 件のデータを書き込みました（重複含む全データ）。")
            logging.info(f"重複施設数: {len(duplicates)} 件, 総取得データ: {len(duplicate_analysis_rows)} 件")
            print(f"INFO: 重複分析ファイル '{duplicate_analysis_path}' に {len(duplicate_analysis_rows)} 件のデータを書き込みました。")
            print(f"INFO: 重複施設数: {len(duplicates)} 件（同一GIDが複数回取得されたもの）")
            
            if duplicates:
                print(f"\n=== 重複上位10件 ===")
                sorted_duplicates_top10 = sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:10]
                for gid, count in sorted_duplicates_top10:
                    print(f"  {gid_to_name.get(gid, 'Unknown')} (GID: {gid}) - {count}回出現")
        # except Exception as e:
        #     logging.error(f"重複分析ファイル書き込み失敗: {e}")
        #     print(f"ERROR: 重複分析ファイル書き込み失敗: {e}")
    
    logging.info(f"処理完了: リクエスト合計: {total_requests_agg}")
    print(f"Finished update_mini. Total found {len(all_rows)}. Requests: {total_requests_agg}")
    return total_requests_agg


def run_from_config(config_file):
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
    except FileNotFoundError:
        print(f"エラー: 設定ファイル '{config_file}' が見つかりません。")
        return
    except json.JSONDecodeError:
        print(f"エラー: 設定ファイル '{config_file}' の形式が不正です。JSON形式を確認してください。")
        return

    api_token = os.environ.get("BRIGHTDATA_API_TOKEN")
    if not api_token:
        print("エラー: 環境変数 'BRIGHTDATA_API_TOKEN' が設定されていません。")
        print("GitHub Secrets に BRIGHTDATA_API_TOKEN を設定してください。")
        raise SystemExit(1)
    
    # ★ エンドポイントを /request に戻したことを明記
    print("BrightData Web Unlocker (/request エンドポイント, /maps/search/ URL) モードで実行します。")


    for task in tasks:
        task_name = task.get('task_name', 'Unnamed Task')
        base_query = task.get('query', '')
        
        # zone_name を直接取得
        zone_name = task.get('zone_name', 'serp_api2')  # デフォルト値
        print(f"settings.json からゾーン名 '{zone_name}' を読み込みました。")

        # settings.jsonのパスを settings/ ディレクトリ基準に修正
        address_csv_path = task.get('address_csv_path', '')
        # results/ で始まる場合はそのまま使用 (ヒートマップファイルなど)
        if address_csv_path and address_csv_path.startswith('results/'):
            file_path = address_csv_path
        elif address_csv_path and not address_csv_path.startswith('settings/'):
            file_path = os.path.join('settings', address_csv_path)
        else:
            file_path = address_csv_path

        # facility_file のパスを results/ ディレクトリ基準に修正
        facility_csv = task.get('facility_file', '')
        if facility_csv and not facility_csv.startswith('results/'):
            facility_file = os.path.join('results', facility_csv)
        else:
            facility_file = facility_csv

        # update_facility_path のパスを results/ ディレクトリ基準に修正
        update_csv = task.get('update_facility_path', '')
        if update_csv and not update_csv.startswith('results/'):
            update_facility_path = os.path.join('results', update_csv)
        else:
            update_facility_path = update_csv
        
        # exclude_gids_path のパスを settings/ ディレクトリ基準に修正
        exclude_csv = task.get('exclude_gids_path', '')
        if exclude_csv and not exclude_csv.startswith('settings/'):
            exclude_gids_path = os.path.join('settings', exclude_csv)
        else:
            exclude_gids_path = exclude_csv
        
        # fid_file のパスを results/ ディレクトリ基準に修正
        fid_csv = task.get('fid_file', '')
        if fid_csv:
            # 明示的に指定された場合はそれを使用
            if not fid_csv.startswith('results/'):
                fid_file_path = os.path.join('results', fid_csv)
            else:
                fid_file_path = fid_csv
        else:
            # 未指定の場合は facility_file から動的に生成
            facility_basename = os.path.basename(facility_file)
            facility_name = os.path.splitext(facility_basename)[0]
            fid_file_path = os.path.join('results', f'{facility_name}_fid.csv')
        
        # ★ 環境変数からカスタムパラメータを取得（GitHub Actionsワークフローの入力を優先）
        custom_address_csv = os.environ.get('CUSTOM_ADDRESS_CSV')
        custom_output_file = os.environ.get('CUSTOM_OUTPUT_FILE')
        
        # カスタムアドレスファイルが指定されている場合は上書き
        if custom_address_csv and custom_address_csv != 'default':
            file_path = custom_address_csv
            print(f"📍 カスタムアドレスファイルを使用: {file_path}")
        
        # カスタム出力ファイルが指定されている場合は上書き
        if custom_output_file and custom_output_file != 'default':
            # results/ ディレクトリ内のファイル名として扱う
            if not custom_output_file.startswith('results/'):
                facility_file = os.path.join('results', custom_output_file)
            else:
                facility_file = custom_output_file
            print(f"📄 カスタム出力ファイルを使用: {facility_file}")
            
            # facility_fileが変更された場合、fid_file_pathも再計算
            facility_basename = os.path.basename(facility_file)
            facility_name = os.path.splitext(facility_basename)[0]
            fid_file_path = os.path.join('results', f'{facility_name}_fid.csv')
            print(f"🔑 FIDファイルを再計算: {fid_file_path}")
        
        # address_csv_pathのファイル名をそのままduplicate_analysis_pathのファイル名に使う
        address_csv_filename = os.path.basename(str(task.get('address_csv_path', 'address.csv')))
        base_name = os.path.splitext(address_csv_filename)[0]
        duplicate_csv = f'dental_duplicate_analysis_{base_name}.csv'
        if not duplicate_csv.startswith('results/'):
            duplicate_analysis_path = os.path.join('results', duplicate_csv)
        else:
            duplicate_analysis_path = duplicate_csv

        included_type = task.get('includedType', None)

        # results_dir を facility_file から決定
        results_dir = os.path.dirname(facility_file)
        if not results_dir:
            results_dir = "results" # デフォルト
        
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
            
        print(f'設定された検索クエリの業種は{base_query}')
        print(f'設定された検索クエリの住所は{file_path}')
        print(f'設定された施設情報ファイルは{facility_file}')
        print(f'設定された増分施設情報ファイルは{update_facility_path}')
        print(f'設定された除外GIDファイルは{exclude_gids_path}')
        print(f'設定されたFID出力ファイルは{fid_file_path}')
        if duplicate_analysis_path:
            print(f'設定された重複分析ファイルは{duplicate_analysis_path}')

        time.sleep(1)
        print(f"\n--- タスク '{task_name}' の処理を開始 ---")
        
        total_requests = update_mini(
            base_query=base_query,
            api_token=api_token, 
            zone_name=zone_name, # 抽出したゾーン名を渡す
            file_path=file_path,
            facility_file=facility_file,
            update_facility_path=update_facility_path,
            exclude_gids_path=exclude_gids_path,
            results_dir=results_dir,
            fid_file_path=fid_file_path,
            included_type=included_type,
            duplicate_analysis_path=duplicate_analysis_path
        )
        print(f"--- タスク '{task_name}' の処理が完了 ---")
        print(f"総リクエスト数: {total_requests}")

if __name__ == "__main__":
    CONFIG_FILE = os.environ.get('CONFIG_FILE', 'settings/settings.json')
    print(f"🚀 Starting with CONFIG_FILE: {CONFIG_FILE}")
    run_from_config(CONFIG_FILE)
