#!/usr/bin/env python3
"""
BrightData APIからレビューを取得し、
settings.jsonのreview_fileに記載されているレビューGIDと照合するスクリプト
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
from collections import defaultdict
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed

# パス設定
BASE_DIR = Path(__file__).parent  # このファイルがあるディレクトリ (/workspaces/googlemap)
RESULTS_DIR = BASE_DIR / 'results'
SETTINGS_DIR = BASE_DIR / 'settings'

# 設定ファイル（環境変数で指定可能、デフォルトはsettings.json）
CONFIG_FILE = os.getenv('CONFIG_FILE', 'settings/settings.json')
print(f"🚀 Starting with CONFIG_FILE: {CONFIG_FILE}")
SETTINGS_JSON = BASE_DIR / CONFIG_FILE if not Path(CONFIG_FILE).is_absolute() else Path(CONFIG_FILE)
if not SETTINGS_JSON.exists():
    # フォールバック: settings/settings.json
    print(f"⚠️ Config file not found at {SETTINGS_JSON}, falling back to settings/settings.json")
    SETTINGS_JSON = SETTINGS_DIR / 'settings.json'

# グローバル変数（settings.jsonから読み込む）
FID_CSV = None
ZONE_NAME = None

# TEST_MODEの場合はfid_test.csvを使用（設定ファイルの値を上書き）
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'

# 処理範囲の設定（並列処理用）
START_LINE = int(os.getenv('START_LINE', '0')) if os.getenv('START_LINE') else None
PROCESS_COUNT = int(os.getenv('PROCESS_COUNT', '0')) if os.getenv('PROCESS_COUNT') else None

# API設定
API_ENDPOINT = 'https://api.brightdata.com/request'
API_TOKEN = os.getenv('BRIGHTDATA_API_TOKEN')
TIMEOUT = 120  # 2分
MAX_WORKERS = int(os.getenv('MAX_WORKERS', '10'))  # 並列処理数（環境変数から取得可能）
BATCH_SIZE = 50  # バッチサイズ

# Gemini API設定
# === 🚀 パフォーマンス最適化のため、Gemini機能を一時的に無効化 ===
# 有効化する場合は下記の行のコメントを外してください
GEMINI_API_KEY = None  # os.getenv('GEMINI_API_KEY')  # ← 有効化: os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = None
print('⚠️  Gemini API機能は無効化されています（パフォーマンス最適化のため）')

# === 元のコード（Gemini有効時） ===
# GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
# GEMINI_MODEL = None
# if GEMINI_API_KEY:
#     genai.configure(api_key=GEMINI_API_KEY)
#     GEMINI_MODEL = genai.GenerativeModel('gemini-2.0-flash')
#     print('✅ Gemini API が有効化されました（AI要約機能を使用できます）')
# else:
#     print('⚠️  GEMINI_API_KEY が設定されていません（AI要約機能は無効）')

# 正規表現パターン
FID_RE = re.compile(r'0x[0-9a-f]+:0x[0-9a-f]+', re.IGNORECASE)


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
            print(f"✅ GitHub Issueを作成しました: {issue_url}")
            return True
        else:
            logging.error(f"❌ GitHub Issue作成失敗: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logging.error(f"❌ GitHub Issue作成中にエラー: {e}")
        return False


def setup_logging():
    """ログ設定を初期化"""
    log_dir = RESULTS_DIR / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file_path = log_dir / 'app.log'
    
    # 既存のハンドラーをクリア（複数回実行時の重複を防止）
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # ログファイルを初期化（上書きモード）
    logging.basicConfig(filename=str(log_file_path), filemode='w', level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(message)s')


def load_settings(task_name_filter=None):
    """settings.jsonを読み込み、FIDファイルとゾーン名を設定
    
    Args:
        task_name_filter: 指定した場合、そのタスク名のみをフィルタリング
    """
    global FID_CSV, ZONE_NAME
    
    print(f'📄 Using config file: {SETTINGS_JSON}')
    
    if not SETTINGS_JSON.exists():
        error_msg = f'Settings file not found: {SETTINGS_JSON}'
        print(f'❌ {error_msg}')
        
        # GitHub Issue作成
        create_github_issue(
            title="[reviews_BrightData_50.py] settings.json未検出エラー",
            body=f"""## エラー内容

設定ファイルが見つかりません。

### エラー詳細

```
{error_msg}
```

### ファイル情報

- **期待されるパス**: `{SETTINGS_JSON}`
- **フォールバックパス**: `settings/settings.json`

### 必須ファイル

`reviews_BrightData_50.py`を実行するには、`settings/settings.json`が必要です。

