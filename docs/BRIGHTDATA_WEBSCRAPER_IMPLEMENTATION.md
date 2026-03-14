## 📋 変更方針

### 戦略: 新規スクリプト + 新規ワークフロー作成 ✅

既存のSERP API版を残しつつ、Web Scraper API版を新規に作成する方式を採用しました。

### 主な変更点

| 項目 | SERP API版（既存） | Web Scraper API版（新規） |
|-----|------------------|------------------------|
| スクリプト | `reviews_BrightData_50.py` | `reviews_BrightData_webscraper.py` |
| ワークフロー | `brightdata_reviews_auto_batch.yml` | `brightdata_webscraper_reviews_auto_batch.yml` |
| 入力データ | FID (施設GID) | GoogleMap URL |
| API方式 | SERP API（同期） | Web Scraper API（非同期スナップショット） |
| 期間指定 | なし | days_back パラメータ |
| 必要な列 | FID列 | GoogleMap列 |

---

## 🚀 実装内容

### 1. 新規スクリプト: `reviews_BrightData_webscraper.py`

**主な機能:**
- ✅ GoogleMap URLから直接レビュー取得
- ✅ days_back パラメータで期間指定
- ✅ スナップショット方式（非同期API）
- ✅ バッチ処理対応
- ✅ ポーリングで完了待機

**APIフロー:**
```
1. trigger → snapshot_id を取得
2. polling → status が "ready" になるまで待機
3. get data → レビューデータを取得
```

**必要な環境変数:**
- `BRIGHTDATA_API_TOKEN` - BrightData APIトークン
- `BRIGHTDATA_DATASET_ID` - Web Scraper Dataset ID

### 2. 新規ワークフロー: `brightdata_webscraper_reviews_auto_batch.yml`

**主な機能:**
- ✅ 自動バッチ分割（5,000件以上）
- ✅ 並列実行（最大6ジョブ）
- ✅ 開始行・終了行指定
- ✅ 期間指定（days_back）
- ✅ 結果の自動統合

**パラメータ:**

| パラメータ | 説明 | デフォルト |
|-----------|------|-----------|
| `facility_file` | 施設データCSV | `dental_new.csv` |
| `review_output_file` | 出力ファイル名 | `dental_reviews_webscraper` |
| `days_back` | 取得期間（日数） | 365 |
| `batch_size` | API 1回の処理数 | 100 |
| `max_parallel_jobs` | 並列ジョブ数 | 2 |
| `start_line` | 開始行 | - |
| `end_line` | 終了行 | - |

---

## 💡 使用方法

### GitHub Actionsで実行

1. **Actionsタブを開く**
2. **「BrightData WebScraper Reviews Auto-Batch」を選択**
3. **「Run workflow」をクリック**
4. **パラメータを設定:**

**dental_new.csvの全件処理（70,000行）の例:**
```
facility_file: dental_new.csv
review_output_file: dental_reviews_2026
days_back: 30 (直近30日間のレビュー)
batch_size: 100
max_parallel_jobs: 6 (6並列で処理)
start_line: (空欄)
end_line: (空欄)
```

**分割処理の例（1-10000行のみ）:**
```
facility_file: dental_new.csv
review_output_file: dental_reviews_part1
days_back: 90
batch_size: 100
max_parallel_jobs: 3
start_line: 1
end_line: 10000
```

### ローカルで実行

```bash
# 環境変数を設定
export BRIGHTDATA_API_TOKEN="your_token"
export BRIGHTDATA_DATASET_ID="gd_your_dataset_id"

# 実行
python reviews_BrightData_webscraper.py \
  --input results/dental_new.csv \
  --output results/dental_reviews.csv \
  --days-back 30 \
  --start-line 1 \
  --process-count 100 \
  --batch-size 50
```

---

## ⚙️ 必要な設定

### GitHub Secrets

以下のSecretsを追加してください：

