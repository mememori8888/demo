# 🚀 GitHub Actions実行ガイド - 5時間以内完了を目指す

## ⚠️ 重要な前提確認

現在の想定では：
- **総件数**: 55,000件
- **1件あたりの処理時間**: 120秒（2分）
- **目標完了時間**: 5時間

この場合、**367ワーカーが必要**ですが、これは非現実的です。

### まず実際の処理時間を確認しましょう！

## 📋 ステップ1: 小規模テストで処理時間を計測

### 1-1. テスト用CSVを作成

```bash
cat > test_small.csv << 'EOF'
url
https://maps.google.com/?cid=4943704292481018584
https://maps.google.com/?cid=1234567890123456789
https://maps.google.com/?cid=9876543210987654321
EOF
```

### 1-2. ローカルでテスト実行

```bash
# 環境変数設定
export BRIGHTDATA_API_TOKEN='your_token_here'

# 3件のテスト実行（処理時間を計測）
time python brightdata_batch_processor.py \
  --csv test_small.csv \
  --workers 1 \
  --days-limit 10 \
  --output-dir test_results
```

### 1-3. 処理時間を確認

```bash
# 結果確認
ls -lh test_results/
head -20 test_results/brightdata_results_*.csv
```

**実際の処理時間を記録してください！**
例: 3件を180秒で処理 → 1件あたり60秒

### 1-4. 必要な並列度を再計算

```python
# 計算ツールを実行
python calculate_workers.py

# または手動計算:
# 必要ワーカー数 = (総件数 × 1件あたりの時間) ÷ (目標時間 × 3600)
# 例: (55000 × 60) ÷ (5 × 3600) = 183.3 → 約200ワーカー
```

## 📊 処理時間別の推奨並列度

| 1件あたりの時間 | 5時間で完了 | 推奨ワーカー数 |
|----------------|------------|--------------|
| 30秒 | 約92ワーカー | **100** |
| 60秒（1分） | 約183ワーカー | **200** |
| 90秒（1.5分） | 約275ワーカー | **300** ⚠️ |
| 120秒（2分） | 約367ワーカー | **不可能** ❌ |

### ⚠️ レート制限の注意

- BrightData APIには通常レート制限があります
- 100-200ワーカー以上は429エラーが頻発する可能性
- **推奨**: まず50-100ワーカーでテストし、エラー率を確認

## 🎯 ステップ2: GitHub Actionsセットアップ

### 2-1. シークレットの設定

1. GitHubリポジトリの「Settings」→「Secrets and variables」→「Actions」
2. 「New repository secret」をクリック
3. 以下を追加:
   - Name: `BRIGHTDATA_API_TOKEN`
   - Value: あなたのBrightData APIトークン

### 2-2. CSVファイルをリポジトリに追加

```bash
# 本番用CSVをコミット
git add facility_urls.csv
git commit -m "Add facility URLs for processing"
git push
```

## 🚀 ステップ3: GitHub Actions実行

### 3-1. 初回実行（小規模テスト）

1. GitHubリポジトリの「Actions」タブを開く
2. 「BrightData Batch Processing」を選択
3. 「Run workflow」をクリック
4. パラメータを設定:
   ```
   CSV file path: test_small.csv
   Number of parallel workers: 10
   Days limit: 10
   Resume from checkpoint: false
   Maximum runtime in hours: 1
   ```
5. 「Run workflow」を実行

### 3-2. 結果を確認

- ワークフロー完了後、「Artifacts」から結果をダウンロード
- CSV結果を確認
- エラー率をチェック

### 3-3. 本番実行

テストで問題なければ、本番実行：

```
CSV file path: facility_urls.csv
Number of parallel workers: 100  ← テスト結果に基づいて調整
Days limit: 10
Resume from checkpoint: false
Maximum runtime in hours: 5
```

## 🔄 ステップ4: 複数回に分けて実行（推奨）

5時間で完了しない場合は、複数回に分けて実行します。

### 4-1. 初回実行

```
CSV file path: facility_urls.csv
Workers: 100
Resume: false
Max runtime: 5 hours
```

### 4-2. 2回目以降（自動再開）

初回実行が5時間でタイムアウトした場合：