**設定ファイルの形式:**
```json
[
  {{
    "task_name": "dental_review",
    "base_query": "歯医者",
    "fid_file": "results/fid.csv",
    "review_file": "results/dental_review.csv",
    "zone_name": "serp_api1"
  }}
]
```

### 対応方法

1. `settings/settings.json`ファイルを作成してください
2. 上記の形式でタスク設定を追加してください
3. ファイルパスが正しいか確認してください

---

*このIssueは自動生成されました*
""",
            labels=["bug", "config-error", "automated"]
        )
        
        return []
    
    with open(SETTINGS_JSON, 'r', encoding='utf-8') as f:
        settings = json.load(f)
    
    # タスク名でフィルタリング
    if task_name_filter:
        settings = [task for task in settings if task.get('task_name') == task_name_filter]
        if not settings:
            print(f'❌ Task "{task_name_filter}" not found in settings.json')
            print(f'Available tasks:')
            with open(SETTINGS_JSON, 'r', encoding='utf-8') as f:
                all_tasks = json.load(f)
                for task in all_tasks:
                    print(f'  - {task.get("task_name", "Unnamed")}')
            return []
        print(f'✅ Selected task: {task_name_filter}')
    else:
        print(f'✅ Loaded {len(settings)} task(s) from settings.json')
    
    # 最初のタスクからfid_fileとzone_nameを読み込む
    if settings and len(settings) > 0:
        first_task = settings[0]
        
        # FIDファイルの設定
        # 優先順位: 1. TEST_MODE, 2. FID_FILE_OVERRIDE環境変数, 3. settings.json
        if TEST_MODE:
            FID_CSV = RESULTS_DIR / 'fid_test.csv'
            print(f'🧪 TEST MODE: Using {FID_CSV}')
        else:
            # 環境変数でFIDファイルを上書き可能
            fid_file_override = os.getenv('FID_FILE_OVERRIDE')
            if fid_file_override:
                FID_CSV = BASE_DIR / fid_file_override if not Path(fid_file_override).is_absolute() else Path(fid_file_override)
                print(f'🔄 FID file (override): {FID_CSV}')
            else:
                fid_file = first_task.get('fid_file', 'results/fid_marrigge.csv')
                FID_CSV = BASE_DIR / fid_file
                print(f'📁 FID file: {FID_CSV}')
        
        # ゾーン名の設定
        ZONE_NAME = first_task.get('zone_name', 'serp_api1')
        print(f'🌐 Zone name: {ZONE_NAME}')
    
    return settings


def find_fid_column(headers, sample_rows):
    """
    FID列を自動検出する
    
    Args:
        headers: 列名のリスト
        sample_rows: サンプル行データのリスト（最大5行）
    
    Returns:
        FID列名、またはNone
    """
    # 1. 列名から探す（優先）
    possible_names = ['施設FID', 'FID', 'fid', 'Facility FID', 'facility_fid']
    for name in possible_names:
        if name in headers:
            print(f'  ✅ 列名 "{name}" からFID列を検出しました')
            return name
    
    # 2. データ内容から判定（FIDパターン: 0x[0-9a-f]+:0x[0-9a-f]+）
    fid_pattern = re.compile(r'0x[0-9a-f]+:0x[0-9a-f]+', re.IGNORECASE)
    
    for header in headers:
        fid_count = 0
        for row in sample_rows:
            value = row.get(header, '')
            if value and isinstance(value, str) and fid_pattern.match(value):
                fid_count += 1
        
        # サンプル行の50%以上がFIDパターンにマッチしたら、その列をFID列とする
        if fid_count >= len(sample_rows) * 0.5:
            print(f'  ✅ 列 "{header}" の内容からFID列を検出しました（{fid_count}/{len(sample_rows)}行がFIDパターン）')
            return header
    
    return None


def load_fid_csv():
    """fid.csvを読み込む (施設ID, 施設GID, 施設FID) - 重複を削除"""
    if not FID_CSV.exists():
        error_msg = f'FID CSV not found: {FID_CSV}'
        print(f'❌ {error_msg}')
        
        # GitHub Issue作成
        create_github_issue(
            title="[reviews_BrightData_50.py] FID CSVファイル未検出エラー",
            body=f"""## エラー内容

FIDデータを含むCSVファイルが見つかりません。

### エラー詳細

```
{error_msg}
```

### ファイル情報

- **期待されるFIDファイル**: `{FID_CSV}`

### 必須データ

`reviews_BrightData_50.py`を実行するには、FIDデータを含むCSVファイルが必要です。

