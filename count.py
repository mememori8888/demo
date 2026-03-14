"""
Google Places APIを使用して、指定されたクエリで場所のIDを取得し、
取得したIDの総数とAPIリクエストの総数をカウントするスクリプト。
"""
import json
import logging
import random
import csv
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests


def extract_api_key_from_json(file_path: Path) -> str:
    """
    指定されたJSONファイルからAPIキーを抽出します。

    Args:
        file_path: JSONファイルのパス

    Returns:
        抽出されたAPIキー
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['api_key']


def csv2list(input_file: Path) -> list[str]:
    """
    CSVファイルを読み込み、各行を結合した文字列のリストを返します。

    Args:
        input_file: 入力CSVファイルのパス

    Returns:
        住所文字列のリスト
    """
    address_list = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = pd.read_csv(f, header=None)
        for index, row in reader.iterrows():
            # 空白で結合
            joined_string = ' '.join(row.dropna().astype(str))
            address_list.append(joined_string)
    return address_list


def search_places(api_key: str, query: str, fields: str, page_token: str | None = None, **kwargs) -> dict:
    """
    Google Places API (searchText) を呼び出し、指数バックオフでリトライします。

    Args:
        api_key: Google Places APIのAPIキー
        query: 検索クエリ
        fields: 取得するフィールド
        page_token: 次ページのトークン
        **kwargs: その他のAPIパラメータ

    Returns:
        APIからのJSONレスポンス
    """
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": fields
    }
    data = {"textQuery": query}
    data.update(kwargs)
    if page_token:
        data["pageToken"] = page_token

    max_retries = 5
    base_delay = 1.0

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                logging.error(f"APIリクエストが最大リトライ回数に達しました: {e}")
                raise
            # 指数バックオフ + ジッター
            delay = (base_delay * (2 ** attempt)) + random.uniform(0, 1)
            logging.warning(f"APIリクエスト失敗: {e}。{delay:.2f}秒後にリトライします。")
            time.sleep(delay)
    return {} # Should not be reached


def count_place_ids_from_config(config_path: Path):
    """
    設定ファイルに基づいて場所IDのカウント処理を実行します。

    Args:
        config_path: 設定ファイルのパス
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
    except FileNotFoundError:
        logging.error(f"設定ファイルが見つかりません: {config_path}")
        return
    except json.JSONDecodeError:
        logging.error(f"設定ファイルのJSON形式が不正です: {config_path}")
        return

    # 結果を保存するディレクトリを作成
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)

    api_key = extract_api_key_from_json(Path("settings/api_key.json"))

    for task in tasks:
        task_name = task.get('task_name', '未定義タスク')
        base_query = task.get('query')
        address_csv_path = task.get('address_csv_path')
        included_type = task.get('includedType')
        exclude_gids_path = task.get('exclude_gids_path')

        if not all([base_query, address_csv_path]):
            logging.warning(f"タスク '{task_name}' の設定が不足しているためスキップします。")
            continue

        print(f"\n--- タスク '{task_name}' の処理を開始 ---")
        
        # 除外GIDリストの読み込み
        exclude_gids = set()
        if exclude_gids_path and (Path("settings") / exclude_gids_path).exists():
            try:
                with open(Path("settings") / exclude_gids_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    exclude_gids = {row[0] for row in reader if row}
                print(f"除外GIDリスト '{exclude_gids_path}' を読み込みました。{len(exclude_gids)}件のGIDを除外します。")
            except Exception as e:
                logging.error(f"除外GIDリスト '{exclude_gids_path}' の読み込みに失敗しました: {e}")

        address_list = csv2list(Path("settings") / address_csv_path)
        total_ids = 0
        total_requests = 0
        
        fields = "places.id,nextPageToken"
        params = {"languageCode": "ja", "includePureServiceAreaBusinesses": True}
        if included_type:
            params["includedType"] = included_type

        for address in address_list:
            search_query = f'{address} {base_query}'
            print(f"検索中: {search_query}")
            page_token = None

            while True:
                total_requests += 1
                results = search_places(api_key, search_query, fields, page_token, **params)

                if places := results.get('places'):
                    # 除外リストに含まれていないIDのみをカウント
                    valid_places = [
                        place for place in places 
                        if place.get('id') not in exclude_gids
                    ]
                    total_ids += len(valid_places)

                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                time.sleep(2) # ページネーションのための待機

        # --- 結果の出力 ---
        # コンソールへの出力
        print(f"--- タスク '{task_name}' の処理が完了しました ---")
        print(f"取得したIDの総数: {total_ids}")
        print(f"APIリクエストの総数: {total_requests}")

        # ファイルへの出力
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output_file_path = results_dir / f"{task_name}_count_result.txt"
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(f"実行日時: {current_date}\n")
            f.write(f"タスク名: {task_name}\n")
            f.write(f"取得したIDの総数: {total_ids}\n")
            f.write(f"APIリクエストの総数: {total_requests}\n")
        print(f"結果を {output_file_path} に保存しました。")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    # settings.json を使用して実行
    count_place_ids_from_config(Path("settings/settings.json"))
