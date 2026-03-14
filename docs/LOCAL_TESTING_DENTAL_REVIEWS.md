# Dental Reviews ローカルテストガイド

## 概要

`test_dental_reviews_local.sh` は、GitHub Actions ワークフロー `dental_new_reviews_sequential.yml` をローカル環境でテストするためのスクリプトです。

## 前提条件

### 必須

1. **BrightData API Token**
   ```bash
   export BRIGHTDATA_API_TOKEN='your_api_token_here'
   ```

2. **Python 環境**
   - Python 3.12+
   - `requests` ライブラリ
   ```bash
   pip install requests
   ```

3. **入力ファイル**
   - `dental_new.csv` (デフォルト)
   - GoogleMap列にリダイレクト後のURLが必要

### オプション

```bash
export BRIGHTDATA_DATASET_ID='gd_lkpb8cqr7v3twzxwp'  # デフォルト値
```

## 基本的な使い方

### 1. 通常実行（デフォルト設定）

```bash
export BRIGHTDATA_API_TOKEN='your_token'
./test_dental_reviews_local.sh
```

**デフォルト設定:**
- CSV_FILE: `dental_new.csv`
- OUTPUT_FILE: `results/dental_new_reviews.csv`
- DAYS_BACK: 10日
- BATCH_SIZE: 100施設
- CSV_BATCH_SIZE: 500行
- WAIT_BETWEEN_BATCHES: 60秒
- GENERATE_REPORT: true
- REPORT_DAYS: 10日

### 2. クイックテストモード（少量データでテスト）

```bash
export BRIGHTDATA_API_TOKEN='your_token'
export TEST_MODE='quick'
./test_dental_reviews_local.sh
```

**クイックモード設定:**
- CSV_BATCH_SIZE: 50行
- BATCH_SIZE: 10施設
- その他はデフォルト

### 3. カスタム設定

```bash
export BRIGHTDATA_API_TOKEN='your_token'
export CSV_FILE='test_dental.csv'
export OUTPUT_FILE='results/test_reviews.csv'
export DAYS_BACK=30
export BATCH_SIZE=50
export CSV_BATCH_SIZE=100
export WAIT_BETWEEN_BATCHES=30
export START_FROM_BATCH=1
export GENERATE_REPORT=true
export REPORT_DAYS=7
./test_dental_reviews_local.sh
```

## 環境変数一覧

| 変数名 | 説明 | デフォルト値 | 必須 |
|--------|------|------------|------|
| `BRIGHTDATA_API_TOKEN` | BrightData APIトークン | - | ✅ |
| `BRIGHTDATA_DATASET_ID` | Web Scraper Dataset ID | gd_lkpb8cqr7v3twzxwp | ❌ |
| `CSV_FILE` | 入力CSVファイル | dental_new.csv | ❌ |
| `OUTPUT_FILE` | 出力CSVファイル | results/dental_new_reviews.csv | ❌ |
| `DAYS_BACK` | 取得日数 | 10 | ❌ |
| `BATCH_SIZE` | APIバッチサイズ（施設数） | 100 | ❌ |
| `CSV_BATCH_SIZE` | CSVバッチサイズ（行数） | 500 | ❌ |
| `WAIT_BETWEEN_BATCHES` | バッチ間待機時間（秒） | 60 | ❌ |
| `START_FROM_BATCH` | 開始バッチ番号 | 1 | ❌ |
| `GENERATE_REPORT` | レポート生成フラグ | true | ❌ |
| `REPORT_DAYS` | レポート分析期間（日） | 10 | ❌ |
| `TEST_MODE` | quick に設定でクイックモード | - | ❌ |

## 実行例

### 例1: 小規模テスト（最初の50行のみ）

```bash
export BRIGHTDATA_API_TOKEN='your_token'
export CSV_BATCH_SIZE=50
export BATCH_SIZE=10
export WAIT_BETWEEN_BATCHES=30
./test_dental_reviews_local.sh
```

### 例2: 特定バッチから再開

```bash
export BRIGHTDATA_API_TOKEN='your_token'
export START_FROM_BATCH=3  # バッチ3から再開
./test_dental_reviews_local.sh
```

### 例3: レポートなしで実行

```bash
export BRIGHTDATA_API_TOKEN='your_token'
export GENERATE_REPORT=false
./test_dental_reviews_local.sh
```

### 例4: 過去30日間のレビュー取得、7日間のレポート

```bash
export BRIGHTDATA_API_TOKEN='your_token'
export DAYS_BACK=30        # レビュー取得: 過去30日
export REPORT_DAYS=7       # レポート分析: 過去7日
./test_dental_reviews_local.sh
```