**必須列:**
- **施設FID** (必須): `施設FID`, `FID`, `fid`
  - 形式: `0x123abc:0x456def`
- **施設ID** (推奨): `施設ID`, `ID`, `facility_id`
- **施設GID** (推奨): `施設GID`, `GID`, `facility_gid`

### 対応方法

1. GoogleマップURLからFID列を含むCSVを作成してください
2. または、既存のFIDファイルを `{FID_CSV}` に配置してください
3. ファイルが正しい場所にあるか確認してください

---

*このIssueは自動生成されました*
""",
            labels=["bug", "data-error", "automated"]
        )
        
        return []
    
    entries = []
    seen_fids = set()
    duplicates = 0
    
    # 全行をメモリに読み込む
    all_rows = []
    with open(FID_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        print(f'📋 CSV Headers: {headers}')
        
        for row in reader:
            all_rows.append(row)
    
    if not all_rows:
        print(f'❌ Error: CSV file is empty')
        return []
    
    # サンプル行から列を自動検出（最初の5行）
    sample_rows = all_rows[:5]
    
    # FID列を自動検出
    fid_column = find_fid_column(headers, sample_rows)
    if not fid_column:
        print(f'❌ Error: FID column not found in CSV')
        print(f'   Available columns: {headers}')
        print(f'   Expected FID pattern: 0x[0-9a-f]+:0x[0-9a-f]+ (e.g., 0x123abc:0x456def)')
        return []
    
    # ID/GID列も自動検出
    id_column = None
    for name in ['施設ID', 'ID', 'id', 'Facility ID', 'facility_id']:
        if name in headers:
            id_column = name
            break
    
    gid_column = None
    for name in ['施設GID', 'GID', 'gid', 'Facility GID', 'facility_gid']:
        if name in headers:
            gid_column = name
            break
    
    # 全行を処理
    for row in all_rows:
        # 検出された列から値を取得
        fid = row.get(fid_column)
        facility_id = row.get(id_column) if id_column else ''
        gid = row.get(gid_column, '') if gid_column else ''
        
        if not fid:
            continue
            
        if fid in seen_fids:
            duplicates += 1
            continue
        
        seen_fids.add(fid)
        entries.append({
            'facility_id': facility_id or '',
            'gid': gid,
            'fid': fid
        })
    
    print(f'✅ Loaded {len(entries)} unique entries from {FID_CSV.name} (removed {duplicates} duplicates)')
    
    # 処理範囲の適用（並列処理用）
    if START_LINE is not None or PROCESS_COUNT is not None:
        start_idx = (START_LINE - 1) if START_LINE else 0  # 1-based to 0-based
        end_idx = start_idx + PROCESS_COUNT if PROCESS_COUNT else len(entries)
        original_count = len(entries)
        entries = entries[start_idx:end_idx]
        print(f'📊 Processing range: lines {start_idx + 1} to {min(end_idx, original_count)} ({len(entries)} facilities)')
        print(f'   Original total: {original_count} facilities')
    
    if len(entries) == 0:
        print(f'❌ Error: No valid data found in specified range')
        print(f'   File: {FID_CSV}')
        print(f'   File exists: {FID_CSV.exists()}')
        print(f'   CSV Headers: {headers}')
        if START_LINE or PROCESS_COUNT:
            print(f'   Start line: {START_LINE}, Process count: {PROCESS_COUNT}')
        print(f'   Please check the file contains valid FID data')
        sys.exit(1)
    
    return entries


def load_existing_reviews(review_file_path):
    """既存のreview_fileを読み込む（ファイルがなければ新規作成）"""
    if not review_file_path.exists():
        print(f'⚠️  Review file not found: {review_file_path}')
        print(f'   新規ファイルを作成します')
        
        # 新規ファイルをヘッダー付きで作成
        try:
            with open(review_file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['レビューID', '施設ID', '施設GID', 'レビュワー評価', 'レビュワー名', 
                               'レビュー日時', 'レビュー本文', 'レビュー要約', 'レビューGID'])
            print(f'✅ 新規ファイルを作成しました: {review_file_path}')
        except Exception as e:
            print(f'❌ ファイル作成に失敗: {e}')
            return [], set(), 100
        
        return [], set(), 100
    
    reviews = []
    gid_set = set()
    max_review_id = 100
    
    with open(review_file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        # 施設GID列がない場合の後方互換性チェック
        has_facility_gid = '施設GID' in fieldnames if fieldnames else False
        if not has_facility_gid:
            print('⚠️  既存レビューファイルに施設GID列がありません。空列として扱います。')
        
        for row in reader:
            # 施設GID列がない場合は空文字列を追加
            if not has_facility_gid:
                row['施設GID'] = ''
            reviews.append(row)
            gid = row.get('レビューGID', '').strip()
            if gid:
                gid_set.add(gid)
            
            # 最大レビューIDを取得
            try:
                review_id_str = row.get('レビューID', '0')
                if review_id_str:
                    review_id = int(review_id_str)
                    if review_id > max_review_id:
                        max_review_id = review_id
            except ValueError:
                pass
            except (ValueError, TypeError):
                pass
    
    print(f'✅ Loaded {len(reviews)} existing reviews')
    print(f'   Unique GIDs: {len(gid_set)}')
    print(f'   Max Review ID: {max_review_id}')
    return reviews, gid_set, max_review_id


def fetch_reviews_from_api(fid, facility_id, gid, max_reviews=50):
    """BrightData APIからレビューを取得（ページネーション対応）"""
    if not API_TOKEN:
        error_msg = 'BRIGHTDATA_API_TOKEN environment variable not set'
        print(f'❌ {error_msg}')
        
        # GitHub Issue作成
        create_github_issue(
            title="[reviews_BrightData_50.py] BRIGHTDATA_API_TOKEN未設定エラー",
            body=f"""## エラー内容

