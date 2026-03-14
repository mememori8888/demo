# ローカル実行ガイド - BrightData レビュー取得

`get_reviews_from_dental_new.py` をローカル環境で簡単に実行するためのラッパースクリプトです。

## 📁 ファイル

- `run_reviews_local_interactive.py` - 対話型ローカル実行スクリプト
- `get_reviews_from_dental_new.py` - 本体スクリプト（BrightData API呼び出し）

## 🚀 基本的な使い方

### 1. 対話モードで実行（推奨）

最も簡単な方法です。スクリプトが必要な情報を対話的に尋ねます。

```bash
python run_reviews_local_interactive.py
```

実行すると、以下のような対話が始まります：

```
============================================================
🚀 BrightData レビュー取得ツール（ローカル実行版）
============================================================

⚠️  BrightData APIトークンが設定されていません

APIトークンを入力してください: [ここに入力]

📁 入力CSV: results/dental_new.csv
📁 出力CSV: results/dental_new_reviews.csv

📊 処理範囲:
   総行数: 1000行
   開始行: 1
   終了行: 1000（最終行まで）
   処理件数: 1000件

⚙️  設定:
   Days back: 10日
   Batch size: 50件/回
   Max wait: 90分
   Dataset ID: gd_luzfs1dn2oa0teb81
   Skip column: web

この設定で実行しますか？ (y/N): 
```

### 2. コマンドライン引数で実行

すべての設定をコマンドラインで指定できます。

```bash
python run_reviews_local_interactive.py \
  --input results/dental_new.csv \
  --output results/dental_new_reviews.csv \
  --api-token YOUR_API_TOKEN_HERE \
  --days-back 10 \
  --start-row 1 \
  --end-row 100 \
  --non-interactive
```

### 3. 環境変数を使用

APIトークンは環境変数で設定することもできます：

```bash
export BRIGHTDATA_API_TOKEN="your_token_here"
python run_reviews_local_interactive.py
```

## 📝 主要なオプション

### 必須パラメータ

| オプション | 説明 | デフォルト |
|----------|------|----------|
| `--input` | 入力CSVファイル（施設情報） | `results/dental_new.csv` |
| `--output` | 出力CSVファイル（レビュー情報） | `results/dental_new_reviews.csv` |
| `--api-token` | BrightData APIトークン | 環境変数から取得 |

### オプショナルパラメータ

| オプション | 説明 | デフォルト |
|----------|------|----------|
| `--update` | 増分ファイル（新規レビューのみ） | なし |
| `--start-row` | 処理開始行（1ベース） | `1` |
| `--end-row` | 処理終了行 | 最終行まで |
| `--days-back` | 何日前までのレビューを取得 | `10` |
| `--batch-size` | API 1回あたりの処理件数 | `50` |
| `--max-wait-minutes` | スナップショット待機時間（分） | `90` |
| `--dataset-id` | BrightData Dataset ID | `gd_luzfs1dn2oa0teb81` |
| `--skip-column` | スキップ判定列名 | `web` |
| `--non-interactive` | 対話モードを無効化 | - |

## 💡 使用例

### 例1: 最初の100件を処理

```bash
python run_reviews_local_interactive.py \
  --input results/dental_new.csv \
  --output results/dental_new_reviews.csv \
  --start-row 1 \
  --end-row 100 \
  --non-interactive
```

### 例2: バッチ処理（500件ずつ、増分ファイル出力）

バッチ1（行1～500）：
```bash
python run_reviews_local_interactive.py \
  --input results/dental_new.csv \
  --output results/dental_new_reviews.csv \
  --update results/dental_new_reviews_batch_1.csv \
  --start-row 1 \
  --end-row 500 \
  --batch-size 50 \
  --non-interactive
```

バッチ2（行501～1000）：
```bash
python run_reviews_local_interactive.py \
  --input results/dental_new.csv \
  --output results/dental_new_reviews.csv \
  --update results/dental_new_reviews_batch_2.csv \
  --start-row 501 \
  --end-row 1000 \
  --batch-size 50 \
  --non-interactive
```

### 例3: 30日分のレビューを取得

```bash
python run_reviews_local_interactive.py \
  --input results/dental_new.csv \
  --output results/dental_new_reviews_30days.csv \
  --days-back 30 \
  --non-interactive
```

