#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GoogleマップURLからFIDを抽出するスクリプト
CSVファイルのGoogleMap列からURLを読み込み、リダイレクト後のURLからFIDを抽出
"""

import csv
import re
import logging
import argparse
import os
import sys
import json
import requests
from pathlib import Path
from urllib.parse import unquote
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def create_github_issue(title, body, labels=None):
    """
    GitHub Issueを作成する
    
    Args:
        title: Issueのタイトル
        body: Issueの本文
        labels: ラベルのリスト（例: ['bug', 'data-error']）
    
    Returns:
        bool: 成功した場合True、失敗した場合False
    """
    github_token = os.getenv('GITHUB_TOKEN')
    repo_owner = os.getenv('GITHUB_REPOSITORY_OWNER', 'mememori8888')
    repo_name = os.getenv('GITHUB_REPOSITORY_NAME', 'googlemap')
    
    if not github_token:
        logging.warning("GITHUB_TOKEN環境変数が設定されていないため、Issueを作成できません")
        return False
    
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    data = {
        "title": title,
        "body": body
    }
    
    if labels:
        data["labels"] = labels
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 201:
            issue_url = response.json().get('html_url')
            logging.info(f"✅ GitHub Issueを作成しました: {issue_url}")
            return True
        else:
            logging.error(f"❌ GitHub Issue作成失敗: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logging.error(f"❌ GitHub Issue作成中にエラー: {e}")
        return False

def validate_required_columns(headers, rows, input_file):
    """
    必須列の存在をチェックし、不足している場合はGitHub Issueを作成
    
    Args:
        headers: CSVのヘッダー（列名リスト）
        rows: CSVの全データ行
        input_file: 入力ファイルパス
    
    Returns:
        tuple: (googlemap_col, id_col, gid_col, エラーメッセージ)
    """
    # 列名を探す
    sample_row = rows[0] if rows else None
    googlemap_col = find_googlemap_column(headers, sample_row)
    gid_col = find_gid_column(headers)
    id_col = find_id_column(headers)
    
    errors = []
    missing_columns = []
    
    # 必須列のチェック
    if not googlemap_col:
        errors.append("❌ GoogleマップURL列が見つかりません")
        missing_columns.append("GoogleマップURL (GoogleMap, URL, google_map など)")
    
    if not id_col:
        errors.append("⚠️ 施設ID列が見つかりません（推奨）")
        missing_columns.append("施設ID (施設ID, ID, facility_id など)")
    
    if not gid_col:
        errors.append("⚠️ 施設GID列が見つかりません（推奨）")
        missing_columns.append("施設GID (施設GID, GID, facility_gid など)")
    
    # データの存在チェック
    if googlemap_col and rows:
        valid_url_count = sum(1 for row in rows if row.get(googlemap_col, '').strip())
        if valid_url_count == 0:
            errors.append(f"❌ GoogleマップURL列（{googlemap_col}）にデータがありません")
    
    # エラーがある場合
    if errors:
        error_msg = "\n".join(errors)
        logging.error("\n" + error_msg)
        logging.error(f"\n利用可能な列: {', '.join(headers)}")
        
        # GitHub Issueを作成
        issue_title = f"[extract_fid_from_urls.py] 必須データ不足エラー"
        issue_body = f"""## エラー内容

`extract_fid_from_urls.py`の実行に必要なデータが不足しています。

### 不足している列

{chr(10).join(f"- {col}" for col in missing_columns)}

### エラー詳細

```
{error_msg}
```

### ファイル情報

- **入力ファイル**: `{input_file}`
- **利用可能な列**: {', '.join(headers)}
- **データ行数**: {len(rows)}行

### 必須データ

`extract_fid_from_urls.py`を実行するには、以下の列が必要です:

1. **GoogleマップURL** (必須) - 列名例: `GoogleMap`, `URL`, `google_map`
2. **施設ID** (推奨) - 列名例: `施設ID`, `ID`, `facility_id`
3. **施設GID** (推奨) - 列名例: `施設GID`, `GID`, `facility_gid`

### 対応方法

1. 入力CSVファイルに上記の列が含まれているか確認してください
2. 列名が異なる場合は、スクリプトが認識できる名前に変更してください
3. GoogleマップURL列にデータが入っていることを確認してください

---