`reviews_BrightData_50.py`の実行に必要なAPIトークンが設定されていません。

### エラー詳細

```
{error_msg}
```

### 必須環境変数

- **BRIGHTDATA_API_TOKEN**: BrightData APIのアクセストークン

### 対応方法

1. BrightDataのダッシュボードからAPIトークンを取得してください
2. 環境変数に設定してください:
   ```bash
   export BRIGHTDATA_API_TOKEN="your_token_here"
   ```
3. GitHub Actionsの場合は、Secretsに `BRIGHTDATA_API_TOKEN` を設定してください

---

*このIssueは自動生成されました*
""",
            labels=["bug", "config-error", "automated"]
        )
        
        return None
    
    headers = {
        'Authorization': f'Bearer {API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    print(f'  📡 Fetching reviews for FID: {fid} (target: {max_reviews} reviews)')
    
    all_reviews = []
    page = 0
    reviews_per_page = 10  # Googleは通常10件ずつ返す
    
    while len(all_reviews) < max_reviews:
        start = page * reviews_per_page
        
        # レビューURLを構築（startパラメータでページネーション）
        url = f'https://www.google.com/reviews?fid={fid}&start={start}&sort=newestFirst&hl=ja&brd_json=1'

        
        payload = {
            'zone': ZONE_NAME,
            'url': url,
            'format': 'json'
        }
        
        try:
            response = requests.post(
                API_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=TIMEOUT
            )
            
            if response.status_code != 200:
                print(f'  ❌ HTTP {response.status_code} at page {page+1}')
                break
            
            # レスポンスをJSONとしてパース
            try:
                response_json = response.json()
            except json.JSONDecodeError as e:
                print(f'  ❌ Failed to parse response as JSON: {e}')
                break
            
            if not response_json:
                print(f'  ⚠️  Empty response at page {page+1}')
                break
            
            # bodyを取得
            body = response_json.get('body')
            if not body:
                print(f'  ⚠️  No body in response at page {page+1}')
                break
            
            # bodyが辞書ならそのまま使用、文字列ならパース
            if isinstance(body, str):
                # Google安全プレフィックスを削除
                if body.startswith(")]}',"):
                    body = body[5:]
                try:
                    parsed_body = json.loads(body)
                except json.JSONDecodeError as e:
                    print(f'  ❌ Failed to parse body as JSON: {e}')
                    break
            else:
                parsed_body = body
            
            # レビューを抽出
            page_reviews = extract_reviews_from_response(parsed_body)
            
            if not page_reviews:
                print(f'  ℹ️  No more reviews at page {page+1}')
                break
            
            all_reviews.extend(page_reviews)
            print(f'  ✅ Page {page+1}: {len(page_reviews)} reviews fetched (total: {len(all_reviews)})')
            
            # これ以上取得する必要がない場合は終了
            if len(page_reviews) < reviews_per_page:
                print(f'  ℹ️  Reached last page (got {len(page_reviews)} < {reviews_per_page})')
                break
            
            page += 1
            
            # === 🚀 API制限を考慮した待機時間（パフォーマンス最適化のため無効化） ===
            # 必要に応じて下記のコメントを外してください
            # time.sleep(0.1)
            
        except requests.exceptions.Timeout:
            print(f'  ⏱️  Request timeout at page {page+1}')
            break
        except Exception as e:
            print(f'  ❌ Error at page {page+1}: {e}')
            break
    
    if not all_reviews:
        return None
    
    # 最大件数でトリム
    if len(all_reviews) > max_reviews:
        all_reviews = all_reviews[:max_reviews]
        print(f'  📊 Trimmed to {max_reviews} reviews')
    
    print(f'  📊 Total reviews fetched: {len(all_reviews)}')
    return all_reviews


def extract_reviews_from_response(response_data):
    """
    BrightData APIレスポンスからレビュー情報を抽出
    successful_responses.jsonの構造に基づく: body.reviews[]
    """
    reviews = []
    
    try:
        # レスポンスの構造: {reviews: [...]}
        if isinstance(response_data, dict) and 'reviews' in response_data:
            reviews = response_data['reviews']
            if not isinstance(reviews, list):
                print(f'  ⚠️  reviews is not a list: {type(reviews)}')
                return []
        else:
            print(f'  ⚠️  No reviews key in response')
            return []
        
        return reviews
    except Exception as e:
        print(f'  ❌ Error extracting reviews: {e}')
        return []


def extract_review_data(review_item):
    """
    レビューアイテムからデータを抽出
    successful_responses.jsonの構造に基づく:
    {review_id, reviewer: {display_name, ...}, rating, created, comment, ...}
    """
    try:
        if not isinstance(review_item, dict):
            return None
        
        # review_id
        review_id = review_item.get('review_id', '')
        
        # reviewer情報
        reviewer = review_item.get('reviewer', {})
        reviewer_name = reviewer.get('display_name', '') if isinstance(reviewer, dict) else ''
        
        # rating (例: "5/5")
        rating_str = review_item.get('rating', '')
        rating = None
        if rating_str and '/' in rating_str:
            try:
                rating = float(rating_str.split('/')[0])
            except (ValueError, IndexError):
                rating = None
        
        # created (例: "9 months ago")
        created = review_item.get('created', '')
        
        # comment (レビューテキスト)
        text = review_item.get('comment', '')
        
        return {
            'review_id': review_id,
            'facility_id': '',  # process_single_facility で設定される
            'facility_gid': '',  # process_single_facility で設定される
            'reviewer_name': reviewer_name,
            'rating': rating,
            'timestamp': created,
            'text': text
        }
    
    except Exception as e:
        print(f'  ⚠️  Failed to extract review data: {e}')
        return None


def summarize_reviews_with_gemini(reviews):
    """
    Gemini APIを使用してレビューを要約
    複数のレビューを施設ごとにまとめて要約する
    """
    if not GEMINI_MODEL:
        return None
    
    if not reviews:
        return None
    
    # レビューテキストを結合（最大10件まで）
    review_texts = []
    for review in reviews[:10]:
        text = review.get('text', '').strip()
        rating = review.get('rating', '')
        if text:
            review_texts.append(f"[評価: {rating}] {text}")
    
    if not review_texts:
        return None
    
    combined_text = "\n\n".join(review_texts)
    
    # プロンプト作成
    prompt = f"""以下は同じ施設に対する複数のレビューです。これらのレビューを分析し、3-5文で簡潔に要約してください。

