# 変更レポート — プライベートリポジトリ分離（2026-04-20）

## 背景

`mememori8888/demo`（公開リポジトリ）に存在していた `settings/` と `results/` フォルダ（住所CSV・スクレイピング結果等のデータ）を、`mememori8888/googlemap`（プライベートリポジトリ）に移動し、データベースとして分離した。

---

## 完成したアーキテクチャ

```
demo（公開）                          googlemap（プライベート／データベース）
├── Pythonスクリプト                  ├── settings/
├── .github/workflows/                │   ├── settings.json
├── docs/webapp/                      │   └── *.csv
│   ├── app.js                        └── results/
│   └── files.json（自動生成）            └── *.csv（スクレイピング結果）
└── .gitignore
    └── settings/, results/ を無視済み
```

### ワークフロー実行時の共通フロー

```
1. demo をチェックアウト
2. googlemap を private-data/ にチェックアウト（PRIVATE_REPO_PAT使用）
3. settings/ と results/ をワークスペースにコピーイン
4. スクリプト実行（相対パスで自然に動作）
5. 処理結果を private-data/results/ にコピーアウト → googlemap にプッシュ
6. demo には docs/webapp/files.json のみコミット
```

---

## 変更ファイル一覧

### 新規作成

| ファイル | 内容 |
|---------|------|
| `faiility_brightdata_new_version.py` | `PRIVATE_DATA_ROOT` を自動検出し、CWDをデータルートに設定して `facility_BrightData_20.py` を起動するラッパー |
| `reviews_brightData_new_version.py` | 同上。`run_reviews_local_interactive.py` を起動するラッパー |

#### データルート検出の優先順位（両ラッパー共通）

```
1. PRIVATE_DATA_ROOT 環境変数
2. /workspaces/googlemap（Codespaces標準パス）
3. カレントディレクトリ（フォールバック）
```

---

### 修正ファイル

#### `update_file_list.py`

- `_detect_data_root()` 関数を追加
- データ読み込み元を `results/` `settings/` から以下の優先順位で自動検出するよう変更：
  - `PRIVATE_DATA_ROOT` 環境変数
  - `private-data/`（GitHub Actions でのチェックアウト先）
  - `/workspaces/googlemap`

#### `docs/webapp/app.js`

- GitHub APIで `demo/settings` `demo/results` を取得するライブフェッチを削除
- `files.json` のみを参照するシンプルな設計に変更
  - 理由: プライベートリポジトリのファイル一覧はGitHub APIで取得不可

#### `.gitignore`

- `settings/` と `results/` を追加済み（demo リポジトリにデータがコミットされないよう保護）

---

### ワークフロー修正

#### `.github/workflows/brightdata_facility.yml`

| 変更前 | 変更後 |
|--------|--------|
| `settings/` `results/` がリポジトリ内に存在する前提 | `private-data/` からコピーイン |
| `python facility_BrightData_20.py` | `python faiility_brightdata_new_version.py` |
| `git add results/ settings/` してdemoにコミット | `private-data/` にコピーアウト→googlemapにプッシュ |

#### `.github/workflows/brightdata_reviews.yml`

| 変更前 | 変更後 |
|--------|--------|
| `settings/` `results/` がリポジトリ内に存在する前提 | `private-data/` からコピーイン |
| `git add results/` してdemoにコミット | `private-data/` にコピーアウト→googlemapにプッシュ |
| `docs/webapp/files.json` もコミット | `files.json` のみdemoにコミット（変更あれば） |

#### `.github/workflows/reviews_local_interactive_sequential.yml`

| 変更前 | 変更後 |
|--------|--------|
| `git pull origin main` で最新CSV取得 | `private-data/` からコピーイン |
| バリデーション: エラーメッセージのみ | エラー時に `private-data/results/` の一覧を表示 |
| バッチ処理後 demo にコミット | `private-data/` にコピーアウト→googlemapにプッシュ |

#### `.github/workflows/issue-ops-universal.yml`

| ジョブ | 変更内容 |
|--------|---------|
| `parse-and-route` (Estimate Cost) | ファイル行数読み込みを削除。パラメータベースの見積もりに変更（プライベートデータのため） |
| `validate-request` | `private-data/` チェックアウト追加。ファイル存在チェックを `data_path()` 経由に変更 |
| `run-facility` | `private-data/` チェックアウト追加。`facility_BrightData_20.py` → `faiility_brightdata_new_version.py` に変更。結果をgooglemapに保存 |
| `report-completion` | `settings/settings.json` 直接読み込みを削除。完了レポートのリンクをgooglemapリポジトリURLに変更 |

#### `.github/workflows/generate-file-list.yml`

| 変更前 | 変更後 |
|--------|--------|
| `settings/**` `results/**` のpushトリガー | `workflow_dispatch` のみ（demoに存在しないため） |
| `settings/` `results/` を sparse-checkout | `private-data/` にチェックアウト |
| ローカルのファイルを読込 | `private-data/` からファイル一覧を生成 |

---

## データ移行状況

| 作業 | 状態 |
|-----|-----|
| `demo` のGitから `settings/` `results/` を削除 | ✅ 完了（commit `3e9a8da`） |
| `.gitignore` に `settings/` `results/` を追加 | ✅ 完了 |
| `googlemap` リポジトリに `settings/` `results/` を移動 | ✅ 完了 |
| `googlemap` リポジトリからPythonコード・ワークフロー等を削除 | ✅ 完了 |

---

## 必要な設定（要対応）

| 設定 | 場所 | 内容 |
|-----|-----|-----|
| `PRIVATE_REPO_PAT` | [demo の GitHub Secrets](https://github.com/mememori8888/demo/settings/secrets/actions) | `repo` スコープのPAT。全ワークフローが `mememori8888/googlemap` にアクセスするために必須 |

### PAT の作成手順

1. GitHub → Settings → Developer settings → Personal access tokens (classic)
2. `repo` スコープを選択して生成
3. `mememori8888/demo` の Settings → Secrets and variables → Actions → New repository secret
4. 名前: `PRIVATE_REPO_PAT`、値: 生成したトークンを貼り付け
