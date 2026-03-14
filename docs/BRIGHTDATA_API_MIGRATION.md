# BrightData API移行ガイド

## 概要

2024年12月6日、BrightDataから新しいスクレイパーAPIへの移行を推奨するメッセージを受け取りました。

**両方のAPI形式をサポート**し、環境変数 `USE_NEW_API` で切り替え可能です。

- **旧API (現在のデフォルト)**: Web Unlocker API - 動作確認済み
- **新API**: Google Maps full information - discover by location scraper (hl_40597452) - 準備中

> ⚠️ **注意**: 新しいスクレイパー (hl_40597452) は現在404エラー（dataset does not exist）が発生します。BrightDataアカウントでスクレイパーをアクティベートする必要があります。利用可能になったら `USE_NEW_API=true` で切り替えてください。

## API切り替え方法

環境変数 `USE_NEW_API` で切り替え:

```bash
# 旧APIを使用（現在のデフォルト）
python facility_BrightData_20.py

# または明示的に指定
export USE_NEW_API=false
python facility_BrightData_20.py

# 新しいAPIを使用（スクレイパーがアクティブな場合）
export USE_NEW_API=true
python facility_BrightData_20.py
```

## 移行理由

BrightDataからのメッセージ:
> "To do this will require using our Google Maps full information - discover by location scraper"

新しいスクレイパーの利点:
- `start`と`num`パラメータをサポート
- より多くの結果を取得可能
- ページネーションの信頼性向上

## 変更されたファイル

### Pythonスクリプト

1. **facility_BrightData_20.py**
   - APIエンドポイント: `https://api.brightdata.com/datasets/v3/trigger?dataset_id=hl_40597452`
   - ペイロード形式: `[{"query": "...", "start": 0, "num": 20, "language": "ja", "country": "jp"}]`
   - レスポンス処理: snapshot_id方式に対応

2. **facility_BrightData_20_update.py**
   - 同様の変更を適用

3. **facility_BrightData_heatmap.py**
   - 同様の変更を適用

4. **search_unmatched_37_facilities.py**
   - 同様の変更を適用
   - 新しいAPI形式のレスポンスから直接施設情報を抽出
   - 旧形式（APP_INITIALIZATION_STATE）も互換性のため維持

### collect_places関数の更新

新しいAPIのレスポンス形式に対応:

```python
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
```

## API仕様の比較

### 旧API (Web Unlocker)

```python
api_url = "https://api.brightdata.com/request"
payload = {
    "zone": zone_name,
    "url": "https://www.google.com/maps/search/...",
    "format": "json"
}
```

**レスポンス形式:**
```json
{
  "status_code": 200,
  "headers": {...},
  "body": "...JSON文字列または HTML..."
}
```

### 新API (Google Maps Scraper)

```python
scraper_id = "hl_40597452"
api_url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={scraper_id}"
payload = [{
    "query": "東京都 渋谷区 歯医者",
    "start": 0,
    "num": 20,
    "language": "ja",
    "country": "jp"
}]
```

**レスポンス形式 (非同期処理):**

1. トリガーレスポンス:
```json
{
  "snapshot_id": "abc123...",
  "status": "running"
}
```

2. スナップショット取得:
```
GET https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json
```

3. 最終データ:
```json
[
  {
    "title": "施設名",
    "address": "住所",
    "latitude": 35.xxx,
    "longitude": 139.xxx,
    "rating": 4.5,
    "reviews": 100,
    ...
  }
]
```

## レスポンス処理の変更

### snapshot_id方式の実装

```python
if isinstance(response_data, dict) and 'snapshot_id' in response_data:
    snapshot_id = response_data['snapshot_id']
    
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
```

## GitHub Actionsワークフロー

ワークフローファイルは変更不要です。以下のファイルで使用されるPythonスクリプトが自動的に新しいAPIを使用します:

- `.github/workflows/brightdata_facility.yml`
- `.github/workflows/brightdata_facility_heatmap.yml`
- `.github/workflows/search_unmatched_37.yml`

## テスト手順

1. 環境変数の確認:
```bash
echo $BRIGHTDATA_API_TOKEN
echo $USE_NEW_API  # 設定されていない場合は新APIがデフォルト
```

