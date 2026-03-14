"""
カテゴリの副産物の仕分処理の追加
output.jsonを先に取得するデザインの検討の為の出力テスト
"""
import os
import requests
import json
import csv
import datetime
import re
from bs4 import BeautifulSoup
import pandas as pd
import logging
import time
import random
from math import ceil
import random

randomC = random.uniform(1,5)

def extract_api_key_from_json(file_path):
    """
    指定されたJSONファイルからAPIキーを抽出します。

    Args:
        file_path (str): JSONファイルのパス

    Returns:
        str: 抽出されたAPIキー
    """

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    api_key = data['api_key']
    return api_key



def update_mini(base_query,api_key, file_path, facility_file, review_file, update_facility_path, update_review_path, exclude_gids_path, results_dir, included_type=None):
    def split_to_csv(df, file_path, chunksize=10000, mode='a'): #チャンクでcsvに出力
        # 'w'モードの初回書き込みか、'a'モードでファイルが存在しない場合にヘッダーを書き込む
        write_header = (mode == 'w') or (not os.path.exists(file_path) or os.path.getsize(file_path) == 0)

        for i in range(0, len(df), chunksize):
            # 'w'モードの場合、最初のチャンクで上書きし、以降は追記('a')モードに切り替える
            current_mode = 'w' if i == 0 and mode == 'w' else 'a'
            # ヘッダーを書き込むのは、ループの初回かつ、書き込みが必要と判断された場合のみ
            is_first_chunk_and_header_needed = (i == 0 and write_header)
            df.iloc[i:i+chunksize].to_csv(f"{file_path}", mode=current_mode, index=False, header=is_first_chunk_and_header_needed, encoding='utf-8')

    def chunks(l, n):
        for i in range(0, len(l), n):
            yield l[i:i + n]

    def bs_address(text):
            # HTMLを解析
        soup = BeautifulSoup(text, 'html.parser')

        # class="region"を持つ要素を検索
        region_element = soup.find('span', class_='region')
        region_element_street = soup.find('span', class_='street-address')
        # 要素のテキストを取得
        if region_element:
            region = region_element.text
            region_street = region_element_street.text
           
        else:
            region = 'not found'
            region_street = 'not found'
        return region,region_street

    def split_address(address_text):
        """
        住所文字列を郵便番号と住所に分割する関数

        Args:
            address_text: 分割したい住所文字列

        Returns:
            tuple: (郵便番号, 住所)
        """

        # 郵便番号の正規表現 (数字5桁または7桁)
        postal_code_pattern = r'〒\d{3}-\d{4}|〒\d{7}'

        # 郵便番号部分を抽出
        match = re.search(postal_code_pattern, address_text)
        if match:
            postal_code = match.group()
            address = address_text.replace(postal_code, "").strip()
            return postal_code, address
        else:
            return None, address_text



    def convert_date_format(date_str):
        """
        日付文字列のフォーマットを変換する関数

        Args:
            date_str: 変換する日付文字列 (例: "2013-12-13")

        Returns:
            変換後の日付文字列 (例: "2013年12月13日")
        """

        # 文字列をdatetimeオブジェクトに変換
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')

        # datetimeオブジェクトを新しいフォーマットの文字列に変換
        new_format = date_obj.strftime('%Y年%m月%d日')
        return new_format

    # 住所のcsvを読み込んで、listにいれる関数
    def csv2list(input_file):
        adress_list = []
        # CSVファイルを開く
        with open(input_file, 'r',encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                joined_string = ' '.join(row)
                after_row = str(joined_string)
                adress_list.append(after_row)

        return adress_list
    


    def search_places(api_key, query,fields,page_token=None,**kwargs):
        """
        Google Places API (新版) の searchText API を呼び出す関数

        Args:
            api_key: Google Places API の API キー
            query: 検索クエリ
            page_token: 次のページのトークン (初回は None)

        Returns:
            辞書形式の検索結果
        """

        url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": fields
        }
        data = {
            "textQuery": query
        }
        data.update(kwargs)
        if page_token:
            data["pageToken"] = page_token

        # 指数バックオフ
        max_retries = 5
        base = 2
        jitter=True

        for attempt in range(1, max_retries + 1):
          try:
              response = requests.post(url, headers=headers, json=data, timeout=15)
              response.raise_for_status()  # ステータスコードが異常な場合、例外を発生させる
              return response.json()

          except requests.exceptions.RequestException as e:
              error_message = f"APIリクエスト失敗 (試行 {attempt}/{max_retries}): {e}"
              try:
                  error_details = response.json()
                  error_message += f" - 詳細: {error_details}"
              except (requests.exceptions.JSONDecodeError, AttributeError):
                  error_message += f" - レスポンスボディ: {response.text}"
              logging.warning(error_message)
              delay = base ** attempt
              if jitter:
                  delay += random.uniform(0, delay)
              time.sleep(delay)

        raise Exception("Max retries exceeded.")

    # ログ設定
    logging.basicConfig(filename=os.path.join(results_dir, 'app.log'), level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(message)s')

    # APIキーを抽出
    # api_key = extract_api_key_from_json(api_file_path)

    # API キーを置き換えてください
    # 使用例
    # query = "東京都 港区 斎場||葬儀場||告別式"
    fields = ','.join(["places.displayName",
              "places.formattedAddress",
              "places.attributions",
              "places.id",
              "places.name",
              "nextPageToken",
              "places.addressComponents",
              "places.adrFormatAddress",
              "places.displayName",
              "places.nationalPhoneNumber",
              "places.location",
              "places.rating",
              "places.primaryTypeDisplayName",
              "places.websiteUri",
              "places.googleMapsUri",
              "places.reviews",
              "places.userRatingCount",
              "places.regularOpeningHours",
              "places.regularSecondaryOpeningHours",
              "places.reviewSummary"
             ])

    # 他のパラメータを追加
    params = {
        "languageCode":"ja",
        "includePureServiceAreaBusinesses":True
    }
    if included_type:
        params["includedType"] = included_type

    # 除外GIDリストの読み込み
    exclude_gids = set()
    if exclude_gids_path and os.path.exists(exclude_gids_path):
        try:
            with open(exclude_gids_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                exclude_gids = {row[0] for row in reader if row}
            print(f"除外GIDリスト '{exclude_gids_path}' を読み込みました。{len(exclude_gids)}件のGIDを除外します。")
        except Exception as e:
            logging.error(f"除外GIDリスト '{exclude_gids_path}' の読み込みに失敗しました: {e}")

    # 全体の流れ
    adress_list = csv2list(file_path)
    #リクエスト数が超過しないようにするためのカウント
    request_count = 0
    #IDの振り方
    # ID = 101
    # review_ID = 1
    # 施設情報のCSVファイルを読み込む
    #chunk導入箇所
    facility_df = pd.DataFrame()
    if os.path.exists(facility_file) and os.path.getsize(facility_file) > 0:
        reader = pd.read_csv(facility_file, chunksize=10000)
        for param in reader:
            facility_df = pd.concat([facility_df, param])
        print(f"既存の施設情報ファイル '{facility_file}' を読み込みました。")
        
        # 営業ステータス列がない場合は空列として追加（後方互換性）
        if '営業ステータス' not in facility_df.columns:
            print("既存施設ファイルに営業ステータス列がありません。空列として追加します。")
            facility_df['営業ステータス'] = ''
    else:
        print(f"施設情報ファイル '{facility_file}' が存在しないか空です。新しく作成します。")
        # 新しいファイルを作成し、空のDataFrameを初期化
        facility_df = pd.DataFrame(columns=['施設ID','施設名', '電話番号', '郵便番号', '都道府県','市区町村','住所',"web",'GoogleMap','ランク', 'カテゴリ', '緯度','経度','施設GID','営業ステータス'])

    # DataFrameの最後の行を取得
    try:
        last_row = facility_df.iloc[-1]
        print(f"施設情報の最後は{last_row}")
        # 最後の施設IDを取得
        last_facility_id = last_row['施設ID'] + 1
        # print(last_facility_id)
        # print(type(last_facility_id))
    except:
        last_facility_id = 101
    # レビュー情報.csvを読み込む
    review_df = pd.DataFrame()
    if os.path.exists(review_file) and os.path.getsize(review_file) > 0:
        reader = pd.read_csv(review_file, chunksize=10000)
        for param in reader:
            review_df = pd.concat([review_df, param])
        print(f"既存のレビュー情報ファイル '{review_file}' を読み込みました。")
        
        # 施設GID列がない場合は空列として追加（後方互換性）
        if '施設GID' not in review_df.columns:
            print("既存レビューファイルに施設GID列がありません。空列として追加します。")
            # 施設IDの後に施設GIDを挿入
            cols = review_df.columns.tolist()
            if '施設ID' in cols:
                facility_id_idx = cols.index('施設ID')
                cols.insert(facility_id_idx + 1, '施設GID')
                review_df['施設GID'] = ''
                review_df = review_df[cols]
            else:
                review_df['施設GID'] = ''
    else:
        print(f"レビュー情報ファイル '{review_file}' が存在しないか空です。新しく作成します。")
        # 新しいファイルを作成し、空のDataFrameを初期化
        review_df = pd.DataFrame(columns=['レビューID','施設ID', '施設GID', 'レビュワー評価', 'レビュワー名', 'レビュー日時', 'レビュー本文', 'レビュー要約', 'レビューGID'])

    # レビューがありませんを除外
    try:
        new_review_df = review_df[~review_df['レビューID'].str.contains('レビューがありません')]
    except:
        new_review_df = review_df
    # 最後のレビューIDを取得
    # print(type(new_review_df))
    # print(new_review_df)
    try:
        last_review = new_review_df.iloc[-1]
        last_review_id = int(last_review['レビューID']) + 1
        # print(last_review_id)
    except:
        last_review_id = 1

    # 既存のGIDとIDの対応を高速に検索できるように準備
    existing_gids = set(facility_df['施設GID'])
    existing_review_gids = set(review_df['レビューGID'])
    gid_to_id_map = facility_df.set_index('施設GID')['施設ID'].to_dict()

    
    update_list = []
    request_log = [] # 各クエリのリクエスト回数を記録するリスト
    for query in adress_list:
        # 初期化
        search_query = f'{query} {base_query}'
        print(f'現在の検索キーワード　{query} {base_query} ')        
        page_token = None
        if 'end end' in query:
            break
        elif 'a b' in query:
            continue

        query_request_count = 0 # このクエリのリクエスト回数カウンター

        while True:
            time.sleep(2)
            request_count += 1
            query_request_count += 1
            results = search_places(api_key, search_query,fields, page_token,**params)
#jsonファイルをダウンロードした場合はここからやる。

            try:
                results['places']
                print("responseがありました。")
                print(results['places'])
                
            except:
                print("responseがありませんでした。")
                break
            
            for result in results['places']:
                
                facility_id = result.get('id')

                if facility_id in exclude_gids:
                    print(f"GID '{facility_id}' は除外リストに含まれているためスキップします。")
                    continue

                if facility_id:
                    if facility_id not in existing_gids:
                        ID = last_facility_id
                        last_facility_id += 1
                        print('新しい施設です。')
                    else: # 既存の施設の場合
                        ID = gid_to_id_map[facility_id]
                else:
                    ID = last_facility_id
                    last_facility_id += 1
                    facility_id = '#N/A'
                    logging.warning(f"Place IDが取得できませんでした。新しいIDを採番します。")

                facility_name = result.get('displayName', {}).get('text', '#N/A')
               
                prefecture = '?' #初期化
                city = '?' #初期化
                try:
                    facility_adress = result.get('formattedAddress', '')
                    postal_code, address = split_address(facility_adress)
                    address = address.replace('日本、', '')
                    for component in result.get("addressComponents", []):
                        if "administrative_area_level_1" in component["types"]:
                            prefecture = component["longText"]
                        elif "locality" in component["types"]:
                            city = component["longText"]
                        elif "administrative_area_level_2" in component["types"]:
                            city = component["longText"]
                except:
                    address = '#N/A '
                    postal_code = '#N/A '
                    prefecture = '#N/A '
                    city = '#N/A '
                    # print('住所はありません')
                try:
                    facility_tell = result['nationalPhoneNumber']
                    # print(f"電話番号: {result['nationalPhoneNumber']}")
                except:
                    facility_tell = '#N/A '
                    # print('電話番号はありません')
                try:
                    facility_location = result['location']
                    #   {'latitude': 34.7144547, 'longitude': 135.5135757}
                    # f-stringを使ってフォーマットを指定
                    facility_lati = f"{facility_location['latitude']}"
                    facility_long = f"{facility_location['longitude']}"
                except:
                    facility_location = '#N/A '
                    facility_lati = '#N/A '
                    facility_long = '#N/A '
                    # print('緯度経度はありません。')
                try:
                    facility_rank = result['rating']
                    # print(f"星ランク:{result['rating']}")
                except:
                    facility_rank = '#N/A '
                    # print(f'星ランクはありません')
                try:
                    facility_cat = result['primaryTypeDisplayName']['text']
                    # print(f"カテゴリ？:{result['primaryTypeDisplayName']['text']}")
                    #N/Aと斎場だった場合、とそれ以外の場合に分ける。
                except:
                    facility_cat = '#N/A'
                    # print('カテゴリはありません。')
                try:
                    facility_web = result['websiteUri']
                except:
                    facility_web = '#N/A '
                try:
                    facility_gmap = result['googleMapsUri']
                except:
                    facility_gmap = '#N/A '
                try:
                    facility_region_text = result['adrFormatAddress']
                    facility_region = bs_address(facility_region_text)
                except:
                    facility_region = ['#N/A ','#N/A ']
                
                if postal_code is not None and prefecture is not None and city is not None:
                    address = address.replace(postal_code,'').replace(prefecture,'').replace(city,'')
                else:
                    # addressがNoneの場合の処理を記述
                    address = '#N/A'
                    print("住所情報が見つからなかったため、置換処理をスキップしました。")

                # レビューのループを作る
                try:
                    for param in result['reviews']:
                        # print(param)
                        try:
                            review_id = param['name']
                            # 正規表現パターン: 最後のスラッシュ以降の文字列を抽出
                            pattern = r"/([^/]+)$"

                            match = re.search(pattern, review_id)
                            if match:
                                review_id = match.group(1)
                                # print(review_id)
                            if review_id not in existing_review_gids:
                                # レビューがない場合
                                print("新しいreviewがありました。")
                                review_ID = last_review_id
                                last_review_id += 1
                            else:  # レビューがある場合
                                #ココがおかしいよ
                                # print("レビューは既にありました。")
                                continue
                                # ID =  facility_df[facility_df['施設GID'].str.contains(facility_id)]['施設ID']
                        except:
                            review_id = '#N/A '
                        try:
                            review_time = param['publishTime']
                            review_time = review_time[:10]
                            #   2013-12-13
                            review_time = convert_date_format(review_time)
                        except:
                            review_time = '#N/A '
                        try:
                            review_rating = param['rating'] 
                        except:
                            review_rating = '#N/A '
                        try:
                            review_text = param['text']['text']
                        except:
                            review_text = '#N/A '
                        try:
                            review_name = param['authorAttribution']['displayName']
                        except:
                            review_name = '#N/A '
                        try:
                            review_summary = param['summary']
                        except:
                            review_summary = '#N/A '

                        output_list = [ID,facility_name,facility_tell,postal_code,prefecture,city, address,facility_web,facility_gmap,facility_rank,facility_cat,facility_lati,facility_long,facility_id,'',review_ID,facility_id,review_rating,review_name,review_time,review_text,review_summary,review_id]
                    #update_listに蓄積
                        update_list.append(output_list)

                    
                except:
                    print("レビューがありません")
                    continue
                
                        
                    
            
            # 追記するデータ (例: 複数のデータをリストで持つ)    
            # 次のページのトークンを取得
            page_token = results.get('nextPageToken')
            # 次のページのトークンがなければループを終了
            print(f'リクエスト {request_count}回目 (クエリ内 {query_request_count}回目)')
            if not page_token:
                break
        
        # クエリごとのリクエスト回数を記録
        request_log.append({'query': query, 'request_count': query_request_count})
            
    # update_listの重複削除

    # リスト内のリストをタプルに変換
    # tuple_list = [tuple(item) for item in update_list]
    # Pandas DataFrameに変換
    update_df = pd.DataFrame(columns = ['施設ID','施設名', '電話番号', '郵便番号', '都道府県','市区町村','住所',"web",'GoogleMap','ランク', 'カテゴリ', '緯度','経度','施設GID','営業ステータス', 'レビューID','施設GID_レビュー','レビュワー評価', 'レビュワー名', 'レビュー日時', 'レビュー本文','レビュー要約','レビューGID'])  # 列名を任意に設定
    if update_list:
        seperate_num = 10
        chunk_num = ceil(len(update_list) / seperate_num)
        result = list(chunks(update_list,chunk_num))
        # print(result)
        tuple_list = [tuple(item) for item in result]
        for param in tuple_list:
            con_df = pd.DataFrame(param,columns = ['施設ID','施設名', '電話番号', '郵便番号', '都道府県','市区町村','住所',"web",'GoogleMap','ランク', 'カテゴリ', '緯度','経度','施設GID','営業ステータス', 'レビューID','施設GID_レビュー','レビュワー評価', 'レビュワー名', 'レビュー日時', 'レビュー本文','レビュー要約','レビューGID'])
            update_df = pd.concat([update_df,con_df])

    
    # update_df.to_csv('update.csv', index=False, encoding='utf-8')  # index=False でインデックス列を出力しない
    # print("update_dfの出力")
    # print(update_df)
    # CSVファイルに出力
    # 施設IDから経度緯度までのDataFrameを作成


    update_df_facility = update_df[['施設ID','施設名', '電話番号', '郵便番号', '都道府県','市区町村','住所',"web",'GoogleMap','ランク', 'カテゴリ', '緯度','経度','施設GID','営業ステータス']]
    # 施設IDとレビューID～レビュー本文のDataFrameを作成
    update_df_review = update_df[['レビューID','施設ID','施設GID_レビュー',  'レビュワー評価', 'レビュワー名', 'レビュー日時', 'レビュー本文','レビュー要約','レビューGID']]
    update_df_review.rename(columns={'施設GID_レビュー': '施設GID'}, inplace=True)
    # 列名 (文字列) をリストで指定
    subset_cols = ['施設GID']
    # 重複を削除
    update_df_facility = update_df_facility.drop_duplicates(subset=subset_cols)
    update_df_facility = update_df_facility.dropna(subset=subset_cols)

        # 列名 (文字列) をリストで指定
    subset_review_cols = ['レビューGID']
    # 重複を削除
    update_df_review = update_df_review.drop_duplicates(subset=subset_review_cols).dropna(subset=subset_review_cols)
    #施設増分とレビュー増分の出力
    split_to_csv(update_df_facility,update_facility_path,chunksize=10000,mode='w')
    split_to_csv(update_df_review,update_review_path,chunksize=10000,mode='w')
    # update_df_facility.to_csv('葬儀施設増分.csv',mode = 'w', index=False, encoding='utf-8')
    # update_df_review.to_csv('葬儀レビュー増分.csv',mode = 'w', index=False, encoding='utf-8')
    # 既存のdfにupdate_dfを追加
    # 行方向に結合
    added_facility_df = pd.concat([facility_df, update_df_facility])
    added_review_df = pd.concat([review_df,update_df_review])
    # 重複削除
    # 列名 (文字列) をリストで指定
    subset_cols = ['施設GID']

    # 重複を削除
    added_facility_df = added_facility_df.drop_duplicates(subset=subset_cols).dropna(subset=subset_cols)
    
    
        # 列名 (文字列) をリストで指定
    subset_review_cols = ['レビューGID']

    # 重複を削除
    added_review_df = added_review_df.drop_duplicates(subset=subset_review_cols).dropna(subset=subset_review_cols)
    print(added_facility_df)
    print(added_review_df)
    # CSVファイルに出力
    # added_facility_df.to_csv('葬儀施設.csv', index=False, encoding='utf-8')
    # added_review_df.to_csv('葬儀レビュー.csv', index=False, encoding='utf-8')
    split_to_csv(added_facility_df,facility_file,chunksize=10000,mode='w')
    split_to_csv(added_review_df,review_file,chunksize=10000,mode='w')
            
    # dfから施設とレビューに分ける

    # リクエスト回数のログをCSVに出力
    request_log_df = pd.DataFrame(request_log)
    # request_log_path = os.path.join(os.path.dirname(facility_file), 'request_counts.csv')
    # request_log_df.to_csv(request_log_path, index=False, encoding='utf-8-sig')
    # print(f"各クエリのリクエスト回数を '{request_log_path}' に保存しました。")
    print("施設情報.csvとレビュー情報.csvを更新しました")
    return request_count

def run_from_config(config_file, exclude_gids_path=None):
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
    except FileNotFoundError:
        print(f"エラー: 設定ファイル '{config_file}' が見つかりません。")
        return
    except json.JSONDecodeError:
        print(f"エラー: 設定ファイル '{config_file}' の形式が不正です。JSON形式を確認してください。")
        return

    # # 環境変数からAPIキーを取得
    # api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
    # if not api_key:
    #     print("エラー: 環境変数 'GOOGLE_MAPS_API_KEY' が設定されていません。")
    #     return
    api_file_path = 'setting/api_key.json'
    api_key = extract_api_key_from_json(api_file_path) # settingsフォルダからの読み込み
   

    for task in tasks:
        task_name = task.get('task_name', '未定義タスク')
        base_query = task.get('query')
        included_type = task.get('includedType')
        # 結果を保存するディレクトリを作成
        results_dir = "results"
        os.makedirs(results_dir, exist_ok=True)

        # ファイルパスをresultsディレクトリ配下に設定
        file_path = os.path.join('setting', task.get('address_csv_path')) # address.csvはsettingフォルダにある想定
        facility_file = os.path.join(results_dir, task.get('facility_file'))
        review_file = os.path.join(results_dir, task.get('review_file'))
        update_facility_path = os.path.join(results_dir, task.get('update_facility_path'))
        update_review_path = os.path.join(results_dir, task.get('update_review_path'))
        exclude_gids_path = os.path.join('setting', task.get('exclude_gids_path')) if task.get('exclude_gids_path') else None # 設定ファイルから読み込む

        print(f'設定された検索クエリの業種は　{base_query}')
        print(f'設定された検索クエリの住所は　{file_path}')
        if included_type:
            print(f'設定されたカテゴリは　{included_type}')
        print(f'設定された施設情報ファイルは　{facility_file}')
        print(f'設定されたレビュー情報ファイルは　{review_file}')
        print(f'設定された増分施設情報ファイルは　{update_facility_path}')
        print(f'設定された増分レビューファイルは　{update_review_path}')
        print(f'設定された除外GIDファイルは　{exclude_gids_path}')
        # address_csv_pathは必須だが、他は生成されるのでチェック対象から外す
        if not all([base_query, task.get('address_csv_path'), task.get('facility_file'), task.get('review_file'), task.get('update_facility_path'), task.get('update_review_path')]):
            print(f"エラー: タスク '{task_name}' に必要な設定情報が不足しています。スキップします。")
            continue
        time.sleep(10)
        # try:
        print(f"\n--- タスク '{task_name}' の処理を開始 ---")
        total_requests = update_mini(
            base_query = base_query,
            api_key=api_key, # api_key.jsonから取得したAPIキーを渡す
            file_path=file_path,
            facility_file=facility_file,
            review_file=review_file,
            update_facility_path=update_facility_path,
            update_review_path=update_review_path,
            exclude_gids_path=exclude_gids_path,
            results_dir=results_dir,
            included_type=included_type
        )
        print(f"--- タスク '{task_name}' の処理が完了しました ---")
        print(f"合計リクエスト数: {total_requests}")
        # except Exception as e:
        #     print(f"エラー: タスク '{task_name}' の実行中に予期せぬエラーが発生しました: {e}")
        #     logging.error(f"タスク '{task_name}' の実行中にエラーが発生: {e}")


if __name__ == "__main__":
    run_from_config("setting/settings.json")