1. **`BRIGHTDATA_API_TOKEN`**
   - BrightData APIトークン
   - 既存のものと同じでOK

2. **`BRIGHTDATA_WEBSCRAPER_DATASET_ID`** ← **新規**
   - Web Scraper用のDataset ID
   - BrightDataコンソールで Google Maps Reviews データセットのIDを確認

---

## 📊 処理時間の見積もり

### Web Scraper API の特性
- **スナップショット完了時間**: 5〜20分/バッチ（100施設）
- **並列制限**: 推奨1〜3並列（API負荷を考慮）

### 70,000行の場合

**設定例:**
- batch_size: 100 (API 1回で100施設)
- max_parallel_jobs: 6
- 1ジョブあたり: 約11,667施設

**推定時間:**
- 1ジョブ: 117バッチ × 15分 = 約29時間
- 6並列: 約29時間 ÷ 6 = **約5時間**

⚠️ **注意**: Web Scraper APIは非同期処理のため、SERP APIより時間がかかります。

---

## 🔄 段階的な移行戦略

### フェーズ1: テスト実行（完了）
- ✅ 新規スクリプト作成
- ✅ 新規ワークフロー作成
- 🔜 100件程度でテスト実行

### フェーズ2: 小規模運用
- 1,000〜5,000件でテスト
- エラーハンドリングの確認
- 出力データの品質確認

### フェーズ3: 大規模運用
- 70,000件の全件処理
- 並列数の最適化
- 定期実行の検討

### フェーズ4: 移行完了
- 既存SERP API版の廃止検討
- ドキュメント更新
- WebUIの更新

---

## ⚡ dental_new.csvへの適用

dental_new.csvには **GoogleMap列が既に存在** するため、すぐに使用可能です。

### 実行手順

1. **GitHub Secretsを設定**
   - `BRIGHTDATA_WEBSCRAPER_DATASET_ID` を追加

2. **テスト実行（100件）**
   ```
   facility_file: dental_new.csv
   days_back: 30
   start_line: 1
   end_line: 100
   ```

3. **全件実行（70,000件）**
   ```
   facility_file: dental_new.csv
   days_back: 365
   max_parallel_jobs: 6
   ```

---

## 🎯 dental_new.csvのURL更新との連携

### 推奨ワークフロー

1. **まず dental_new.csvのURLを更新**
   - ワークフロー: `Update GoogleMap URLs`
   - cid形式 → 正規URL形式に変換

2. **次にレビューを取得**
   - ワークフロー: `BrightData WebScraper Reviews Auto-Batch`
   - 正規URLから直接レビュー取得

この順序で実行することで、最新のURLから正確にレビューを取得できます。

---

## 📝 次のステップ

### 1. GitHub Secretsの設定
```
Settings → Secrets and variables → Actions → New repository secret
Name: BRIGHTDATA_WEBSCRAPER_DATASET_ID
Value: gd_xxxxxxxxx
```

### 2. テスト実行
- 100件程度で動作確認
- エラーがないか確認

### 3. 本番実行
- dental_new.csv全件でレビュー取得

### 4. 結果確認
- 出力CSVの内容確認
- レビュー件数の確認

---

## ❓ FAQ

### Q1: SERP API版と併用できますか？
A: はい、両方のワークフローは独立しているため併用可能です。

### Q2: FIDベースの処理は必要なくなりますか？
A: Web Scraper API版ではFID不要ですが、既存のSERP API版は引き続きFIDを使用します。

### Q3: 処理時間はどちらが早いですか？
A: SERP API版の方が高速です。Web Scraper API版は非同期処理のため待機時間が発生します。

### Q4: 期間指定はどう使いますか？
A: `days_back: 30` で直近30日間、`days_back: 365` で1年間のレビューを取得します。

### Q5: dental_new.csvのURL更新と同時実行できますか？
A: 可能ですが、URL更新 → レビュー取得の順序を推奨します。
