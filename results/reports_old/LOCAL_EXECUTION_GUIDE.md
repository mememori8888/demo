# dental_new レビュー取得 - ローカル実行ガイド

GitHub Actionsの課金制限がある場合、ローカル環境で同じ処理を実行できます。

## 前提条件

1. Python 3.12+
2. BrightData API Token
3. `requests` ライブラリ

```bash
pip install requests
```

## 実行方法

### 1. API Tokenの設定

```bash
export BRIGHTDATA_API_TOKEN='your-api-token-here'
```

### 2. スクリプトの実行

**北海道のみ（推奨）:**
```bash
./run_reviews_local.sh
```

**カスタム設定:**
```bash
./run_reviews_local.sh [入力CSV] [出力CSV] [日数] [Batch Size] [CSV Batch Size] [待機時間]
```

**例:**
```bash
# 北海道のみ、過去30日間
./run_reviews_local.sh results/dental_new_hokkaido.csv results/dental_new_reviews_hokkaido.csv 30

# 全国、過去10日間（時間がかかります）
./run_reviews_local.sh results/dental_new.csv results/dental_new_reviews.csv 10
```

## パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| 入力CSV | `results/dental_new_hokkaido.csv` | 施設データCSV |
| 出力CSV | `results/dental_new_reviews_hokkaido.csv` | レビュー出力CSV |
| 日数 | `10` | 取得期間（日数） |
| Batch Size | `100` | API 1回あたりの施設数 |
| CSV Batch Size | `500` | 1バッチあたりの行数 |
| 待機時間 | `120` | バッチ間の待機時間（秒） |

## 処理時間の目安

### 北海道のみ（3,242施設、うちweb列空1,184件 = 実質2,058施設）
- **バッチ数**: 約5バッチ
- **1バッチ**: 約10-15分
- **合計**: 約1.5-2時間

### 全国（77,076施設）
- **バッチ数**: 約155バッチ
- **合計**: 約2-3日間 ⚠️

## エラーハンドリング

スクリプトには以下のエラーハンドリングが組み込まれています：

- ✅ **自動リトライ**: 各バッチ最大3回リトライ（30秒→60秒→90秒待機）
- ✅ **連続エラー検知**: 連続3回失敗で自動中断
- ✅ **詳細ログ**: `results/logs/batch_*.log` に保存
- ✅ **web列スキップ**: web列が空の施設は自動的にスキップ

## ログファイル

処理中のログは以下に保存されます：

- `results/logs/dental_reviews.log` - メインログ
- `results/logs/batch_*.log` - 各バッチのログ

## 中断と再開

処理を中断した場合、特定のバッチから再開できます：

```bash
# バッチ3から再開
START_BATCH=3 ./run_reviews_local.sh
```

ただし、この機能は現在のスクリプトには実装されていません。
必要に応じて環境変数 `START_ROW` と `END_ROW` で範囲指定できます：

```bash
export START_ROW=1001
export END_ROW=1500
python3 get_reviews_from_dental_new.py
```

## トラブルシューティング

### API Token エラー
```
❌ エラー: BRIGHTDATA_API_TOKEN環境変数が設定されていません
```
→ `export BRIGHTDATA_API_TOKEN='your-token'` を実行

### タイムアウトエラー
→ スクリプトが自動的にリトライします（最大3回）

### 連続エラー
→ API制限に達した可能性があります。しばらく待ってから再実行してください

## GitHub Actionsとの違い

| 項目 | GitHub Actions | ローカル実行 |
|-----|---------------|------------|
| 実行環境 | クラウド | ローカルマシン |
| 費用 | 課金あり | 無料（電気代のみ） |
| 自動コミット | あり | 手動 |
| ログ保存 | Artifacts | ローカルファイル |
| 中断・再開 | 難しい | 簡単 |

## 実行例

```bash
$ ./run_reviews_local.sh
==========================================
dental_new レビュー取得（ローカル実行）
==========================================

📊 処理概要:
  - 入力CSV: results/dental_new_hokkaido.csv
  - 出力CSV: results/dental_new_reviews_hokkaido.csv
  - 総行数: 3242
  - CSVバッチサイズ: 500行
  - 総バッチ数: 7
  - API Batch Size: 100
  - Days back: 10
  - バッチ間待機: 120秒

実行しますか？ (y/N): y

==========================================
🚀 バッチ 1/7 開始
   範囲: 行1～500
==========================================
...
```

## 完了後

1. 出力ファイルを確認: `results/dental_new_reviews_hokkaido.csv`
2. ログを確認: `results/logs/dental_reviews.log`
3. Gitにコミット（任意）:
```bash
git add results/dental_new_reviews_hokkaido.csv
git commit -m "chore: Add dental reviews (local execution)"
git push
```