2. 新しいAPIのテスト:
```bash
# 新しいAPIを明示的に指定（デフォルトなので省略可能）
export USE_NEW_API=true
python test_brightdata_api.py
```

3. 旧APIのテスト（必要に応じて）:
```bash
export USE_NEW_API=false
python facility_BrightData_20.py
```

4. ログの確認:
```bash
cat results/logs/app.log
```

4. 結果の検証:
- `results/dental.csv` などの出力ファイルを確認
- 施設データが正しく取得されているか確認
- GID、FIDが正しく記録されているか確認

## 注意事項

### タイムアウト

新しいAPIは非同期処理のため、スナップショット取得に最大60秒かかります:

```python
for wait_attempt in range(12):  # 5秒x12回 = 60秒
    time.sleep(5)
    # ...
```

### リトライロジック

既存のリトライロジックは維持されています:

```python
max_retries = 5
for attempt in range(1, max_retries + 1):
    # ...
    delay = 2 ** attempt + random.uniform(0, 1)
    time.sleep(delay)
```

### エラーハンドリング

- スナップショット取得タイムアウト
- JSONパース失敗
- 認証エラー (401/403)
- ネットワークエラー

## トラブルシューティング

### スナップショットタイムアウト

**症状:** `ERROR: スナップショット取得タイムアウト`

**対処:**
- 待機時間を延長: `range(12)` → `range(24)` (120秒)
- クエリを簡略化

### 空のレスポンス

**症状:** `WARNING: 空の応答`

**対処:**
- クエリの形式を確認
- `language`と`country`パラメータが正しいか確認

### 認証エラー

**症状:** `ERROR: 認証エラー`

**対処:**
- `BRIGHTDATA_API_TOKEN`が正しいか確認
- スクレイパーIDが正しいか確認: `hl_40597452`

## 互換性

### 旧形式との互換性

`collect_places`関数は旧形式のレスポンス（`organic`キー）にも対応しているため、段階的な移行が可能です。

### データ形式の互換性

施設情報の抽出ロジックは以下のキーに対応:

- `title` / `name` → 施設名
- `address` / `vicinity` → 住所
- `latitude`, `longitude` / `location.latitude`, `location.longitude` → 座標
- `rating` / `avg_rating` → 評価
- `reviews` / `user_ratings_total` → レビュー数

## 参考リンク

- [BrightData Google Maps Scraper](https://brightdata.com/cp/scrapers/browse?domain=google.com&id=hl_40597452)
- [BrightData Datasets API Documentation](https://docs.brightdata.com/scraping-automation/datasets/api-reference)

## 互換性維持

すべてのスクリプトで新旧両方のAPIをサポート:

- `facility_BrightData_20.py`
- `facility_BrightData_20_update.py`
- `facility_BrightData_heatmap.py`
- `search_unmatched_37_facilities.py`

環境変数が設定されていない場合、**自動的に新しいAPIを使用**します。

## GitHub Actions での使用

ワークフローファイルで環境変数を設定:

```yaml
- name: Run facility scraper
  env:
    BRIGHTDATA_API_TOKEN: ${{ secrets.BRIGHTDATA_API_TOKEN }}
    USE_NEW_API: true  # または false
  run: |
    python facility_BrightData_20.py
```
## 新しいスクレイパーのアクティベーション方法

BrightDataで新しいスクレイパーを有効化:

1. [BrightData ダッシュボード](https://brightdata.com/cp/scrapers)にログイン
2. "Google Maps full information - discover by location" (ID: hl_40597452) を検索
3. スクレイパーをアクティベート
4. APIトークンに適切な権限があることを確認
5. `export USE_NEW_API=true` で新APIに切り替え

## 変更履歴

- 2024-12-06: 新しいBrightData APIへの移行準備
  - スクレイパーID: `hl_40597452` (準備中)
  - 4つのPythonスクリプトを更新
  - snapshot_id方式のレスポンス処理を実装
  - 新旧両方のAPIをサポート（環境変数 `USE_NEW_API` で切り替え）
  - デフォルトは旧API（新スクレイパーが利用可能になるまで）クリプトを更新
  - snapshot_id方式のレスポンス処理を実装
  - 新旧両方のAPIをサポート（環境変数 `USE_NEW_API` で切り替え）
  - デフォルトは新API