```
CSV file path: facility_urls.csv
Workers: 100
Resume: true  ← ここを変更
Max runtime: 5 hours
```

**チェックポイント機能により、処理済みの分はスキップされます！**

### 4-3. 完了まで繰り返し

進捗状況はワークフロー実行後の「Summary」で確認できます：

```
Progress: 20,000 / 55,000 (36%)
Remaining: 35,000 URLs
```

完了するまで「Resume: true」で再実行を繰り返してください。

## 📊 実行例とシナリオ

### シナリオA: 1件60秒の場合

```
必要ワーカー数: 約183
推奨設定: 200ワーカー
予想完了時間: 約4.6時間（1回で完了）

実行:
1. Workers: 200, Resume: false
→ 5時間以内に完了 ✅
```

### シナリオB: 1件90秒の場合

```
必要ワーカー数: 約275
推奨設定: 150ワーカー × 2回
予想完了時間: 約9.2時間（2回で完了）

実行:
1. Workers: 150, Resume: false（5時間実行）
   → 約30,000件処理
2. Workers: 150, Resume: true（5時間実行）
   → 残り25,000件処理
→ 合計10時間で完了 ✅
```

### シナリオC: 1件120秒（2分）の場合

```
必要ワーカー数: 約367
推奨設定: 100ワーカー × 4回
予想完了時間: 約18.3時間（4回で完了）

実行:
1. Workers: 100, Resume: false（5時間） → 約15,000件
2. Workers: 100, Resume: true（5時間） → 約15,000件
3. Workers: 100, Resume: true（5時間） → 約15,000件
4. Workers: 100, Resume: true（5時間） → 約10,000件
→ 合計20時間で完了 ✅
```

## 🛠️ トラブルシューティング

### 429エラー（レート制限）が多発

```bash
# ワーカー数を減らす
Workers: 50 に変更
```

### タイムアウトエラー

```bash
# スクリプトは自動的にリトライします
# ワーカー数を減らして安定性を向上
Workers: 50-100 に変更
```

### メモリ不足

```bash
# バッチ処理スクリプトは逐次保存なので問題ないはず
# GitHub Actionsのランナーメモリ: 7GB
```

## 📈 最適化のヒント

### 1. 段階的にワーカー数を増やす

```
1回目: Workers 50  → エラー率確認
2回目: Workers 100 → エラー率確認
3回目: Workers 150 → エラー率確認（エラー率10%以下なら採用）
```

### 2. データを分割して並列実行

55,000件を複数のファイルに分割して、複数のワークフローを同時実行：

```bash
# ファイル分割
split -l 11000 facility_urls.csv facility_part_

# 5つのワークフローを同時実行
Part 1: facility_part_aa (11,000件) - Workers: 100
Part 2: facility_part_ab (11,000件) - Workers: 100
Part 3: facility_part_ac (11,000件) - Workers: 100
Part 4: facility_part_ad (11,000件) - Workers: 100
Part 5: facility_part_ae (11,000件) - Workers: 100

→ 約1-2時間で完了（5つ並列実行）
```

### 3. 時間帯を分散

BrightData APIの混雑状況によって速度が変わる可能性：

```
- 日本時間深夜に実行（米国昼間を避ける）
- 複数回に分けて実行時間を分散
```

## 🎉 まとめ

### クイックスタート

```bash
# 1. 小規模テスト
python brightdata_batch_processor.py \
  --csv test_small.csv --workers 1

# 2. 処理時間を確認（例: 60秒/件）

# 3. GitHub Actions実行（Workers: 200）
#    → 5時間以内に完了！

# 4. 完了しない場合は Resume: true で再実行
```

### 推奨アプローチ

1. **まずテスト**: 3-10件で実際の処理時間を計測
2. **並列度計算**: `calculate_workers.py`で最適なワーカー数を算出
3. **小規模実行**: 100件程度で本番環境テスト
4. **本番実行**: チェックポイント機能を活用して安全に処理

### 成功の鍵

- ✅ 実際の処理時間を正確に把握する
- ✅ レート制限を考慮したワーカー数設定
- ✅ チェックポイント機能で安全に再開
- ✅ 100件ごとにCSVが自動保存される
- ✅ 途中で終了してもデータは保存される

これで55,000件を安全かつ効率的に処理できます！🚀
