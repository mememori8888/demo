# 🎯 BrightData 非同期処理システム - ファイル構成

## 📂 主要ファイル

### 🔧 実行スクリプト

| ファイル | 用途 | 説明 |
|---------|------|------|
| **brightdata_batch_processor.py** | メインスクリプト | 大規模データ処理、チェックポイント機能付き |
| **download_snapshot.py** | snapshot取得 | 既存のsnapshot IDからデータ取得 |
| **step1_quick_test.sh** | 小規模テスト | 処理時間を計測（最初に実行） |
| **step2_github_actions_setup.sh** | セットアップ | GitHub Actions設定ガイド |

### 🤖 GitHub Actions

| ファイル | 用途 | 特徴 |
|---------|------|------|
| **.github/workflows/brightdata_processing.yml** | 単一ジョブ | 通常の並列処理 |
| **.github/workflows/brightdata_matrix_processing.yml** | Matrix並列 | 地域別の超高速処理 ⭐ |

### 📚 ドキュメント

| ファイル | 内容 |
|---------|------|
| **START_HERE.md** | 最初に読むガイド |
| **docs/MATRIX_STRATEGY_GUIDE.md** | Matrix Strategy完全ガイド ⭐ |
| **docs/ASYNC_VS_SYNC_COMPARISON.md** | 非同期処理の利点 |
| **docs/GITHUB_ACTIONS_EXECUTION_GUIDE.md** | 詳細実行ガイド |
| **docs/BRIGHTDATA_EFFICIENT_PROCESSING_GUIDE.md** | 効率化ガイド |

---

## 🚀 クイックスタート

### ステップ1: テスト実行
```bash
export BRIGHTDATA_API_TOKEN='your_token'
./step1_quick_test.sh
```

### ステップ2: GitHub Actions設定
```bash
./step2_github_actions_setup.sh
```

### ステップ3: 本番実行

#### 🎭 Matrix Strategy（推奨） - 1-2時間
```
GitHub Actions → BrightData Matrix Processing
Regions: all
```

#### 📊 単一ジョブ - 数時間〜
```
GitHub Actions → BrightData Batch Processing
Workers: 100
```

---

## 💡 処理方式

### 非同期処理の仕組み

```
1. 複数のリクエストを同時送信
   ↓
2. snapshot IDを即座に取得
   ↓
3. バックグラウンドで処理
   ↓
4. 完了したものから順次取得
```

**利点:**
- ✅ 待機時間を有効活用
- ✅ CPU使用率が大幅向上
- ✅ 処理時間が10-100倍高速化

---

## 🗺️ 地域別処理（Matrix Strategy）

### 特徴
- 47都道府県を同時処理
- 1地域が失敗しても他は継続
- 結果は自動統合

### 実行例
```yaml
# 北海道のみ
Regions: 北海道

# 主要都市
Regions: 北海道,東京都,大阪府,愛知県,福岡県

# 全国
Regions: all
```

---

## 📊 処理時間の目安（55,000件）

| 方式 | 時間 | 推奨度 |
|------|------|--------|
| 同期処理 | 約76日 | ❌ |
| 非同期（100並列） | 約18時間 | ⚠️ |
| Matrix Strategy（47地域） | **1-2時間** | ✅✅✅ |

---

## 🎯 削除した不要ファイル

以下のファイルは削除されました（非同期処理では不要）：

- ❌ `test_brightdata_api.py` - 元の単一処理スクリプト
- ❌ `brightdata_parallel_processor.py` - 小規模向け（batch_processorで代替）
- ❌ `calculate_workers.py` - 一時的な計算ツール
- ❌ `test_small_setup.py` - 一時的なセットアップ
- ❌ `test_brightdata_response_*.json` - 古いテスト結果

---

## 📞 サポート

詳細は各ドキュメントを参照してください：
- [START_HERE.md](START_HERE.md) - 最初に読む
- [docs/MATRIX_STRATEGY_GUIDE.md](docs/MATRIX_STRATEGY_GUIDE.md) - Matrix Strategy
- [docs/ASYNC_VS_SYNC_COMPARISON.md](docs/ASYNC_VS_SYNC_COMPARISON.md) - 非同期処理の詳細
