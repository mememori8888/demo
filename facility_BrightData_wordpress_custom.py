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
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# InsecureRequestWarning を無効にする
urllib3.disable_warnings(InsecureRequestWarning)

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("facility_search_custom.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def git_sync(file_path, message):
    """
    Gitへの同期を行う（Pull -> Add -> Commit -> Push）
    """
    try:
        print(f"🔄 Git同期を開始します: {message}")
        
        # カレントディレクトリからの相対パスを取得
        try:
            rel_path = os.path.relpath(file_path, os.getcwd())
        except ValueError:
            rel_path = file_path

        # Pull (rebase)
        subprocess.run(["git", "pull", "--rebase"], check=False, capture_output=True)
        
        # Add
        subprocess.run(["git", "add", rel_path], check=True, capture_output=True)
        
        # Commit
        subprocess.run(["git", "commit", "-m", message], check=False, capture_output=True)
        
        # Push
        result = subprocess.run(["git", "push"], check=False, capture_output=True)
        
        if result.returncode == 0:
            print("✅ Git同期完了")
        else:
            print(f"⚠️ Git Push失敗: {result.stderr.decode()}")
            
    except Exception as e:
        print(f"⚠️ Git同期エラー: {e}")

def search_places(api_token, zone_name, query, log_dir, max_requests=1):
    """
    BrightData APIを使用してGoogle Maps検索を行い、パース済みのJSONオブジェクトを返す
    """
    url = "https://api.brightdata.com/request"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    all_parsed_json = []
    total_requests = 0
    MAX_RETRIES = 3
    
    # Google Mapsはstartパラメータをサポートしないため、ループは1回のみ
    for start_index in range(max_requests):
        search_url = f"https://www.google.com/maps/search/{quote(query)}/?hl=ja&gl=jp"
        
        payload = {
            "zone": zone_name,
            "url": search_url,
            "format": "json"
        }
        
        success = False
        for attempt in range(MAX_RETRIES):
            try:
                if attempt > 0:
                    logging.info(f"Retrying ({attempt + 1}/{MAX_RETRIES}): {search_url}")
                    time.sleep(random.uniform(2, 5))

                logging.info(f"Requesting: {search_url}")
                response = requests.post(url, headers=headers, json=payload, verify=False, timeout=120)
                total_requests += 1
                
                # ログ保存 (生レスポンス)
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_query = re.sub(r'[\\/*?:"<>|]', '_', query)
                log_file = os.path.join(log_dir, f"resp_{safe_query}_{start_index}_{timestamp}.json")
                
                parsed_data = None
                if response.status_code == 200 and response.text:
                    try:
                        # レスポンス全体を一度JSONとしてパース
                        wrapper_data = response.json()
                        
                        # ログにはラッパーごと保存
                        with open(log_file, 'w', encoding='utf-8') as f:
                            json.dump(wrapper_data, f, ensure_ascii=False, indent=2)

                        # 'body'キーの中身を取得
                        body_content = wrapper_data.get('body')

                        if isinstance(body_content, str):
                            # bodyが文字列の場合、Googleのプレフィックスを削除して再度パース
                            if body_content.startswith(")]}'"):
                                body_content = body_content[4:]
                            
                            # HTML内のJSONを抽出
                            match = re.search(r'window\.APP_INITIALIZATION_STATE\s*=\s*', body_content)
                            if match:
                                start_pos = match.end()
                                # 括弧のバランスをとってJSONを正確に抽出する
                                if start_pos < len(body_content) and body_content[start_pos] == '[':
                                    open_brackets = 0
                                    in_string = False
                                    escape = False
                                    end_pos = -1
                                    
                                    for i in range(start_pos, len(body_content)):
                                        char = body_content[i]
                                        
                                        if escape:
                                            escape = False
                                            continue
                                        
                                        if char == '\\':
                                            escape = True
                                            continue
                                        
                                        if char == '"':
                                            in_string = not in_string
                                        
                                        if not in_string:
                                            if char == '[':
                                                open_brackets += 1
                                            elif char == ']':
                                                open_brackets -= 1
                                        
                                        if open_brackets == 0:
                                            end_pos = i + 1
                                            break
                                    
                                    if end_pos != -1:
                                        json_str = body_content[start_pos:end_pos]
                                        try:
                                            parsed_data = json.loads(json_str)
                                        except json.JSONDecodeError as e:
                                            logging.warning(f"Failed to parse extracted JSON string: {e}. Query: {query}")
                                else:
                                     logging.warning(f"APP_INITIALIZATION_STATE found but not followed by a list. Query: {query}")
                            else:
                                # APP_INITIALIZATION_STATE が見つからない場合、body自体をJSONとしてパース試行
                                try:
                                    parsed_data = json.loads(body_content)
                                except json.JSONDecodeError:
                                    logging.warning(f"Could not find APP_INITIALIZATION_STATE and body is not valid JSON. Query: {query}")

                        elif isinstance(body_content, (dict, list)):
                            # bodyが既にJSONオブジェクトの場合
                            parsed_data = body_content
                        
                        if parsed_data:
                            all_parsed_json.append(parsed_data)
                            success = True
                            break
                        else:
                            logging.warning(f"Could not extract valid JSON from response body. Query: {query}")

                    except (json.JSONDecodeError, KeyError) as e:
                        logging.error(f"Failed to parse JSON response: {e}. Query: {query}. Response text: {response.text[:500]}")
                        
                        # --- デバッグコード追加 ---
                        # パース失敗時にレスポンスボディ全体を保存
                        debug_body_path = os.path.join(log_dir, f"failed_body_{safe_query}_{timestamp}.html")
                        try:
                            # response.json()を試みて、成功すればbodyを、失敗すればtext全体を保存
                            try:
                                wrapper_data_for_debug = response.json()
                                body_content_for_debug = wrapper_data_for_debug.get('body', response.text)
                            except json.JSONDecodeError:
                                body_content_for_debug = response.text

                            with open(debug_body_path, 'w', encoding='utf-8') as f_debug:
                                f_debug.write(body_content_for_debug)
                            logging.info(f"Saved failed response body to {debug_body_path}")
                        except Exception as debug_e:
                            logging.error(f"Failed to save debug body file: {debug_e}")
                        # --- デバッグコード終了 ---

                        # 生のテキストをログに保存
                        with open(log_file.replace('.json', '.txt'), 'w', encoding='utf-8') as f:
                            f.write(response.text)
                else:
                    logging.error(f"API Error: {response.status_code} - {response.text[:500]}. Query: {query}")
                    if response.status_code in [401, 403]: # 認証エラーはリトライしない
                        break
            
            except requests.exceptions.RequestException as e:
                logging.error(f"Request failed: {e}. Query: {query}")
        
        if not success:
            logging.error(f"Failed to get data for query after {MAX_RETRIES} attempts: {query}")
            
        time.sleep(random.uniform(1, 3))
        
    return all_parsed_json, total_requests

def find_value_recursive(data, condition):
    """
    ネストされたデータ構造から、条件に一致する値を再帰的に探す。
    """
    if condition(data):
        return data
    if isinstance(data, dict):
        for key, value in data.items():
            result = find_value_recursive(value, condition)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_value_recursive(item, condition)
            if result is not None:
                return result
    return None

def find_all_values_recursive(data, condition):
    """
    ネストされたデータ構造から、条件に一致するすべての値を再帰的に探してリストで返す。
    """
    results = []
    
    def search(d):
        if condition(d):
            results.append(d)
        
        if isinstance(d, dict):
            for value in d.values():
                search(value)
        elif isinstance(d, list):
            for item in d:
                search(item)
    
    search(data)
    return results

def find_phone_recursive(data):
    """
    電話番号と思われる値を再帰的に探索する。
    日本の電話番号形式（ハイフンあり・なし）に一致するものを探す。
    """
    phone_pattern = re.compile(r"^(0\d{1,4}-\d{1,4}-\d{4}|0\d{9,10})$")
    
    def condition(x):
        return isinstance(x, str) and phone_pattern.match(x)
        
    return find_value_recursive(data, condition)

def find_website_recursive(data):
    """
    ウェブサイトURLと思われる値を再帰的に探索する。
    'http'で始まり'google.com'を含まない文字列を探す。
    """
    def condition(x):
        return isinstance(x, str) and x.startswith('http') and 'google.com' not in x
        
    return find_value_recursive(data, condition)

def find_business_status_recursive(data):
    """
    営業ステータスを示すキーワードを再帰的に探索し、最も優先度の高いものを返す。
    優先度: 閉業 > 休業中 > 営業中
    """
    statuses = []
    
    def search(d):
        if isinstance(d, str):
            # より広範なキーワードマッチング
            lower_d = d.lower()
            if "閉業" in d or "恒久的に閉鎖" in d or "廃業" in d or "permanently closed" in lower_d or "closed" in lower_d:
                statuses.append("閉業")
            elif "休業中" in d or "temporarily closed" in lower_d:
                statuses.append("休業中")
            elif "営業中" in d or "open" in lower_d:
                statuses.append("営業中")
        elif isinstance(d, dict):
            for value in d.values():
                search(value)
        elif isinstance(d, list):
            for item in d:
                search(item)

    search(data)

    if "閉業" in statuses:
        return "閉業"
    if "休業中" in statuses:
        return "休業中"
    if "営業中" in statuses:
        return "営業中"
    return ""

def collect_places(parsed_json, places_list):
    """
    パース済みのJSON全体から、再帰的探索によって施設情報を抽出する。
    """
    if not parsed_json:
        return

    try:
        # より広範囲にplace_idを探索（0xで始まるか、/g/ で始まるURL形式）
        all_place_ids = find_all_values_recursive(parsed_json, 
            lambda x: isinstance(x, str) and (x.startswith('0x') or x.startswith('/g/')))
        
        if not all_place_ids:
            logging.warning("Could not find any place IDs in JSON.")
            return

        seen_gids = {p.get('place_id') for p in places_list}
        
        for gid in all_place_ids:
            if gid in seen_gids:
                continue
            
            seen_gids.add(gid)
            
            # GID周辺のデータ構造を探索
            # find_all_values_recursive を使って、このGIDを含むすべての親構造を取得
            def find_parent_with_gid(data, target_gid):
                """GIDを含む最も近い親リストを見つける"""
                if isinstance(data, list):
                    if target_gid in data:
                        return data
                    for item in data:
                        result = find_parent_with_gid(item, target_gid)
                        if result:
                            return result
                elif isinstance(data, dict):
                    for value in data.values():
                        result = find_parent_with_gid(value, target_gid)
                        if result:
                            return result
                return None
            
            candidate = find_parent_with_gid(parsed_json, gid)
            if not candidate:
                candidate = parsed_json  # フォールバック
            
            # 各情報を再帰的に探索
            # 施設名: 比較的長い文字列で、URLやplace_idではないもの
            all_strings = find_all_values_recursive(candidate, 
                lambda x: isinstance(x, str) and len(x) > 2 and not x.startswith('http') 
                and not x.startswith('0x') and not x.startswith('/g/'))
            name = all_strings[0] if all_strings else ""
            
            # 住所：〒から始まる文字列、または日本語を含む長めの文字列
            address = find_value_recursive(candidate, lambda x: isinstance(x, str) and '〒' in x)
            if not address:
                # フォールバック: 日本語都道府県名を含む文字列
                address = find_value_recursive(candidate, 
                    lambda x: isinstance(x, str) and len(x) > 10 and 
                    any(pref in x for pref in ['北海道', '東京都', '京都府', '大阪府', '県']))
            
            phone = find_phone_recursive(candidate)
            website = find_website_recursive(candidate)
            business_status = find_business_status_recursive(candidate)
            
            # 緯度経度：数値のペアを探す（Google Mapsの座標は通常8桁の整数形式で保存されることも）
            lat = ''
            lng = ''
            # まず浮動小数点数のペアを探す
            coords_list = find_all_values_recursive(candidate, 
                lambda x: isinstance(x, list) and len(x) >= 2 and 
                isinstance(x[0], (int, float)) and isinstance(x[1], (int, float)) and
                30 <= abs(x[0]) <= 50 and 125 <= abs(x[1]) <= 150)  # 日本の座標範囲
            
            if coords_list:
                lat = coords_list[0][0]
                lng = coords_list[0][1]
            else:
                # 整数形式（10^7倍されている）を探す
                int_coords = find_all_values_recursive(candidate,
                    lambda x: isinstance(x, list) and len(x) >= 2 and
                    isinstance(x[0], int) and isinstance(x[1], int) and
                    300000000 <= abs(x[0]) <= 500000000 and 1250000000 <= abs(x[1]) <= 1500000000)
                if int_coords:
                    lat = int_coords[0][0] / 10000000
                    lng = int_coords[0][1] / 10000000

            # カテゴリ: 特定の文字列（歯科、病院など）
            category_keywords = ['歯科', '病院', '医院', 'クリニック', 'dentist', 'clinic', 'hospital']
            all_categories = find_all_values_recursive(candidate,
                lambda x: isinstance(x, str) and any(kw in x.lower() for kw in category_keywords))
            category = all_categories[0] if all_categories else ''

            # 評価: 0-5の範囲の浮動小数点数
            ratings = find_all_values_recursive(candidate,
                lambda x: isinstance(x, (int, float)) and 0 <= x <= 5 and x != 0)
            rating = ratings[0] if ratings else ''

            # Google Maps URL
            if gid.startswith('/g/'):
                google_maps_url = f"https://www.google.com/maps{gid}"
            else:
                google_maps_url = f"https://www.google.com/maps/place/?q=place_id:{gid}"

            # 結果を構築
            place_data = {
                "name": name or "",
                "address": address or "",
                "phone": phone or "",
                "website": website or "",
                "category": category or "",
                "rating": rating,
                "latitude": lat,
                "longitude": lng,
                "place_id": gid,
                "business_status": business_status or "",
                "google_maps_url": google_maps_url
            }
            places_list.append(place_data)

    except Exception as e:
        logging.error(f"JSON parsing/extraction failed: {e}")
        import traceback
        traceback.print_exc()


def process_custom_search():
    """
    'wordpress独自データ.csv' を読み込み、各行のキーワードで検索を実行し、
    結果を 'wordpress_custom_search_results.csv' に保存する。
    """
    # スクリプトのディレクトリを基準にパスを構築
    # exec() で実行されると __file__ が定義されないため、フォールバックを追加
    script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
    log_dir = os.path.join(script_dir, 'logs')
    input_csv_path = os.path.join(script_dir, 'results', 'wordpress独自データ.csv')
    output_csv_path = os.path.join(script_dir, 'results', 'wordpress_custom_search_results.csv')
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    api_token = os.environ.get("BRIGHTDATA_API_TOKEN")
    if not api_token:
        print("エラー: 環境変数 'BRIGHTDATA_API_TOKEN' が設定されていません。")
        return

    # ゾーン名はハードコードまたは環境変数から取得
    zone_name = "serp_api2" 
    
    # 入力データの読み込み
    search_targets = []
    if os.path.exists(input_csv_path):
        # utf-8-sig で読み込む（BOM付き対応）
        with open(input_csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            # ヘッダーがあるか確認（なさそうだが念のため）
            # サンプル: 神奈川県大和市-星野歯科医院,046-267-8550,神奈川県,大和市,渋谷2-24-10-A
            for row in reader:
                if len(row) >= 1:
                    # 検索キーワードを作成
                    # 例: "神奈川県大和市 星野歯科医院" のようにする？
                    # CSVの1列目が "神奈川県大和市-星野歯科医院" となっているので、これをそのまま使うか、
                    # ハイフンをスペースに変えるか。
                    # ここではハイフンをスペースに置換して検索クエリとする
                    original_key = row[0]
                    query = original_key.replace('-', ' ')
                    search_targets.append({'query': query, 'original_row': row})
    else:
        print(f"エラー: 入力ファイル {input_csv_path} が見つかりません。")
        return

    # --- テスト用フィルタリング開始 ---
    # 最初の9件 + 特定のターゲット（沖縄県宮古島市 上野歯科診療所）
    target_keyword = "沖縄県宮古島市 上野歯科診療所"
    test_targets = search_targets[:9]
    
    specific_target = next((t for t in search_targets if t['query'] == target_keyword), None)
    if specific_target:
        # 既に含まれていなければ追加
        if specific_target not in test_targets:
            test_targets.append(specific_target)
    else:
        print(f"警告: テスト対象の '{target_keyword}' が見つかりませんでした。")

    search_targets = test_targets
    print(f"テスト実行モード: {len(search_targets)} 件を処理します。")
    # --- テスト用フィルタリング終了 ---

    print(f"処理対象: {len(search_targets)} 件")
    
    # 出力ファイルの準備
    # 既存のカラム + 検索キーワード + 取得した情報
    header = [
        '検索キーワード', '施設名', '電話番号', '郵便番号', '都道府県', '市区町村', '住所', 
        'web', 'GoogleMap', 'ランク', 'カテゴリ', '緯度', '経度', '施設GID', '営業ステータス',
        '元データ_1', '元データ_2', '元データ_3', '元データ_4', '元データ_5' # 元データの内容も残す
    ]
    
    # 既存ファイルを削除して新規作成（テスト実行のため毎回クリーンな状態から開始）
    if os.path.exists(output_csv_path):
        os.remove(output_csv_path)
    
    with open(output_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
            
    # 並列処理の設定
    # 12000件以上あるため、5時間以内に終わらせるために並列数を増やす
    # 20並列なら、1件5秒としても約1時間で終わる計算
    MAX_WORKERS = 20 
    
    # 定期保存の間隔（件数）
    SAVE_INTERVAL = 100
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for target in search_targets:
            futures.append(executor.submit(process_single_target, target, api_token, zone_name, log_dir))
            
        completed = 0
        total = len(futures)
        
        for future in as_completed(futures):
            results = future.result()
            completed += 1
            
            if results:
                # 結果をCSVに書き込み
                with open(output_csv_path, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    for row in results:
                        writer.writerow(row)
                print(f"[{completed}/{total}] 完了: {results[0][0]} ({len(results)} 件ヒット)")
            else:
                print(f"[{completed}/{total}] 結果なし")
            
            # Git同期を無効化
            # if completed % SAVE_INTERVAL == 0:
            #     git_sync(output_csv_path, f"Update custom search results: {completed}/{total}")

    # Git同期を無効化
    # git_sync(output_csv_path, f"Finish custom search results: {completed}/{total}")

def process_single_target(target, api_token, zone_name, log_dir):
    query = target['query']
    original_row = target['original_row']
    
    # 元データを5列分確保（足りない場合は空文字埋め）
    original_data = (original_row + [''] * 5)[:5]
    
    json_responses, _ = search_places(api_token, zone_name, query, log_dir, max_requests=1)
    
    # --- デバッグ用コード開始 ---
    if json_responses:
        # スクリプトのディレクトリを基準にパスを構築
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
            debug_file_path = os.path.join(script_dir, 'debug_json_output.json')
            # 1回だけ書き込むようにする
            if not os.path.exists(debug_file_path):
                with open(debug_file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_responses[0], f, ensure_ascii=False, indent=2)
                print(f"デバッグ用JSONを {debug_file_path} に保存しました。")
        except Exception as e:
            print(f"デバッグファイルの保存中にエラーが発生しました: {e}")
    # --- デバッグ用コード終了 ---

    places = []
    for resp_json in json_responses:
        collect_places(resp_json, places)
        
    output_rows = []
    
    if not places:
        # 結果がない場合も、検索キーワードと元データだけ出力する
        row = [
            query, # 検索キーワード
            "", "", "", "", "", "", # 施設情報（空）
            "", "", "", "", "", "", "", "検索結果なし" # ステータスに記録
        ] + original_data
        output_rows.append(row)
        
    for p in places:
        if not isinstance(p, dict):
            continue
        
        category = p.get("category", "")
        if "介護施設" in category:
            continue
            
        # 新しいデータ構造から情報を抽出
        name = p.get("name", "")
        phone = p.get("phone", "")
        address = p.get("address", "")
        web = p.get("website", "")
        gmap = p.get("google_maps_url", "")
        rating = str(p.get("rating", "")) if p.get("rating") else ""
        category = p.get("category", "")
        lat = str(p.get("latitude", "")) if p.get("latitude") else ""
        lng = str(p.get("longitude", "")) if p.get("longitude") else ""
        gid = p.get("place_id", "")
        status = p.get("business_status", "")
        
        # 住所パース（簡易版）
        # 住所から都道府県・市区町村を抽出する処理を追加可能
        postal = ""
        pref = ""
        city = ""
        addr_detail = address
        
        # 都道府県の抽出（簡易）
        prefs = ["北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
                 "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
                 "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
                 "岐阜県", "静岡県", "愛知県", "三重県",
                 "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
                 "鳥取県", "島根県", "岡山県", "広島県", "山口県",
                 "徳島県", "香川県", "愛媛県", "高知県",
                 "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"]
        
        for pref_name in prefs:
            if address.startswith(pref_name):
                pref = pref_name
                addr_detail = address[len(pref_name):]
                
                # 市区町村の抽出（次の区切りまで）
                import re
                city_match = re.match(r'^([^0-9]+?[市区町村郡])', addr_detail)
                if city_match:
                    city = city_match.group(1)
                    addr_detail = addr_detail[len(city):]
                break
        
        # 行データ作成
        row = [
            query, # 検索キーワード
            name, phone, postal, pref, city, addr_detail,
            web, gmap, rating, category, lat, lng, gid, status
        ] + original_data
        
        output_rows.append(row)
        
    return output_rows

if __name__ == "__main__":
    process_custom_search()
