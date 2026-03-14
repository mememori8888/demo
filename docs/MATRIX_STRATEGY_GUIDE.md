# 🎭 Matrix Strategy 並列処理ガイド

## 🚀 超高速！地域別並列処理

GitHub ActionsのMatrix Strategyを使って、**複数の地域を同時に処理**します。

---

## 📊 処理速度の比較

### 通常処理（1ジョブ）
```
55,000件 ÷ 100ワーカー = 約9時間
```

### Matrix Strategy（47都道府県並列）
```
55,000件 ÷ 47地域 ÷ 50ワーカー = 約30分！
※同時実行数の制限により実際は1-2時間
```

---

## 🎯 3つの実行モード

### モード1: 特定地域のみ処理

**例: 北海道のみ**

```yaml
Regions to process: 北海道
Workers per region: 50
```

**完了時間**: 約20-30分（件数による）

---

### モード2: 複数地域を指定

**例: 主要都市のみ**

```yaml
Regions to process: 北海道,東京都,大阪府,愛知県,福岡県
Workers per region: 50
```

**完了時間**: 約30-60分
**並列実行**: 5地域が同時に処理される

---

### モード3: 全地域を並列処理

**例: 47都道府県すべて**

```yaml
Regions to process: all
Workers per region: 50
```

**完了時間**: 約1-2時間（同時実行制限による）
**並列実行**: 最大10地域が同時に処理される

---

## 🔧 セットアップ

### 1. CSVファイルに地域情報を追加

```csv
url,facility_name,prefecture,category
https://maps.google.com/?cid=123,札幌歯科,北海道,歯科
https://maps.google.com/?cid=456,仙台歯科,宮城県,歯科
https://maps.google.com/?cid=789,東京歯科,東京都,歯科
```

**重要**: `prefecture` カラムが必要です

---

### 2. ローカルでテスト（地域フィルタリング）

```bash
# 環境変数設定
export BRIGHTDATA_API_TOKEN='your_token'

# 北海道のみテスト
python brightdata_batch_processor.py \
  --csv facility_urls.csv \
  --filter-column prefecture \
  --filter-value 北海道 \
  --workers 10 \
  --output-dir test_results

# 結果確認
ls -lh test_results/
```

---

## ⚡ GitHub Actions実行手順

### ステップ1: ワークフローを選択

1. GitHubリポジトリの「Actions」タブ
2. 「BrightData Matrix Processing」を選択
3. 「Run workflow」をクリック

---

### ステップ2: パラメータ設定

#### 🗺️ 北海道のみ処理する場合

```
CSV file path: facility_urls.csv
Filter column name: prefecture
Regions to process: 北海道
Workers per region: 50
Days limit: 10
```

#### 🌆 主要5都市を処理する場合

```
CSV file path: facility_urls.csv
Filter column name: prefecture
Regions to process: 北海道,東京都,大阪府,愛知県,福岡県
Workers per region: 50
Days limit: 10
```

#### 🗾 全国すべて（47都道府県）を処理する場合

```
CSV file path: facility_urls.csv
Filter column name: prefecture
Regions to process: all
Workers per region: 50
Days limit: 10
```

---

## 📊 実行中の確認

### Matrix Jobsの表示

Actionsページで以下のように表示されます：

```
✅ process-region (北海道) - 完了
🔄 process-region (東京都) - 実行中
⏳ process-region (大阪府) - 待機中
...
```

### リアルタイム進捗

各地域のジョブをクリックすると：
- 処理状況がリアルタイムで表示
- 成功/失敗件数
- エラーログ

---

## 📁 結果のダウンロード

### 地域別の結果

```
Artifacts:
├── results-北海道
│   ├── brightdata_results_*.csv
│   └── brightdata_failed_*.csv
├── results-東京都
│   ├── brightdata_results_*.csv
│   └── brightdata_failed_*.csv
└── ...
```

### 統合結果

```
Artifacts:
└── merged-results-all-regions
    ├── all_results_merged.csv  ← 全地域の成功データ統合
    └── all_failed_merged.csv   ← 全地域の失敗データ統合
```

**これをダウンロードすれば、全地域のデータが1つのCSVに！**

---

## 🎯 実践例

### 例1: 北海道だけを素早く処理

```yaml
# GitHub Actionsで実行
Regions: 北海道
Workers: 50
```

**結果:**
- 実行時間: 約20分
- 出力: `results-北海道/brightdata_results_*.csv`

---

### 例2: 主要5都市を同時処理

```yaml
Regions: 北海道,東京都,大阪府,愛知県,福岡県
Workers: 50
```

**結果:**
- 実行時間: 約30-40分（5地域並列）
- 出力: 各地域のArtifacts + 統合結果

---

### 例3: 全国を一気に処理

```yaml
Regions: all
Workers: 50
```

**結果:**
- 実行時間: 約1-2時間
- 出力: 47地域のArtifacts + 統合結果

---

## 💡 Matrix Strategyの利点

### 1. **超高速処理**
- 地域を同時に処理
- 待ち時間なし

### 2. **耐障害性**
- 1地域が失敗しても他は継続
- `fail-fast: false` により保証

### 3. **管理しやすい**
- 地域ごとに独立したログ
- 地域ごとに再実行可能

### 4. **Job Summaries**
- 各地域の処理結果が一覧表示
- 最終的な統合結果も自動集計

### 5. **Artifacts管理**
- 地域ごとに個別保存
- 自動統合で全国データも取得可能

---

## 🔄 再実行・リトライ

### 特定地域だけ再実行

```yaml
# 北海道だけやり直す
Regions: 北海道
```

チェックポイント機能により、前回の続きから自動再開！

---

### 失敗した地域を一括再実行

```bash
# 失敗した地域を特定
Regions: 青森県,秋田県,山形県

# これらだけ再実行
```

---

## 📈 パフォーマンス最適化

### 同時実行数の調整

ワークフローファイルの `max-parallel` を調整：

```yaml
strategy:
  max-parallel: 10  # ← ここを変更
```

- 小さい値（5）: 安全だが遅い
- 中程度（10）: バランス良好 ✅
- 大きい値（20）: 高速だがリソース注意

---

## 🎉 まとめ

### 通常処理 vs Matrix Strategy

| 項目 | 通常処理 | Matrix Strategy |
|------|---------|----------------|
| 55,000件の処理時間 | 9-18時間 | **1-2時間** ✅ |
| 地域別管理 | ❌ | ✅ |
| 並列実行 | スレッドレベル | ジョブレベル |
| 再実行 | 全体 | 地域単位 |
| 結果管理 | 1ファイル | 地域別+統合 |

---

## 🚀 今すぐ試す

### クイックスタート

```bash
# 1. ローカルでテスト（北海道のみ）
python brightdata_batch_processor.py \
  --csv facility_urls.csv \
  --filter-column prefecture \
  --filter-value 北海道 \
  --workers 10

# 2. GitHub Actionsで本番実行
# → Actionsタブから「BrightData Matrix Processing」を選択
# → Regions: all
# → Run workflow

# 3. 1-2時間後、全国のデータが完成！
```

これで**55,000件を1-2時間で処理完了**できます！🎉