### 例4: 特定の列でスキップ判定を変更

デフォルトは `web` 列が空の場合スキップしますが、別の列を指定できます：

```bash
python run_reviews_local_interactive.py \
  --input results/dental_new.csv \
  --output results/dental_new_reviews.csv \
  --skip-column googlemap \
  --non-interactive
```

## 🔧 GitHub Actions との違い

GitHub Actions版（ワークフロー）との主な違い：

| 機能 | GitHub Actions | ローカル実行 |
|-----|---------------|-----------|
| 実行環境 | クラウド（Ubuntu） | ローカルマシン |
| タイムアウト | 350分（約6時間） | 制限なし |
| 並列実行 | 可能 | 手動で複数端末起動が必要 |
| 自動保存 | 30分ごと自動コミット | なし |
| ログ | Artifact保存 | ローカルファイル |
| APIトークン | Secrets管理 | 環境変数または引数 |

## 📊 処理の流れ

1. **環境変数設定**: コマンドライン引数を環境変数に変換
2. **スクリプト実行**: `get_reviews_from_dental_new.py` を呼び出し
3. **API呼び出し**: BrightData Web Scraper API でレビュー取得
4. **CSV出力**: レビューデータを指定ファイルに保存

## 🐛 トラブルシューティング

### APIトークンエラー

```
❌ エラー: APIトークンが設定されていません
```

**解決方法**:
- `--api-token` で指定する
- 環境変数 `BRIGHTDATA_API_TOKEN` を設定する

```bash
export BRIGHTDATA_API_TOKEN="your_token_here"
```

### 入力ファイルが見つからない

```
❌ エラー: 入力ファイルが見つかりません: results/dental_new.csv
```

**解決方法**:
- ファイルパスを確認する
- 絶対パスで指定する

```bash
python run_reviews_local_interactive.py \
  --input /path/to/your/dental_new.csv
```

### スナップショットタイムアウト

```
❌ Timeout after 90 minutes
```

**解決方法**:
- `--max-wait-minutes` を増やす
- `--batch-size` を減らす（1回のAPI呼び出し件数を減らす）

```bash
python run_reviews_local_interactive.py \
  --max-wait-minutes 120 \
  --batch-size 30
```

### ログ確認

処理ログは以下に保存されます：

```
results/logs/dental_reviews.log
```

エラー調査時はこのファイルを確認してください：

```bash
tail -f results/logs/dental_reviews.log
```

## 📚 関連ドキュメント

- [BrightData API Migration Guide](docs/BRIGHTDATA_API_MIGRATION.md)
- [Batch Processing Guide](docs/BATCH_PROCESSING_500_GUIDE.md)
- [Efficient Processing Guide](docs/BRIGHTDATA_EFFICIENT_PROCESSING_GUIDE.md)

## 🔐 セキュリティ

- APIトークンは **絶対にGitにコミットしないでください**
- 環境変数または対話入力で指定してください
- `.env` ファイルを使用する場合は `.gitignore` に追加してください

## 💡 ヒント

### 大量データの処理

1000件以上の施設がある場合は、バッチ処理を推奨：

```bash
# バッチスクリプトを作成
for i in {1..10}; do
  START=$((($i - 1) * 100 + 1))
  END=$(($i * 100))
  
  python run_reviews_local_interactive.py \
    --start-row $START \
    --end-row $END \
    --update results/batch_${i}.csv \
    --non-interactive
  
  # バッチ間隔（API制限対策）
  sleep 120
done
```

### 処理状況のモニタリング

別の端末でログをリアルタイム監視：

```bash
tail -f results/logs/dental_reviews.log
```

### CSV結合

複数バッチのCSVを結合する場合：

```bash
python merge_batches.py
```

または手動で：

```bash
# ヘッダーを取得
head -1 results/batch_1.csv > results/dental_new_reviews.csv

# すべてのバッチからデータ行を追加（ヘッダー除く）
tail -n +2 -q results/batch_*.csv >> results/dental_new_reviews.csv
```

## 📞 サポート

問題が発生した場合：

1. ログファイルを確認: `results/logs/dental_reviews.log`
2. GitHub Issues に報告
3. 関連ドキュメントを参照

---

**作成日**: 2026-02-09  
**対応バージョン**: get_reviews_from_dental_new.py v3.x
