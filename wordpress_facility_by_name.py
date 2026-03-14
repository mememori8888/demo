#!/usr/bin/env python3
"""
WordPress独自データから施設名で直接検索して詳細情報を取得
facility_BrightData_20.pyの仕組みを使用して、施設名+住所で検索
"""
import os
import requests
import json
import csv
import datetime
import re
import logging
import time
import random
from urllib.parse import quote
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from concurrent.futures import ThreadPoolExecutor, as_completed

# InsecureRequestWarning を無効にする
urllib3.disable_warnings(InsecureRequestWarning)

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("wordpress_facility_search.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def extract_facility_info_from_app_state(app_state, query):
    """
    APP_INITIALIZATION_STATEから施設情報を抽出
    """
    if not isinstance(app_state, list) or len(app_state) == 0:
        logging.warning(f"APP_INITIALIZATION_STATEが配列でないか空: {query}")
        return None
    
    # [0][1]に検索結果がある構造
    try:
        if len(app_state) > 0 and isinstance(app_state[0], list) and len(app_state[0]) > 1:
            results = app_state[0][1]
            if isinstance(results, list):
                # 最初の検索結果のみを処理（最も関連性が高い）
                for item in results[:1]:  # 最初の1件のみ
                    if isinstance(item, list) and len(item) > 14:
                        # [14]に施設情報がある
                        facility_data = item[14]
                        if isinstance(facility_data, list) and len(facility_data) > 0:
                            # 施設名、住所、座標などを抽出
                            info = {
                                'name': None,
                                'address': None,
                                'lat': None,
                                'lng': None,
                                'rating': None,
                                'user_ratings_total': None,
                                'place_id': None,
                                'business_status': None
                            }
                            
                            # 施設名 [14][11]
                            if len(facility_data) > 11 and facility_data[11]:
                                info['name'] = facility_data[11]
                            
                            # 住所 [14][18]
                            if len(facility_data) > 18 and facility_data[18]:
                                info['address'] = facility_data[18]
                            
                            # 座標 [14][9]
                            if len(facility_data) > 9 and isinstance(facility_data[9], list) and len(facility_data[9]) >= 2:
                                info['lat'] = facility_data[9][0]
                                info['lng'] = facility_data[9][1]
                            
                            # Place ID [14][10]
                            if len(facility_data) > 10 and facility_data[10]:
                                info['place_id'] = facility_data[10]
                            
                            # 評価 [14][4]
                            if len(facility_data) > 4 and isinstance(facility_data[4], list):
                                if len(facility_data[4]) > 7 and facility_data[4][7]:
                                    info['rating'] = facility_data[4][7]
                                if len(facility_data[4]) > 8 and facility_data[4][8]:
                                    info['user_ratings_total'] = facility_data[4][8]
                            
                            # 営業ステータス - 様々な位置を探索
                            # 優先順位: 営業時間外 > 24時間営業 > 営業中 > 一時休業 > 閉業
                            found_status = None
                            for i in range(50, min(len(facility_data), 100)):
                                if isinstance(facility_data[i], list) and len(facility_data[i]) > 0:
                                    if isinstance(facility_data[i][0], str):
                                        status = facility_data[i][0]
                                        if status in ['営業時間外', '24時間営業', '営業中', '一時休業', '閉業']:
                                            # 優先度の高いステータスで上書き
                                            priority = {'営業時間外': 1, '24時間営業': 2, '営業中': 3, '一時休業': 4, '閉業': 5}
                                            if found_status is None or priority.get(status, 99) < priority.get(found_status, 99):
                                                found_status = status
                            
                            if found_status:
                                info['business_status'] = found_status
                            
                            # 少なくとも名前があれば返す
                            if info['name']:
                                status_info = f" (営業ステータス: {info['business_status']})" if info['business_status'] else " (営業ステータス: なし)"
                                logging.info(f"施設情報抽出成功: {info['name']}{status_info}")
                                return info
    except (IndexError, TypeError) as e:
        logging.error(f"APP_INITIALIZATION_STATE解析エラー: {e}, クエリ: {query}")
    
    return None

def search_facility_by_name(api_token, zone_name, facility_name, prefecture, city, log_dir):
    """
    施設名+住所でGoogle Maps検索を実行
    """
    # 検索クエリを構築
    query = f"{facility_name} {prefecture}{city}"
    
    url = "https://api.brightdata.com/request"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    # Google Maps検索URL
    search_url = f"https://www.google.com/maps/search/{quote(query)}/?hl=ja&gl=jp"
    
    payload = {
        "zone": zone_name,
        "url": search_url,
        "format": "json"
    }
    
    MAX_RETRIES = 3
    
    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                logging.info(f"リトライ ({attempt + 1}/{MAX_RETRIES}): {query}")
                time.sleep(random.uniform(2, 5))
            
            logging.info(f"検索中: {query}")
            response = requests.post(url, headers=headers, json=payload, verify=False, timeout=120)
            
            if response.status_code == 200 and response.text:
                # レスポンスをパース
                try:
                    data = response.json()
                    
                    # bodyの中身をチェック
                    body_content = None
                    if isinstance(data, dict) and 'body' in data:
                        body_content = data['body']
                    elif isinstance(data, str):
                        body_content = data
                    else:
                        body_content = response.text
                    
                    # APP_INITIALIZATION_STATEを抽出
                    parsed_data = None
                    if body_content and isinstance(body_content, str):
                        # 先頭の不要な文字列を削除
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
                                        logging.info(f"APP_INITIALIZATION_STATE抽出成功: {query} (長さ: {len(json_str)})")
                                    except json.JSONDecodeError as e:
                                        logging.warning(f"APP_INITIALIZATION_STATE JSON解析失敗: {query}, エラー: {e}, 先頭100文字: {json_str[:100]}")
                                else:
                                    logging.warning(f"APP_INITIALIZATION_STATE 括弧終端未検出: {query}")
                            else:
                                logging.warning(f"APP_INITIALIZATION_STATE が配列で開始しない: {query}")
                    
                    # APP_INITIALIZATION_STATEから施設情報を抽出
                    if parsed_data:
                        logging.info(f"APP_INITIALIZATION_STATE解析開始: {query}, type={type(parsed_data)}, len={len(parsed_data) if isinstance(parsed_data, (list, dict)) else 'N/A'}")
                        facility_info = extract_facility_info_from_app_state(parsed_data, query)
                        if facility_info:
                            return facility_info
                        else:
                            logging.warning(f"施設情報抽出失敗: {query}")
                    
                    # HTMLから直接情報を抽出
                    extracted_info = {}
                    if body_content and facility_name in body_content:
                        # 営業ステータス（優先順位付き、より具体的なものを先にチェック）
                        status_patterns = [
                            (r'営業時間外', '営業時間外'),
                            (r'一時休業', '一時休業'),
                            (r'24\s*時間営業', '24時間営業'),
                            (r'営業中', '営業中'),
                            (r'閉業', '閉業'),
                        ]
                        for pattern, status in status_patterns:
                            if re.search(pattern, body_content):
                                extracted_info['business_status'] = status
                                break
                        
                        # 電話番号 (複数パターン対応)
                        phone_patterns = [
                            r'tel:(\+81\d{9,11})',  # +81付き
                            r'(\d{2,4}-\d{2,4}-\d{4})',  # ハイフン付き
                            r'(\d{10,11})'  # 数字のみ
                        ]
                        for pattern in phone_patterns:
                            phone_match = re.search(pattern, body_content)
                            if phone_match:
                                extracted_info['phone'] = phone_match.group(1)
                                break
                        
                        # 住所（郵便番号付き）
                        address_match = re.search(r'〒(\d{3}-\d{4})\s*([^"<>]+?)(?=["<>])', body_content)
                        if address_match:
                            extracted_info['address'] = f"〒{address_match.group(1)} {address_match.group(2).strip()}"
                        
                        # Place ID
                        place_id_match = re.search(r'ChIJ[A-Za-z0-9_-]+', body_content)
                        if place_id_match:
                            place_id = place_id_match.group(0)
                            extracted_info['place_id'] = place_id
                            # Google Maps URLを構築
                            extracted_info['google_maps_url'] = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                        
                        # 座標（複数パターン試行）
                        coord_patterns = [
                            r'\[null,null,([\d.]+),([\d.]+)\]',  # [null,null,lat,lng]
                            r'@([\d.]+),([\d.]+),',  # @lat,lng,
                        ]
                        for pattern in coord_patterns:
                            for coord_match in re.finditer(pattern, body_content):
                                try:
                                    lat = float(coord_match.group(1))
                                    lng = float(coord_match.group(2))
                                    # 緯度経度の妥当性チェック（日本付近）
                                    if 20 <= lat <= 50 and 120 <= lng <= 150:
                                        extracted_info['lat'] = lat
                                        extracted_info['lng'] = lng
                                        logging.info(f"座標抽出成功: {query}, lat={lat}, lng={lng}")
                                        break
                                except ValueError:
                                    continue
                            if 'lat' in extracted_info:
                                break
                        
                        if 'lat' not in extracted_info:
                            logging.warning(f"座標抽出失敗: {query}")
                    
                    # 抽出した情報を返す
                    if facility_name and (parsed_data or extracted_info):
                        return {
                            'name': facility_name,
                            **extracted_info
                        }
                    
                    # SERP API形式のレスポンスもチェック（念のため）
                    if isinstance(data, dict):
                        if 'organic' in data and isinstance(data['organic'], list) and len(data['organic']) > 0:
                            return data['organic'][0]
                        if 'local_results' in data and isinstance(data['local_results'], list) and len(data['local_results']) > 0:
                            return data['local_results'][0]
                    
                    logging.warning(f"検索結果なし: {query}")
                    return None
                    
                except json.JSONDecodeError as e:
                    logging.error(f"JSON解析エラー: {e}, クエリ: {query}")
                    continue
            else:
                logging.error(f"APIエラー: {response.status_code}, クエリ: {query}")
                if response.status_code in [401, 403]:
                    break
        
        except requests.exceptions.RequestException as e:
            logging.error(f"リクエスト失敗: {e}, クエリ: {query}")
    
    return None

def extract_facility_info(result, original_data):
    """
    検索結果から施設情報を抽出
    """
    if not result:
        return None
    
    # 基本情報
    name = result.get('title', result.get('name', ''))
    rating = result.get('rating', '')
    reviews = result.get('reviews', '')
    business_status = result.get('business_status', '')
    
    # 住所情報
    address = result.get('address', '')
    
    # 郵便番号と都道府県を抽出
    postal = ''
    prefecture = ''
    city = ''
    addr_detail = address
    
    postal_match = re.search(r'〒(\d{3}-\d{4})', address)
    if postal_match:
        postal = postal_match.group(1)
        addr_detail = address.replace(f'〒{postal}', '').strip()
    
    # 都道府県リスト
    prefs = ['北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
             '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
             '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県',
             '岐阜県', '静岡県', '愛知県', '三重県',
             '滋賀県', '京都府', '大阪府', '兵庫県', '奈良県', '和歌山県',
             '鳥取県', '島根県', '岡山県', '広島県', '山口県',
             '徳島県', '香川県', '愛媛県', '高知県',
             '福岡県', '佐賀県', '長崎県', '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県']
    
    for pref_name in prefs:
        if addr_detail.startswith(pref_name):
            prefecture = pref_name
            addr_detail = addr_detail[len(pref_name):]
            
            # 市区町村を抽出
            city_match = re.match(r'^([^0-9]+?[市区町村郡])', addr_detail)
            if city_match:
                city = city_match.group(1)
                addr_detail = addr_detail[len(city):]
            break
    
    # 連絡先情報
    phone = result.get('phone', '')
    website = result.get('website', '')
    
    # 座標
    gps = result.get('gps_coordinates', {})
    lat = gps.get('latitude', '') if isinstance(gps, dict) else ''
    lng = gps.get('longitude', '') if isinstance(gps, dict) else ''
    
    # Place ID
    place_id = result.get('place_id', '')
    if not place_id:
        # data_idから抽出を試みる
        data_id = result.get('data_id', '')
        if data_id:
            place_id = data_id
    
    # Google Maps URL
    google_maps_url = result.get('google_maps_url', result.get('link', ''))
    
    # カテゴリ/タイプ
    place_type = result.get('type', '')
    
    # 営業時間/ステータス
    hours = result.get('hours', '')
    open_state = business_status if business_status else result.get('open_state', '')
    
    return {
        '検索キーワード': f"{original_data['name']} {original_data['prefecture']}{original_data['city']}",
        '施設名': name,
        '電話番号': phone,
        '郵便番号': postal,
        '都道府県': prefecture,
        '市区町村': city,
        '住所': addr_detail,
        'web': website,
        'GoogleMap': google_maps_url,
        'ランク': rating,
        'レビュー数': reviews,
        'カテゴリ': place_type,
        '緯度': lat,
        '経度': lng,
        '施設GID': place_id,
        '営業時間': hours,
        '営業ステータス': open_state,
        '元データ_施設名': original_data['name'],
        '元データ_電話番号': original_data['phone'],
        '元データ_都道府県': original_data['prefecture'],
        '元データ_市区町村': original_data['city'],
        '元データ_住所': original_data['address']
    }

def process_single_facility(api_token, zone_name, facility_data, log_dir):
    """1件の施設を検索"""
    result = search_facility_by_name(
        api_token, 
        zone_name, 
        facility_data['name'],
        facility_data['prefecture'],
        facility_data['city'],
        log_dir
    )
    
    if result:
        return extract_facility_info(result, facility_data)
    else:
        # 結果なしの場合も元データを記録
        return {
            '検索キーワード': f"{facility_data['name']} {facility_data['prefecture']}{facility_data['city']}",
            '施設名': '',
            '電話番号': '',
            '郵便番号': '',
            '都道府県': '',
            '市区町村': '',
            '住所': '',
            'web': '',
            'GoogleMap': '',
            'ランク': '',
            'レビュー数': '',
            'カテゴリ': '',
            '緯度': '',
            '経度': '',
            '施設GID': '',
            '営業時間': '',
            '営業ステータス': '検索結果なし',
            '元データ_施設名': facility_data['name'],
            '元データ_電話番号': facility_data['phone'],
            '元データ_都道府県': facility_data['prefecture'],
            '元データ_市区町村': facility_data['city'],
            '元データ_住所': facility_data['address']
        }

def main():
    """メイン処理"""
    script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
    log_dir = os.path.join(script_dir, 'logs')
    input_csv = os.path.join(script_dir, 'results', 'wordpress独自データ.csv')
    output_csv = os.path.join(script_dir, 'results', 'wordpress_facility_search_results.csv')
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # API設定
    api_token = os.environ.get("BRIGHTDATA_API_TOKEN")
    if not api_token:
        print("エラー: 環境変数 'BRIGHTDATA_API_TOKEN' が設定されていません。")
        return
    
    zone_name = "serp_api1"
    
    # 入力データ読み込み
    facilities = []
    with open(input_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 5:
                # 施設名を抽出（都道府県市区町村-施設名 の形式）
                name_part = row[0].split('-', 1)
                facility_name = name_part[1] if len(name_part) > 1 else name_part[0]
                
                facilities.append({
                    'name': facility_name,
                    'phone': row[1],
                    'prefecture': row[2],
                    'city': row[3],
                    'address': row[4]
                })
    
    # 全件処理
    print(f"処理開始: {len(facilities)}件を処理します")
    
    # 出力ファイル準備
    if os.path.exists(output_csv):
        os.remove(output_csv)
    
    # ヘッダー書き込み
    with open(output_csv, 'w', newline='', encoding='utf-8-sig') as f:
        if facilities:
            dummy_result = process_single_facility(api_token, zone_name, facilities[0], log_dir)
            writer = csv.DictWriter(f, fieldnames=dummy_result.keys())
            writer.writeheader()
    
    # 並列処理
    MAX_WORKERS = 10
    completed = 0
    total = len(facilities)
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for facility in facilities:
            futures.append(executor.submit(process_single_facility, api_token, zone_name, facility, log_dir))
        
        for future in as_completed(futures):
            result = future.result()
            completed += 1
            
            # 結果を追記
            with open(output_csv, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=result.keys())
                writer.writerow(result)
            
            status = "✓" if result['施設名'] else "✗"
            print(f"[{completed}/{total}] {status} {result['検索キーワード']}")
    
    print(f"\n完了: {output_csv}")

if __name__ == "__main__":
    main()
