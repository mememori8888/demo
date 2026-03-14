# ワークフロー選択肢の自動更新ガイド

このガイドでは、GitHub Actionsワークフローの選択肢を自動的に更新する仕組みについて説明します。

---

## 📋 概要

`webapp/files.json`の内容に基づいて、GitHub Actionsワークフローファイルの選択肢（アドレスファイルと出力ファイル）を**自動的に更新**します。

---

## 🔄 自動更新の仕組み

### 1. ファイルリストの収集

`update_file_list.py`スクリプトが以下を実行します：

1. **settingsディレクトリ**から`.csv`ファイルを取得
2. **resultsディレクトリ**から`.csv`ファイルを取得
3. `docs/webapp/files.json`に保存

### 2. ワークフローファイルの自動更新

同じスクリプトが：

1. `webapp/files.json`の内容を読み取り
2. `.github/workflows/brightdata_facility.yml`の選択肢部分を自動更新
3. 正規表現を使って該当箇所のみを置換

### 3. GitHub Actionsでの自動コミット

ワークフロー実行後、自動的に：

1. `update_file_list.py`を実行
2. 更新されたファイルをコミット
   - `docs/webapp/files.json`
   - `.github/workflows/brightdata_facility.yml`
3. Gitリポジトリにpush

---

## 🚀 使い方

### 手動での更新

新しいファイルを追加した後、手動で更新する場合：

```bash
python update_file_list.py
```

実行結果：
```
Updating file list from results and settings to docs/webapp/files.json
✅ File list saved to docs/webapp/files.json
   - Settings files: 6
   - Results files: 39

📝 Updating workflow file: .github/workflows/brightdata_facility.yml
✅ Workflow file updated successfully
   - Address CSV options: 6
   - Output file options: 39
```

### 自動更新（GitHub Actions）

ワークフローを実行すると、**自動的に**以下が実行されます：

1. 施設データ取得スクリプトの実行
2. 新しい結果ファイルの生成
3. `update_file_list.py`の実行
4. ワークフローファイルの自動更新
5. 変更のコミット・push

---

## 📂 対象ファイル

### アドレスファイル（`address_csv`）

**ソース**: `settings/*.csv`

**選択肢に追加される形式**:
```yaml
- 'settings/address.csv'
- 'settings/address_test.csv'
- 'settings/address_wordpress_only.csv'
```

### 出力ファイル（`output_file`）

**ソース**: `results/*.csv`

**選択肢に追加される形式**:
```yaml
- 'dental_new.csv'
- 'dental_review.csv'
- 'marriage_reviews.csv'
```

**制限**: 最大50件まで（GitHub Actionsの制限）

---

## ⚙️ スクリプトの詳細

### `update_file_list.py`の主な機能

#### 1. `update_file_list()`

```python
def update_file_list():
    # settingsとresultsディレクトリをスキャン
    # files.jsonを生成
    # ワークフローファイルを自動更新
```

#### 2. `update_workflow_choices()`

```python
def update_workflow_choices(workflow_file, settings_files, results_files):
    # 正規表現でワークフローファイルの選択肢部分を検索
    # 新しい選択肢リストに置き換え
```

**正規表現パターン**:

- **address_csv**: `(      address_csv:[\s\S]*?options:\n)([\s\S]*?)(        default: 'default')`
- **output_file**: `(      output_file:[\s\S]*?options:\n)([\s\S]*?)(        default: 'default')`

---

## 🔍 トラブルシューティング

### 問題: ワークフローファイルが更新されない

**原因**: 正規表現パターンが一致しない

**解決策**:
```bash
# ワークフローファイルの構文を確認
cat .github/workflows/brightdata_facility.yml | grep -A 10 "address_csv:"

# 手動で実行してエラーメッセージを確認
python update_file_list.py
```

### 問題: 選択肢が50件で制限される

**原因**: GitHub Actionsの制限

**解決策**:
- 古いファイルを削除する
- または、ファイル名のパターンでフィルタリングする

---

## 📈 メリット

✅ **手動編集不要**: ファイルが追加されると自動的に選択肢に反映  
✅ **一貫性維持**: `files.json`とワークフローファイルが常に同期  
✅ **メンテナンス削減**: YAMLファイルを手動編集する必要なし  
✅ **エラー防止**: タイポや書式ミスを防止  

---

## 🔧 カスタマイズ

### ファイルフィルタの変更

拡張子や名前パターンでフィルタリングしたい場合：

```python
# update_file_list.py の一部を修正
for file_path in glob.glob(os.path.join(results_dir, 'dental_*.csv')):
    # 歯科関連のファイルのみ
```

### 選択肢の並び順変更

```python
# 名前順
settings_files.sort()

# 更新日時順（新しい順）
results_files.sort(key=lambda x: x['last_modified'], reverse=True)
```

---

## 📝 メンテナンス

### 定期的な実行

月に1回程度、手動で実行してクリーンアップ：

```bash
# 不要なファイルを削除
rm results/old_*.csv

# ファイルリストを更新
python update_file_list.py

# コミット
git add docs/webapp/files.json .github/workflows/brightdata_facility.yml
git commit -m "Update file lists"
git push
```

---

## 📚 関連ドキュメント

- [GitHub Actions ワークフロー構文](https://docs.github.com/ja/actions/using-workflows/workflow-syntax-for-github-actions)
- [CLIENT_GUIDE.md](./CLIENT_GUIDE.md) - システム全体のガイド
- [BRIGHTDATA_EFFICIENT_PROCESSING_GUIDE.md](./BRIGHTDATA_EFFICIENT_PROCESSING_GUIDE.md) - データ処理ガイド

---

**自動更新により、ワークフローメンテナンスが大幅に簡素化されます** 🎉
