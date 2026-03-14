# エラーハンドリング実装サマリー

## 実装日時
2026年1月6日

## 実装内容

3つのPythonプログラムに必須データチェックとGitHub Issue自動作成機能を追加しました。

---

## 1. extract_fid_from_urls.py

### 追加された機能

#### ✅ GitHub Issue作成関数
- `create_github_issue(title, body, labels)` - GitHub APIを使用してIssue作成

#### ✅ 必須データバリデーション関数
- `validate_required_columns(headers, rows, input_file)` - CSVの必須列をチェック

### チェック項目

1. **GoogleマップURL列** (必須)
   - 列名例: `GoogleMap`, `URL`, `google_map`
   - データの存在チェック

2. **施設ID列** (推奨)
   - 列名例: `施設ID`, `ID`, `facility_id`

3. **施設GID列** (推奨)
   - 列名例: `施設GID`, `GID`, `facility_gid`

4. **CSV空チェック**
   - データ行が存在するか

### エラー時の動作

- ❌ エラーメッセージをコンソールとログに出力
- 🔔 GitHub Issueを自動作成
- 🛑 `sys.exit(1)` でプログラムを終了

---

## 2. facility_BrightData_20_update.py

### 追加された機能

#### ✅ GitHub Issue作成関数
- `create_github_issue(title, body, labels)` - GitHub APIを使用してIssue作成

### チェック項目

1. **BRIGHTDATA_API_TOKEN環境変数** (必須)
   - BrightData APIのアクセストークン
   - 存在しない場合 → Issue作成 + `SystemExit(1)`

2. **住所データ** (必須)
   - ヒートマップファイル または 住所リストファイル
   - データが空の場合 → Issue作成 + `SystemExit(1)`

3. **既存施設ファイルの読み込み**
   - ID取得失敗時 → Issue作成 + `SystemExit(1)`

### エラー時の動作

- ❌ エラーメッセージをコンソールとログに出力
- 🔔 GitHub Issueを自動作成
- 🛑 `raise SystemExit(1)` でプログラムを終了

---

## 3. reviews_BrightData_50.py

### 追加された機能

#### ✅ GitHub Issue作成関数
- `create_github_issue(title, body, labels)` - GitHub APIを使用してIssue作成

### チェック項目

1. **settings.json** (必須)
   - タスク設定ファイル
   - 存在しない場合 → Issue作成 + 空リスト返却

2. **FID CSVファイル** (必須)
   - 列: `施設FID`, `施設ID`, `施設GID`
   - FID形式: `0x123abc:0x456def`
   - 存在しない場合 → Issue作成 + 空リスト返却

3. **BRIGHTDATA_API_TOKEN環境変数** (必須)
   - BrightData APIのアクセストークン
   - 存在しない場合 → Issue作成 + `None`返却

4. **CSV空チェック**
   - データ行が存在するか → Issue作成 + `sys.exit(1)`

5. **FID列の検出**
   - FIDパターンに一致する列があるか → Issue作成 + 空リスト返却

6. **処理範囲のデータ**
   - 指定された範囲にデータが存在するか → Issue作成 + `sys.exit(1)`

### エラー時の動作

- ❌ エラーメッセージをコンソールとログに出力
- 🔔 GitHub Issueを自動作成
- 🛑 エラー内容に応じて適切に終了

---

## GitHub Issue作成の仕様

### 環境変数

```bash
GITHUB_TOKEN          # GitHub APIトークン（必須）
GITHUB_REPOSITORY_OWNER  # リポジトリオーナー（デフォルト: mememori8888）
GITHUB_REPOSITORY_NAME   # リポジトリ名（デフォルト: googlemap）
```

### Issueの内容

各Issueには以下が含まれます:

1. **タイトル**: `[スクリプト名] エラーの種類`
2. **本文**:
   - エラー内容
   - エラー詳細
   - ファイル情報
   - 必須データの説明
   - 具体的な対応方法
3. **ラベル**: `bug`, `data-error`/`config-error`, `automated`

### 動作条件

- ✅ GitHub Actions: 自動的に`GITHUB_TOKEN`が設定される
- ⚠️ ローカル実行: `GITHUB_TOKEN`がない場合は警告のみ（処理は終了）

---

## テスト状況

### 構文チェック
- ✅ `extract_fid_from_urls.py` - エラーなし
- ✅ `facility_BrightData_20_update.py` - エラーなし  
- ✅ `reviews_BrightData_50.py` - エラーなし

### VS Code エラーチェック
- ✅ 全ファイル - エラーなし

---

## 使用例

### extract_fid_from_urls.py

```bash
# 正常実行
python extract_fid_from_urls.py --input results/facility.csv

# エラー例: GoogleMap列がない
❌ GoogleマップURL列が見つかりません
利用可能な列: 施設ID, 施設名, 住所

✅ GitHub Issueを作成しました: https://github.com/mememori8888/googlemap/issues/XX
```

### facility_BrightData_20_update.py

```bash
# エラー例: APIトークンがない
ERROR: BRIGHTDATA_API_TOKEN環境変数が設定されていません。

✅ GitHub Issueを作成しました: https://github.com/mememori8888/googlemap/issues/XX
```

### reviews_BrightData_50.py

```bash
# エラー例: FIDファイルがない
❌ FID CSV not found: results/fid.csv

✅ GitHub Issueを作成しました: https://github.com/mememori8888/googlemap/issues/XX
```

---

## まとめ

### 実装済み機能
- ✅ 必須データの自動チェック
- ✅ 詳細なエラーメッセージ表示
- ✅ GitHub Issue自動作成
- ✅ 適切なプログラム終了処理
- ✅ GitHub Actions対応

### メリット
1. **早期エラー検出**: 実行前に必須データをチェック
2. **自動通知**: 問題が発生したら自動的にIssue作成
3. **デバッグ支援**: 詳細なエラー情報と対応方法を提供
4. **運用効率化**: GitHub Actionsで自動実行時も確実にエラーを把握

### 注意事項
- ローカル実行時にGitHub Issue作成を有効にするには`GITHUB_TOKEN`の設定が必要
- GitHub Actionsでは自動的に`GITHUB_TOKEN`が利用可能
- Issueには`automated`ラベルが付与されるため、手動Issueと区別可能