要約には以下を含めてください：
1. 全体的な評価の傾向（良い点・悪い点）
2. 頻繁に言及される特徴やサービス
3. 顧客満足度の主な要因

レビュー:
{combined_text}

要約:"""
    
    try:
        response = GEMINI_MODEL.generate_content(prompt)
        summary = response.text.strip()
        return summary
    
    except Exception as e:
        print(f'  ⚠️  Gemini要約エラー: {e}')
        return None


def match_reviews_with_existing(fetched_reviews, existing_gid_set, facility_id, facility_gid, next_review_id):
    """取得したレビューと既存のGIDセットを照合"""
    new_reviews = []
    skipped = 0
    current_id = next_review_id
    
    for review in fetched_reviews:
        review_gid = review.get('review_id', '')
        
        if review_gid in existing_gid_set:
            # 既存のレビューGIDと一致する場合はスキップ
            skipped += 1
        else:
            # 新規レビューとして追加
            new_reviews.append({
                'assigned_review_id': current_id,
                'facility_id': facility_id,
                'facility_gid': facility_gid,
                'reviewer_name': review.get('reviewer_name', ''),
                'rating': review.get('rating', ''),
                'timestamp': review.get('timestamp', ''),
                'text': review.get('text', ''),
                'review_gid': review_gid
            })
            current_id += 1
    
    return new_reviews, skipped, current_id


def save_reviews_to_csv(csv_file_path, reviews, facility_summaries=None):
    """
    レビューをCSVファイルに保存（既存レビュー辞書と新規レビュー辞書の両方に対応）
    facility_summaries: {facility_id: summary_text} の辞書（オプション）
    """
    if not reviews:
        return
    
    # CSVヘッダー
    fieldnames = ['レビューID', '施設ID', '施設GID', 'レビュワー評価', 'レビュワー名', 
                  'レビュー日時', 'レビュー本文', 'レビュー要約', 'レビューGID']
    
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for review in reviews:
            # 既存レビュー（CSVから読み込んだもの）と新規レビュー（APIから取得したもの）の両方に対応
            if 'assigned_review_id' in review:
                # 新規レビュー
                facility_id = review.get('facility_id', '')
                
                # 施設ごとの要約を取得（存在する場合）
                summary = 'AI要約は停止中'
                if facility_summaries and facility_id in facility_summaries:
                    summary = facility_summaries[facility_id]
                
                writer.writerow({
                    'レビューID': review.get('assigned_review_id', ''),
                    '施設ID': facility_id,
                    '施設GID': review.get('facility_gid', ''),
                    'レビュワー評価': review.get('rating', ''),
                    'レビュワー名': review.get('reviewer_name', ''),
                    'レビュー日時': review.get('timestamp', ''),
                    'レビュー本文': review.get('text', ''),
                    'レビュー要約': summary,
                    'レビューGID': review.get('review_gid', '')
                })
            else:
                # 既存レビュー
                facility_id = review.get('施設ID', '')
                
                # 要約が生成されている場合は更新、なければ既存の値を保持
                summary = review.get('レビュー要約', '')
                if facility_summaries and facility_id in facility_summaries:
                    summary = facility_summaries[facility_id]
                
                writer.writerow({
                    'レビューID': review.get('レビューID', ''),
                    '施設ID': facility_id,
                    '施設GID': review.get('施設GID', ''),
                    'レビュワー評価': review.get('レビュワー評価', ''),
                    'レビュワー名': review.get('レビュワー名', ''),
                    'レビュー日時': review.get('レビュー日時', ''),
                    'レビュー本文': review.get('レビュー本文', ''),
                    'レビュー要約': summary,
                    'レビューGID': review.get('レビューGID', '')
                })


def process_single_facility(entry, existing_gid_set):
    """1施設の処理（並列実行用）"""
    facility_id = entry['facility_id']
    gid = entry['gid']
    fid = entry['fid']
    
    result = {
        'facility_id': facility_id,
        'gid': gid,
        'success': False,
        'fetched_reviews': [],
        'new_reviews': [],
        'skipped': 0,
        'summary': None
    }
    
    try:
        # APIからレビューを取得（最大50件）
        review_items = fetch_reviews_from_api(fid, facility_id, gid, max_reviews=50)
        
        if not review_items:
            print(f'[{facility_id}] ❌ API取得失敗')
            return result
        
        # レビューデータを抽出
        fetched_reviews = []
        for item in review_items:
            review_data = extract_review_data(item)
            if review_data:
                # 施設IDとGIDをレビューデータに設定
                review_data['facility_id'] = facility_id
                review_data['facility_gid'] = gid
                fetched_reviews.append(review_data)
        
        if not fetched_reviews:
            print(f'[{facility_id}] ❌ データ抽出失敗')
            return result
        
        result['fetched_reviews'] = fetched_reviews
        result['success'] = True
        
        # === 🚀 Gemini要約を生成（パフォーマンス最適化のため無効化） ===
        # 有効化する場合は下記のコメントを外してください
        # if GEMINI_MODEL and fetched_reviews:
        #     reviews_for_summary = fetched_reviews[:10]
        #     summary = summarize_reviews_with_gemini(reviews_for_summary)
        #     result['summary'] = summary if summary else '要約生成失敗（Gemini APIエラー）'
        #     print(f'[{facility_id}] ✅ {len(fetched_reviews)}件取得、要約生成完了')
        # else:
        #     print(f'[{facility_id}] ✅ {len(fetched_reviews)}件取得')
        
        # 無効化時の処理
        print(f'[{facility_id}] ✅ {len(fetched_reviews)}件取得')
        
        return result
        
    except Exception as e:
        print(f'[{facility_id}] ❌ エラー: {e}')
        return result


def process_task(task, fid_entries):
    """1つのタスクを処理"""
    task_name = task.get('task_name', 'unknown')
    review_file = task.get('review_file', '')
    update_review_path = task.get('update_review_path', '')  # ★ 増分ファイルパスを取得
    
    print(f'\n{"="*80}')
    print(f'タスク: {task_name}')
    print(f'レビューファイル: {review_file}')
    print(f'増分レビューファイル: {update_review_path}')
    print(f'並列処理数: {MAX_WORKERS}')
    print(f'{"="*80}\n')
    
    if not review_file:
        print('⚠️  review_fileが設定されていません')
        return
    
    # 既存のレビューを読み込み（ファイルがなければ新規作成）
    # パスが 'results/' で始まる場合は BASE_DIR からの相対パスとして扱う
    if review_file.startswith('results/'):
        review_file_path = BASE_DIR / review_file
    else:
        review_file_path = RESULTS_DIR / review_file
        
    existing_reviews, existing_gid_set, max_review_id = load_existing_reviews(review_file_path)
    next_review_id = max_review_id + 1
    
    if not existing_gid_set:
        print('⚠️  既存のレビューにGIDが設定されていません（新規ファイルまたは空ファイル）')
        print('   全てのレビューを新規として処理します')
    
    # 統計情報
    stats = {
        'total_facilities': 0,
        'total_fetched_reviews': 0,
        'new_reviews': 0,
        'skipped_reviews': 0,
        'new_reviews_list': [],
        'ai_summaries': 0
    }
    
    # 施設ごとのAI要約を保存
    facility_summaries = {}
    
    print(f'🚀 {len(fid_entries)}施設を並列処理開始...\n')
    
    # 並列処理で各施設を処理
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 全施設をサブミット
        future_to_entry = {executor.submit(process_single_facility, entry, existing_gid_set): entry for entry in fid_entries}
        
        completed = 0
        # 完了した順に処理
        for future in as_completed(future_to_entry):
            entry = future_to_entry[future]
            completed += 1
            
            try:
                result = future.result()
                
                if not result['success']:
                    continue
                
                facility_id = result['facility_id']
                gid = result['gid']
                fetched_reviews = result['fetched_reviews']
                
                stats['total_facilities'] += 1
                stats['total_fetched_reviews'] += len(fetched_reviews)
                
                # 既存のGIDと照合
                new_reviews, skipped, next_review_id = match_reviews_with_existing(
                    fetched_reviews, existing_gid_set, facility_id, gid, next_review_id
                )
                
                stats['new_reviews'] += len(new_reviews)
                stats['skipped_reviews'] += skipped
                stats['new_reviews_list'].extend(new_reviews)
                
                # 要約を保存
                if result['summary']:
                    facility_summaries[facility_id] = result['summary']
                    stats['ai_summaries'] += 1
                
                # 進捗表示
                if completed % 10 == 0:
                    print(f'\n📊 進捗: {completed}/{len(fid_entries)} 施設完了 (新規:{stats["new_reviews"]}件)\n')
                
                # 50施設ごとにCSVに保存（途中保存）
                if completed % 50 == 0 and stats['new_reviews_list']:
                    save_reviews_to_csv(review_file_path, existing_reviews + stats['new_reviews_list'], facility_summaries)
                    print(f'\n💾 途中保存: {len(stats["new_reviews_list"])}件\n')
                    
            except Exception as e:
                print(f'❌ 処理エラー: {e}')
    
    # レポート出力
    print(f'\n{"="*80}')
    print(f'📊 集計結果')
    print(f'{"="*80}')
    print(f'処理施設数: {stats["total_facilities"]}')
    print(f'取得レビュー総数: {stats["total_fetched_reviews"]}')
    print(f'新規レビュー: {stats["new_reviews"]}')
    print(f'スキップ（既存）: {stats["skipped_reviews"]}')
    # === Gemini要約統計（無効化中） ===
    # if GEMINI_MODEL:
    #     print(f'Gemini要約生成数: {stats["ai_summaries"]}')
    
    if stats['total_fetched_reviews'] > 0:
        new_rate = stats['new_reviews'] / stats['total_fetched_reviews'] * 100
        print(f'新規率: {new_rate:.1f}%')
    
    # 新規レビューの詳細
    if stats['new_reviews_list']:
        print(f'\n✅ 新規レビュー (最初の5件):')
        for review in stats['new_reviews_list'][:5]:
            print(f"  レビューID: {review['assigned_review_id']}")
            print(f"  施設ID: {review['facility_id']}")
            print(f"  レビューGID: {review['review_gid'][:40]}...")
            print(f"  レビュワー: {review['reviewer_name']}")
            print(f"  評価: {review['rating']}")
            print()
    
    # 結果をJSONに保存 (無効化)
    # output_file = RESULTS_DIR / f'{task_name}_match_result.json'
    # with open(output_file, 'w', encoding='utf-8') as f:
    #     json.dump({
    #         'task_name': task_name,
    #         'review_file': review_file,
    #         'statistics': {
    #             'total_facilities': stats['total_facilities'],
    #             'total_fetched_reviews': stats['total_fetched_reviews'],
    #             'new_reviews': stats['new_reviews'],
    #             'skipped_reviews': stats['skipped_reviews']
    #         },
    #         'new_reviews_list': stats['new_reviews_list']
    #     }, f, ensure_ascii=False, indent=2)
    
    # print(f'\n💾 結果を保存しました: {output_file}')
    
    # ★ 増分ファイル（update_review_path）に新規レビューのみを保存
    if update_review_path:
        try:
            if update_review_path.startswith('results/'):
                update_review_file_path = BASE_DIR / update_review_path
            else:
                update_review_file_path = RESULTS_DIR / update_review_path
                
            save_reviews_to_csv(update_review_file_path, stats['new_reviews_list'], facility_summaries)
            
            if stats['new_reviews_list']:
                print(f"💾 増分ファイル '{update_review_path}' に {len(stats['new_reviews_list'])} 件の新規レビューを書き込みました。")
            else:
                print(f"💾 増分ファイル '{update_review_path}' を作成しました（新規レビュー: 0件）。")
        except Exception as e:
            print(f"❌ 増分ファイル書き込み失敗: {e}")
    else:
        print("⚠️  増分ファイル(update_review_path)のパスが指定されていません。スキップします。")
    
    # レビューをCSVに保存（既存+新規）
    # 新規レビューがある、または要約が生成された場合に保存
    if stats['new_reviews_list'] or facility_summaries:
        all_reviews = existing_reviews + stats['new_reviews_list']
        save_reviews_to_csv(review_file_path, all_reviews, facility_summaries)
        print(f'💾 レビューをCSVに保存しました: {review_file_path} (既存:{len(existing_reviews)}件 + 新規:{len(stats["new_reviews_list"])}件 = 合計:{len(all_reviews)}件)')
        # === Gemini要約メッセージ（無効化中） ===
        # if GEMINI_MODEL and facility_summaries:
        #     print(f'🤖 Gemini要約: {len(facility_summaries)}施設の要約を生成しました')
    else:
        print(f'⚠️  新規レビューも要約もないため、CSVは更新されませんでした')


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description='BrightDataレビュー取得ツール')
    parser.add_argument('--config', default='settings/settings.json', help='設定ファイルのパス')
    parser.add_argument('--fid-file', type=str, help='FIDファイルのパス')
    parser.add_argument('--review-file', type=str, help='レビュー出力ファイルのパス')
    parser.add_argument('--task-name', type=str, help='処理するタスク名')
    parser.add_argument('--start-line', type=int, help='開始行番号 (1-based)')
    parser.add_argument('--process-count', type=int, help='処理件数')
    
    args = parser.parse_args()
    
    # グローバル変数を上書き
    global CONFIG_FILE, START_LINE, PROCESS_COUNT
    if args.config:
        CONFIG_FILE = args.config
    if args.start_line:
        START_LINE = args.start_line
    if args.process_count:
        PROCESS_COUNT = args.process_count
    
    print('='*80)
    print('レビュー取得・照合ツール')
    print('='*80)
    
    # ログ設定を初期化
    setup_logging()
    
    # タスク名のフィルタリング(コマンドライン引数 > 環境変数)
    task_name_filter = args.task_name or os.getenv('TASK_NAME')
    if task_name_filter:
        print(f'🎯 Task filter: {task_name_filter}')
    
    # 設定読み込み
    settings = load_settings(task_name_filter)
    if not settings:
        sys.exit(1)
    
    # コマンドライン引数でFIDファイルを上書き
    if args.fid_file:
        global FID_CSV
        FID_CSV = BASE_DIR / args.fid_file if not Path(args.fid_file).is_absolute() else Path(args.fid_file)
        print(f'🔄 FID file (command-line): {FID_CSV}')
    
    fid_entries = load_fid_csv()
    if not fid_entries:
        sys.exit(1)
    
    # 各タスクを処理
    for task in settings:
        # コマンドライン引数でレビューファイルを上書き
        if args.review_file:
            task['review_file'] = args.review_file
            print(f'🔄 Review file (command-line): {args.review_file}')
        
        try:
            process_task(task, fid_entries)
        except Exception as e:
            print(f'\n❌ エラーが発生しました: {e}')
            import traceback
            traceback.print_exc()
    
    print(f'\n{"="*80}')
    print('処理完了')
    print(f'{"="*80}')


if __name__ == '__main__':
    main()
