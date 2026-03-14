# BrightData API 効率的な大量処理ガイド

## 📋 概要

55,000施設のデータを効率的に処理するための並列処理スクリプトです。

### 🎯 改善効果

**従来（順次処理）:**
- 処理時間: 1施設あたり2分
- 総処理時間: 55,000 × 2分 = **110,000分（約76日）**

**改善後（並列処理）:**
- 並列度10の場合: **約7.6日**
- 並列度20の場合: **約3.8日**
- 並列度50の場合: **約1.5日**

## 🚀 クイックスタート

### 1. 基本的な使い方

```bash
# 環境変数設定
export BRIGHTDATA_API_TOKEN='your_api_token_here'

# 並列度10で実行（推奨）
python brightdata_batch_processor.py \
  --csv facility_urls.csv \
  --url-column url \
  --workers 10 \
  --output-dir results
```

### 2. 高速処理（並列度20）

```bash
python brightdata_batch_processor.py \
  --csv facility_urls.csv \
  --url-column url \
  --workers 20 \
  --output-dir results
```

### 3. 中断からの再開

```bash
# チェックポイントから自動再開
python brightdata_batch_processor.py \
  --csv facility_urls.csv \
  --resume \
  --workers 10 \
  --output-dir results
```

## 📊 スクリプト説明

### `brightdata_batch_processor.py`（推奨）⭐

**用途:** 数万件以上のURL処理（大規模向け）

**特徴:**
- チェックポイント機能（中断・再開可能）
- 結果を逐次保存（メモリ効率的）
- リトライ機能
- 詳細な進捗表示
- 地域別フィルタリング対応

**実行例:**
```bash
python brightdata_batch_processor.py \
  --csv facility_urls.csv \
  --workers 10 \
  --output-dir results
```

## ⚙️ オプション詳細

### 必須パラメータ

| パラメータ | 説明 | 例 |
|-----------|------|-----|
| `--csv` | 入力CSVファイル | `facility_urls.csv` |

### 任意パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `--url-column` | `url` | URLカラム名 |
| `--workers` | `10` | 並列実行数（5-20推奨） |
| `--days-limit` | `10` | レビュー取得期間（日） |
| `--output-dir` | `results` | 出力ディレクトリ |
| `--resume` | - | チェックポイントから再開 |

## 🔧 並列度の調整

### 推奨設定

| 環境 | 並列度 | 理由 |
|------|--------|------|
| **通常** | 10-15 | バランスが良い |
| **高速化** | 20-30 | リソースに余裕がある場合 |
| **安全重視** | 5-10 | レート制限を避ける |

### 注意事項

- BrightDataのレート制限に注意
- 並列度を上げすぎると429エラー（レート制限）が発生する可能性
- エラーが多発する場合は並列度を下げる

## 📁 入力ファイル形式

### CSVファイル例

```csv
url,facility_name,category
https://maps.google.com/?cid=4943704292481018584,施設A,歯科
https://maps.google.com/?cid=1234567890123456789,施設B,歯科
```

**注意:**
- URLカラムが必須
- ヘッダー行が必要
- UTF-8エンコーディング

## 📤 出力形式

### 成功データ（JSONL形式）

`results/brightdata_results_20260128_120000.jsonl`

```jsonl
{"place_id": "...", "review_rating": 5, "source_url": "https://..."}
{"place_id": "...", "review_rating": 4, "source_url": "https://..."}
```

### 失敗データ（JSONL形式）

`results/brightdata_failed_20260128_120000.jsonl`

```jsonl
{"url": "https://...", "error": "timeout", "timestamp": "2026-01-28T12:00:00"}
```

### チェックポイントファイル

`results/checkpoint_20260128_120000.txt`

```
https://maps.google.com/?cid=4943704292481018584
https://maps.google.com/?cid=1234567890123456789
```

## 🔄 処理フロー

```
1. CSVファイル読み込み
   ↓
2. チェックポイント確認（--resume時）
   ↓
3. 未処理URLの抽出
   ↓
4. 並列処理開始
   ├─ API呼び出し
   ├─ 進捗監視
   ├─ 結果ダウンロード
   ├─ リトライ（エラー時）
   └─ 逐次保存
   ↓
5. チェックポイント更新
   ↓
6. 進捗表示（10件ごと）
```

## 🛠️ トラブルシューティング

### 429エラー（レート制限）が発生

```bash
# 並列度を下げる
python brightdata_batch_processor.py \
  --csv facility_urls.csv \
  --workers 5
```

### 処理が途中で停止した

```bash
# チェックポイントから再開
python brightdata_batch_processor.py \
  --csv facility_urls.csv \
  --resume
```

### メモリ不足エラー

```bash
# バッチ処理スクリプトを使用（逐次保存）
python brightdata_batch_processor.py \
  --csv facility_urls.csv \
  --workers 5
```

### タイムアウトが頻発

- ネットワーク接続を確認
- 並列度を下げる
- スクリプトは自動的にリトライします

