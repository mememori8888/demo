# CSV統合処理ガイド

## 📋 概要

3つのCSVファイルを統合し、post_idの重複を防ぎながら統一データを作成します。

## 📁 入力ファイル

| ファイル名 | 内容 | post_id |
|-----------|------|---------|
| **matched_data.csv** | Google Map照合済み（74,049件） | ✅ あり |
| **unmatched_data.csv** | Google Map未照合（1,433件） | ❌ なし |
| **wordpress_only_data.csv** | WordPress独自データ（7,172件） | ✅ あり |

## 🔄 統合ロジック

### 1. matched_data.csv
- **処理**: そのまま使用
- **post_id**: 既存のpost_idをそのまま保持
- **理由**: 電話番号と緯度経度の照合済みで信頼性が高い

### 2. unmatched_data.csv
- **処理**: 新規post_idを自動割り当て
- **post_id**: 最大post_id + 1から順に割り当て
- **理由**: post_idが空白のため新規採番が必要

### 3. wordpress_only_data.csv
- **処理**: Google Mapデータと重複しないもののみ追加
- **post_id**: 既存のpost_idをそのまま使用
- **重複判定**: 電話番号で照合

## 🚀 実行方法

```bash
# 統合処理を実行
python integrate_csv_data.py
```

## 📊 出力ファイル

### 1. integrated_data.csv
統合された完全なデータ

**列構成:**
- 施設ID
- 施設名
- 電話番号
- 郵便番号
- 都道府県
- 市区町村
- 住所
- web
- GoogleMap
- ランク
- カテゴリ
- latitude
- longitude
- 施設GID
- 営業ステータス
- phone
- 照合方法
- **post_id** ← 重複なし

### 2. integration_breakdown.txt
統合処理の詳細レポート

## 🔍 post_id重複防止の仕組み

```python
# 1. 既存post_idを収集
used_post_ids = set(matched_data) ∪ set(wordpress_only_data)

# 2. 新規post_idを割り当て（unmatched_data用）
next_id = max(used_post_ids) + 1
while next_id in used_post_ids:
    next_id += 1  # 重複回避

# 3. WordPress独自データのフィルタリング
wordpress_unique = wordpress_data - google_map_phones
```

## 📈 期待される結果

| 項目 | 件数（予想） |
|------|-------------|
| Google Map照合済み | 74,049件 |
| Google Map未照合 | 1,433件 |
| WordPress独自 | 約5,000-6,000件* |
| **合計** | **約80,000-81,000件** |

*WordPress独自データは電話番号重複を除外するため、7,172件より少なくなる

## ✅ 確認事項

実行後、以下を確認してください：

```python
import pandas as pd

df = pd.read_csv('results/integrated_data.csv')

# post_id重複チェック
duplicates = df['post_id'].value_counts()
print(duplicates[duplicates > 1])  # 空であればOK

# 件数確認
print(f"総件数: {len(df):,}")
print(f"post_id範囲: {df['post_id'].min():.0f} - {df['post_id'].max():.0f}")
```

## 🛠️ トラブルシューティング

### Q1. post_idが重複している
**A:** スクリプトを再実行してください。重複防止ロジックが動作します。

### Q2. WordPress独自データが少ない
**A:** 電話番号がGoogle Mapデータと重複するものは除外されます。これは正常です。

### Q3. unmatched_dataのpost_idが大きすぎる
**A:** 既存の最大post_idから採番するため、大きな数値になります。問題ありません。

## 📝 注意事項

- ✅ 既存のpost_idは変更しない
- ✅ 重複は完全に排除される
- ✅ 元のCSVファイルは変更されない
- ✅ いつでも再実行可能

## 🔄 再統合が必要な場合

```bash
# 元データを更新した後、再実行するだけ
python integrate_csv_data.py
```

出力ファイルは上書きされます。