## 出力ファイル

### 処理中に生成されるファイル

1. **レビューCSV**
   - パス: `results/dental_new_reviews.csv` (デフォルト)
   - 形式: `reviews_BrightData_50.py` と同じ
   - カラム: レビューID, 施設ID, 施設GID, レビュワー評価, レビュワー名, レビュー本文, etc.

2. **バッチCSV**
   - パス: `results/dental_new_reviews_batch_*.csv`
   - 各バッチの処理結果を個別保存

3. **ログファイル**
   - パス: `results/logs/dental_reviews_local_test.log`
   - 全処理ログを記録

4. **レポートファイル** (GENERATE_REPORT=true の場合)
   - Markdown: `results/reports/review_report_YYYYMMDD_HHMMSS.md`
   - JSON: `results/reports/review_report_YYYYMMDD_HHMMSS.json`
   - CSV: `results/reports/review_summary_YYYYMMDD_HHMMSS.csv`

## スクリプトの動作

### 実行フロー

```
1. 環境変数チェック
   ├─ BRIGHTDATA_API_TOKEN: 必須
   └─ BRIGHTDATA_DATASET_ID: オプション（デフォルト値あり）

2. 設定表示
   └─ 全パラメータをコンソールに表示

3. CSVデータ分析
   ├─ 総行数カウント
   └─ 必要なバッチ数を計算

4. バッチ処理ループ
   ├─ 各バッチでget_reviews_from_dental_new.py実行
   ├─ 成功/失敗をカウント
   └─ バッチ間で指定秒数待機

5. レポート生成（GENERATE_REPORT=true）
   └─ generate_review_report.py実行

6. 結果サマリー表示
   ├─ 成功/失敗バッチ数
   ├─ 総レビュー数
   └─ 生成ファイル一覧
```

### GitHubワークフローとの違い

| 項目 | ワークフロー | ローカルスクリプト |
|------|------------|------------------|
| Gitコミット | ✅ 自動実行 | ❌ 実行しない |
| Gitプッシュ | ✅ 自動実行 | ❌ 実行しない |
| GitHub Artifacts | ✅ アップロード | ❌ ローカル保存のみ |
| 環境変数 | Secrets使用 | export設定 |

## トラブルシューティング

### エラー: BRIGHTDATA_API_TOKEN が設定されていません

```bash
export BRIGHTDATA_API_TOKEN='your_actual_token_here'
```

### エラー: dental_new.csv が見つかりません

```bash
# ファイルが別の場所にある場合
export CSV_FILE='path/to/your/dental_new.csv'
./test_dental_reviews_local.sh
```

### エラー: Python モジュールが見つかりません

```bash
pip install -r requirements.txt
```

### 一部のバッチで失敗

- ログファイルを確認: `results/logs/dental_reviews_local_test.log`
- 特定バッチから再開: `export START_FROM_BATCH=3`

### APIレート制限エラー

```bash
# 待機時間を増やす
export WAIT_BETWEEN_BATCHES=120  # 120秒
./test_dental_reviews_local.sh
```

## 本番実行前のチェックリスト

- [ ] クイックテストモードで動作確認
  ```bash
  export TEST_MODE='quick'
  ./test_dental_reviews_local.sh
  ```

- [ ] レビューCSVの形式確認
  ```bash
  head -n 5 results/dental_new_reviews.csv
  ```

- [ ] レポート生成確認
  ```bash
  ls -lh results/reports/
  cat results/reports/review_report_*.md
  ```

- [ ] ログにエラーがないか確認
  ```bash
  grep -i error results/logs/dental_reviews_local_test.log
  ```

- [ ] GitHub Actionsのシークレット設定確認
  - Settings → Secrets → Actions
  - `BRIGHTDATA_API_TOKEN` が設定されているか

## 関連ファイル

- **メインスクリプト**: [get_reviews_from_dental_new.py](../get_reviews_from_dental_new.py)
- **レポート生成**: [generate_review_report.py](../generate_review_report.py)
- **ワークフロー**: [.github/workflows/dental_new_reviews_sequential.yml](../.github/workflows/dental_new_reviews_sequential.yml)

## 参考

- [QUICK_START_20PARALLEL.md](../QUICK_START_20PARALLEL.md) - 並列処理の設定方法
- [BRIGHTDATA_API_MIGRATION.md](./BRIGHTDATA_API_MIGRATION.md) - API移行ガイド
- [CID_TO_PLACE_URL_UNLOCKER_GUIDE.md](./CID_TO_PLACE_URL_UNLOCKER_GUIDE.md) - URL変換ガイド
