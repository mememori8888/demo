# Stage1: 安全なスナップショット送信戦略

## 🛡️ API Rate Limit対策

### 実装した安全機能

#### 1️⃣ **リクエスト間の待機時間**
```
Request 1 → Wait 5s → Request 2 → Wait 5s → Request 3
```
- デフォルト: **5秒**
- カスタマイズ可能: `--wait-between-requests` パラメータ

#### 2️⃣ **Rate Limit検出時の自動待機**
```
Request → 429 Error → Wait 60s → Retry
```
- 429エラー検出時: **60秒待機**
- 自動リトライで続行

#### 3️⃣ **定期的な進捗保存**
```
10 snapshots → Auto-save → Continue → 10 more → Auto-save
```
- デフォルト: **10スナップショットごと**
- エラー発生時でも再開可能

#### 4️⃣ **エラー時の継続処理**
```
Snapshot 1 ✅ → Snapshot 2 ❌ → Snapshot 3 ✅ (継続)
```
- 一部失敗しても処理継続
- 失敗カウントを記録

## 📊 リクエストフロー

```
CSVファイル (17,000施設)
    ↓
CSV Batch 1 (500施設)
    ↓
API Chunk 1 (50 URLs) → ⏳ 5s待機
    ↓
API Chunk 2 (50 URLs) → ⏳ 5s待機
    ↓
...
    ↓
API Chunk 10 (50 URLs) → 💾 進捗保存
    ↓
CSV Batch 2 (500施設)
    ↓
...
```

## ⚙️ 推奨設定

### 小規模処理（~100施設）
```yaml
csv_batch_size: 100
api_batch_size: 50
wait_between_requests: 3
save_interval: 5
```
- **所要時間**: 約10-15分
- **安全性**: 高

### 中規模処理（~1,000施設）
```yaml
csv_batch_size: 500
api_batch_size: 50
wait_between_requests: 5  # デフォルト
save_interval: 10
```
- **所要時間**: 約1.5-2時間
- **安全性**: 高

### 大規模処理（~10,000施設）
```yaml
csv_batch_size: 500
api_batch_size: 50
wait_between_requests: 5
save_interval: 20
```
- **所要時間**: 約15-20時間
- **安全性**: 高
- **推奨**: 複数地域に分割して並行実行

## 💡 ベストプラクティス

### 1. 地域別に分割実行
```bash
# 並行実行可能（各1-2時間）
Stage1 → hokkaido.csv (1,500施設)
Stage1 → tohoku.csv (1,800施設)  
Stage1 → kanto.csv (3,000施設)
```

### 2. 時間帯の分散
```bash
# 朝: 小規模地域
08:00 - Stage1 → hokkaido.csv

# 昼: 中規模地域  
12:00 - Stage1 → tohoku.csv

# 夜: 大規模地域
18:00 - Stage1 → kanto.csv
```

### 3. エラー発生時の対応
```bash
# 同じパラメータで再実行（既存データは保持）
# 失敗した部分のみリトライ可能
Stage1 → 再実行 (--start-batch N)
```

## 📈 実行時間の計算

### 計算式
```
総時間 = (施設数 / API_BATCH_SIZE) × (待機時間 + API処理時間)
```

### 実例（1,000施設の場合）
```
API requests = 1,000 / 50 = 20回
待機時間 = 20 × 5秒 = 100秒
API処理時間 = 20 × 5秒 ≈ 100秒
---
総時間 ≈ 200秒 ≈ 3-4分
```

## 🚨 トラブルシューティング

### 429 Rate Limit エラーが多発
→ `wait_between_requests` を増やす（例: 10秒）

### タイムアウトが発生
→ `api_batch_size` を減らす（例: 25）

### 処理が遅すぎる
→ 地域別に分割して並行実行

## ✅ 安全性チェックリスト

- ✅ リクエスト間に5秒以上の待機
- ✅ 10スナップショットごとに自動保存
- ✅ 429エラー時の自動待機
- ✅ エラー発生時も処理継続
- ✅ 進捗状況のリアルタイム表示
- ✅ 再実行時の重複防止

## 📝 ログ例

```
📦 Processing Configuration:
   - CSV Batch Size: 500
   - API Batch Size: 50
   - Total Batches: 34
   - Starting from: Batch 1
   - Wait between requests: 5s
   - Auto-save interval: Every 10 snapshots

============================================================
🚀 CSV Batch 1/34
   Rows: 1 - 500
============================================================
📦 URLs in batch: 275

📤 API Chunk 1/6 (50 URLs)
✅ Snapshot sd_xxx recorded (50 URLs)
⏳ Waiting 5s before next request...

📤 API Chunk 2/6 (50 URLs)
✅ Snapshot sd_yyy recorded (50 URLs)
⏳ Waiting 5s before next request...

...

💾 Auto-saving progress (10 snapshots)...
💾 Saved 10 snapshot records
```

これにより、安全かつ効率的にスナップショットを送信できます！