*このIssueは自動生成されました*
"""
        
        create_github_issue(
            title=issue_title,
            body=issue_body,
            labels=["bug", "data-error", "automated"]
        )
        
        return None, None, None, error_msg
    
    return googlemap_col, id_col, gid_col, None

def setup_driver():
    """Selenium WebDriverをセットアップ"""
    # logging.info("WebDriverをセットアップしています...")
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # ヘッドレスモード
    chrome_options.add_argument('--no-sandbox')  # サンドボックス無効化
    chrome_options.add_argument('--disable-dev-shm-usage')  # 共有メモリ無効化
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    # logging.info("✓ WebDriver起動完了")
    
    return driver

def extract_fid_from_url(url):
    """
    GoogleマップURLからFIDを抽出
    """
    if not url:
        return None
        
    decoded_url = unquote(url)
    
    # 優先パターン: !1s の後ろにある 0x...:0x... (最も確実)
    priority_pattern = r'!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)'
    match = re.search(priority_pattern, decoded_url)
    if match:
        return match.group(1)
    
    # パターン2: /1s の後ろにあるもの
    pattern2 = r'/1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)'
    match = re.search(pattern2, decoded_url)
    if match:
        return match.group(1)
        
    # 汎用パターン: 任意の場所にある 0x...:0x...
    # ただし、誤検知のリスクがあるため、上記で見つからない場合のフォールバック
    general_pattern = r'(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)'
    matches = re.findall(general_pattern, decoded_url)
    if matches:
        # 複数ある場合は最初のものを返す（通常は最初がFID）
        return matches[0]
    
    return None

def extract_gid_from_url(url):
    """
    GoogleマップURLからGID (Google Place ID) を抽出
    
    パターン例:
    - /place/...!1s0x... の前の部分から ChIJ... を抽出
    - /maps/place/ の後ろにある ChIJ...
    - data=...!4m...!3m...!1sChIJ... からの抽出
    
    注意: cid形式のURLからは直接GIDを抽出できません。
    リダイレクト後のURLから抽出する必要があります。
    """
    if not url:
        return None
    
    decoded_url = unquote(url)
    
    # パターン1: data= パラメータ内の !1sChIJ...
    # 例: data=!4m5!3m4!1sChIJr52f68_iAGARL7oYaqfduY4
    data_pattern = r'!1s(ChIJ[A-Za-z0-9_-]+)'
    match = re.search(data_pattern, decoded_url)
    if match:
        return match.group(1)
    
    # パターン2: /place/ の直後にある ChIJ...（スラッシュ2つも対応）
    # 例: /place/ChIJr52f68_iAGARL7oYaqfduY4
    # 例: /place//ChIJr52f68_iAGARL7oYaqfduY4
    place_pattern = r'/place/+([ChIJ][A-Za-z0-9_-]+)'
    match = re.search(place_pattern, decoded_url)
    if match:
        gid = match.group(1)
        # ChIJで始まるかチェック（FIDと区別するため）
        if gid.startswith('ChIJ'):
            return gid
    
    # パターン3: 汎用パターン（任意の場所にある ChIJ...）
    # FIDとGIDを区別するため、ChIJで始まるもののみ
    general_pattern = r'(ChIJ[A-Za-z0-9_-]+)'
    matches = re.findall(general_pattern, decoded_url)
    if matches:
        # 複数ある場合は最初のものを返す
        return matches[0]
    
    return None

def get_redirected_url(driver, original_url, max_wait=20, check_interval=2):
    """
    URLにアクセスしてリダイレクト後のURLを取得
    JavaScriptによるリダイレクトを待機
    """
    try:
        driver.get(original_url)
        
        # 初回待機（ページ読み込み）
        time.sleep(3)
        
        # 最初のURLを記録
        initial_url = driver.current_url
        
        # URLが変化するまで待機
        waited = 3
        retry_count = 0
        max_retries = 8  # 最大8回チェック
        
        while waited < max_wait and retry_count < max_retries:
            time.sleep(check_interval)
            waited += check_interval
            retry_count += 1
            
            current_url = driver.current_url
            
            # URLが変化したかチェック
            if current_url != initial_url:
                # GoogleマップのURLであれば採用
                if 'google' in current_url and 'maps' in current_url:
                    # logging.debug(f"  ✓ URLが変化しました (待機時間: {waited}秒)")
                    return current_url
                
                # URLが変わったがGoogleマップっぽくない場合
                # logging.debug(f"  URLが変化しましたが、GoogleマップのURLではない可能性があります: {current_url}")
                initial_url = current_url
            else:
                pass
                # logging.debug(f"  URLが変化していません。待機中... (試行{retry_count}/{max_retries})")
        
        # 最終的なURLを返す
        final_url = driver.current_url
        if final_url == original_url:
            pass
            # logging.warning(f"  ⚠ URLが変化しませんでした（JavaScriptリダイレクトが発生しなかった可能性）")
        
        return final_url
        
    except Exception as e:
        logging.error(f"URL取得エラー ({original_url}): {e}")
        return None

def find_googlemap_column(headers, sample_row=None):
    """
    GoogleマップURLの列名を探す
    """
    # 1. 列名から探す
    possible_names = ['GoogleMap', 'googlemap', 'Google Map', 'google_map', 'URL', 'url', 'GoogleマップURL', 'link', 'Link']
    
    for name in possible_names:
        if name in headers:
            return name
    
    # 2. 部分一致で探す
    for header in headers:
        header_lower = header.lower()
        if 'google' in header_lower and ('map' in header_lower or 'url' in header_lower):
            return header
        # urlやlinkという文字が含まれる列を探す
        if 'url' in header_lower or 'link' in header_lower:
            return header
    
    # 3. データ内容から判定（sample_rowがある場合）
    if sample_row:
        for header in headers:
            value = sample_row.get(header, '')
            if value and isinstance(value, str):
                # google.com を含むかチェック
                if 'google.com' in value:
                    logging.info(f"  列 '{header}' の内容からGoogleマップURLと判定しました")
                    return header
    
    return None

def find_gid_column(headers):
    """
    施設GIDの列名を探す
    """
    possible_names = ['施設GID', 'GID', 'gid', '施設gid', 'facility_gid']
    
    for name in possible_names:
        if name in headers:
            return name
    
    # 部分一致で探す
    for header in headers:
        if 'gid' in header.lower():
            return header
    
    return None

def find_id_column(headers):
    """
    施設IDの列名を探す
    """
    possible_names = ['施設ID', 'ID', 'id', '施設id', 'facility_id', 'post_id']
    
    for name in possible_names:
        if name in headers:
            return name
    
    # 部分一致で探す
    for header in headers:
        if header.lower() in ['id', '施設id']:
            return header
    
    return None

def process_single_url(row, googlemap_col, id_col, gid_col, delay):
    """
    1つのURLを処理する（並列実行用）
    """
    facility_id = row.get(id_col, '') if id_col else ''
    facility_gid = row.get(gid_col, '') if gid_col else ''
    original_url = row.get(googlemap_col, '')
    
    if not original_url:
        return None
        
    driver = None
    try:
        driver = setup_driver()
        
        # URLにアクセスしてリダイレクト後のURLを取得
        redirected_url = get_redirected_url(driver, original_url)
        
        if not redirected_url:
            logging.warning(f"  ✗ URLの取得に失敗 (ID: {facility_id})")
            return None
        
        # FIDを抽出
        fid = extract_fid_from_url(redirected_url)
        
        # GIDを抽出（既存のGIDがない場合、またはURLから抽出を優先する場合）
        final_gid = facility_gid  # デフォルトは既存のGID
        try:
            extracted_gid = extract_gid_from_url(redirected_url)
            # URLから抽出したものを優先、なければ既存の値を使用
            if extracted_gid:
                final_gid = extracted_gid
        except Exception as e:
            logging.debug(f"  GID抽出でエラー (ID: {facility_id}): {e}")
            # エラーが発生しても既存のGIDを使うので処理は継続
        
        if fid:
            gid_info = f" GID: {final_gid}" if final_gid else ""
            logging.info(f"  ✓ FID抽出成功: {fid}{gid_info} (ID: {facility_id})")
            return {
                '施設ID': facility_id,
                '施設GID': final_gid if final_gid else '',
                '施設FID': fid
            }
        else:
            logging.warning(f"  ✗ FIDの抽出に失敗 (ID: {facility_id})")
            return None
            
    except Exception as e:
        logging.error(f"エラー (ID: {facility_id}): {e}")
        return None
    finally:
        if driver:
            driver.quit()

def process_csv(input_file, output_file, max_workers=4, delay=2, limit=None):
    """
    CSVファイルを処理してFIDを抽出（並列処理対応）
    """
    logging.info(f"入力ファイル: {input_file}")
    logging.info(f"出力ファイル: {output_file}")
    logging.info(f"並列数: {max_workers}")
    
    results = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        
        # 全行を読み込む
        rows = list(reader)
        
        if not rows:
            error_msg = "CSVファイルにデータがありません"
            logging.error(f"❌ {error_msg}")
            
            # GitHub Issueを作成
            create_github_issue(
                title="[extract_fid_from_urls.py] CSVファイルが空です",
                body=f"""## エラー内容\n\nCSVファイルにデータ行がありません。\n\n### ファイル情報\n\n- **入力ファイル**: `{input_file}`\n- **ヘッダー**: {headers}\n\n### 対応方法\n\n1. CSVファイルにヘッダー行とデータ行が含まれているか確認してください\n2. ファイルが破損していないか確認してください\n\n---\n\n*このIssueは自動生成されました*