## 📈 進捗監視

### リアルタイム進捗表示

10件ごとに以下の情報が表示されます：

```
📊 進捗状況 [2026-01-28 12:00:00]
  完了: 100/55000 (0.18%)
  成功: 98, 失敗: 2, リトライ: 5
  処理中: 10
  経過時間: 15.0分
  平均処理時間: 9.0秒/件
  残り時間(推定): 137.5時間 (8250分)
```

### ログファイル

標準出力をファイルにリダイレクト可能：

```bash
python brightdata_batch_processor.py \
  --csv facility_urls.csv \
  --workers 10 \
  2>&1 | tee process_log.txt
```

## 💾 ディスク容量の見積もり

### 必要容量計算

- 1施設あたり約10件のレビュー
- 1レビューあたり約1KB
- 55,000施設の場合

```
55,000施設 × 10レビュー × 1KB = 約550MB
```

**推奨:** 2GB以上の空き容量

## ⚡ 性能最適化のヒント

### 1. 並列度の段階的増加

```bash
# まず小さな並列度で試す
python brightdata_batch_processor.py --csv test.csv --workers 5

# エラーが少なければ増やす
python brightdata_batch_processor.py --csv test.csv --workers 10

# さらに増やす
python brightdata_batch_processor.py --csv test.csv --workers 20
```

### 2. データ分割処理

大量データは分割して処理すると安全：

```bash
# CSVを分割（10,000件ずつ）
python split_csv_for_parallel.py --input facility_urls.csv --chunk-size 10000

# 各ファイルを並列処理
python brightdata_batch_processor.py --csv facility_urls_part1.csv --workers 15
python brightdata_batch_processor.py --csv facility_urls_part2.csv --workers 15
```

### 3. バックグラウンド実行

```bash
# nohupで実行（セッション切断後も継続）
nohup python brightdata_batch_processor.py \
  --csv facility_urls.csv \
  --workers 10 \
  > process.log 2>&1 &

# 進捗確認
tail -f process.log
```

### 4. スクリーンセッションの使用

```bash
# スクリーンセッション開始
screen -S brightdata

# スクリプト実行
python brightdata_batch_processor.py --csv facility_urls.csv --workers 10

# デタッチ: Ctrl+A, D

# 再接続
screen -r brightdata
```

## 🔐 セキュリティ

### API トークンの管理

```bash
# .envファイルに保存
echo "BRIGHTDATA_API_TOKEN=your_token" > .env

# スクリプト実行前に読み込み
export $(cat .env | xargs)
python brightdata_batch_processor.py --csv facility_urls.csv
```

### .gitignoreに追加

```gitignore
.env
results/
*.log
```

## 📞 サポート

### エラーログの確認

失敗したURLは `brightdata_failed_*.jsonl` に記録されます：

```bash
# 失敗理由の集計
cat results/brightdata_failed_*.jsonl | jq '.error' | sort | uniq -c
```

### 再処理

```bash
# 失敗したURLのみを抽出して再処理
cat results/brightdata_failed_*.jsonl | jq -r '.url' > failed_urls.txt

# CSVに変換
echo "url" > failed_urls.csv
cat failed_urls.txt >> failed_urls.csv

# 再実行
python brightdata_batch_processor.py --csv failed_urls.csv --workers 5
```

## 📚 関連ドキュメント

- [START_HERE.md](../START_HERE.md) - クイックスタートガイド
- [docs/MATRIX_STRATEGY_GUIDE.md](MATRIX_STRATEGY_GUIDE.md) - 地域別並列処理
- [docs/ASYNC_VS_SYNC_COMPARISON.md](ASYNC_VS_SYNC_COMPARISON.md) - 非同期処理の利点
- [docs/GITHUB_ACTIONS_EXECUTION_GUIDE.md](GITHUB_ACTIONS_EXECUTION_GUIDE.md) - GitHub Actions実行ガイド

## 🎉 まとめ

### 55,000施設の処理時間見積もり

| 並列度 | 処理時間 | 備考 |
|--------|---------|------|
| 1（従来）| 約76日 | 非推奨 |
| 5 | 約15日 | 安全重視 |
| **10** | **約7.6日** | **推奨** |
| 20 | 約3.8日 | 高速化 |
| 30 | 約2.5日 | レート制限注意 |

### おすすめの実行方法

```bash
# 1. 環境変数設定
export BRIGHTDATA_API_TOKEN='your_token'

# 2. スクリーンセッション開始
screen -S brightdata

# 3. バッチ処理実行（並列度10）
python brightdata_batch_processor.py \
  --csv facility_urls.csv \
  --url-column url \
  --workers 10 \
  --days-limit 10 \
  --output-dir results \
  2>&1 | tee process_log.txt

# 4. デタッチ（Ctrl+A, D）

# 5. 必要に応じて再接続
screen -r brightdata
```

これで55,000施設を **約1週間** で処理できます！🚀