""",
                labels=["bug", "data-error", "automated"]
            )
            
            sys.exit(1)
        
        # 必須列のバリデーション
        googlemap_col, id_col, gid_col, error_msg = validate_required_columns(headers, rows, input_file)
        
        if error_msg:
            # エラーメッセージは既に表示され、Issueも作成済み
            sys.exit(1)
        
        logging.info(f"使用する列:")
        logging.info(f"  - 施設ID列: {id_col}")
        logging.info(f"  - 施設GID列: {gid_col}")
        logging.info(f"  - GoogleマップURL列: {googlemap_col}")
        
        total = len(rows)
        
        if limit:
            rows = rows[:limit]
            logging.info(f"テストモード: {limit}件に制限")
        
        logging.info(f"処理件数: {len(rows)}件 / 全{total}件")
        
        # 重複チェック用のセット
        processed_urls = set()
        unique_rows = []
        
        for idx, row in enumerate(rows, 1):
            original_url = row.get(googlemap_col, '')
            if not original_url:
                continue
            
            if original_url in processed_urls:
                continue
            
            processed_urls.add(original_url)
            unique_rows.append(row)
            
        logging.info(f"重複除外後の件数: {len(unique_rows)}件")
        
        # 並列処理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for row in unique_rows:
                futures.append(executor.submit(process_single_url, row, googlemap_col, id_col, gid_col, delay))
            
            completed = 0
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
                
                completed += 1
                if completed % 10 == 0:
                    logging.info(f"進捗: {completed}/{len(unique_rows)} ({(completed/len(unique_rows))*100:.1f}%)")
    
    # 結果を出力
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['施設ID', '施設GID', '施設FID'])
        writer.writeheader()
        if results:
            writer.writerows(results)
    
    logging.info("="*60)
    if results:
        logging.info(f"✓ 処理完了: {len(results)}件のFIDを抽出")
    else:
        logging.warning("⚠ FIDを抽出できませんでした（0件）")
    
    logging.info(f"✓ 出力ファイル: {output_file}")
    logging.info("="*60)

def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(description='GoogleマップURLからFIDを抽出')
    parser.add_argument('--input', '-i', required=True, help='入力CSVファイル')
    parser.add_argument('--output', '-o', help='出力CSVファイル')
    parser.add_argument('--delay', '-d', type=int, default=2, help='待機時間')
    parser.add_argument('--limit', '-l', type=int, help='最大件数')
    parser.add_argument('--workers', '-w', type=int, default=4, help='並列数（デフォルト: 4）')
    
    args = parser.parse_args()
    
    # 入力ファイルのパスを設定
    if os.path.isabs(args.input):
        input_file = args.input
    else:
        if args.input.startswith('results/'):
            input_file = args.input
        else:
            input_file = os.path.join('results', args.input)
    
    if not os.path.exists(input_file):
        logging.error(f"入力ファイルが見つかりません: {input_file}")
        return
    
    # 出力ファイルのパスを設定
    if args.output:
        output_file = args.output
    else:
        output_file = 'results/extracted_fid.csv'
    
    # 出力ディレクトリを作成
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    logging.info("="*60)
    logging.info("FID抽出処理開始（並列モード）")
    logging.info("="*60)
    
    try:
        process_csv(input_file, output_file, args.workers, args.delay, args.limit)
    except Exception as e:
        logging.error(f"エラーが発生しました: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
