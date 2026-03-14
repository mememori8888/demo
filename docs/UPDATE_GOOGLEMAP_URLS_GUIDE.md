# GoogleMap URL更新ツール

このツールは、CSVファイル内のGoogleMapURLをリダイレクト後の最終URLに更新します。

## 機能

- CSVファイルのGoogleMap列を自動検出
- 各URLにアクセスしてリダイレクト後の最終URLを取得
- 元のCSVファイルを直接更新（バックアップ作成）
- 並列処理で高速化

## 使用方法

### GitHub Actionsで実行（推奨）

1. **GitHubのリポジトリページに移動**
2. **「Actions」タブをクリック**
3. **左サイドバーから「Update GoogleMap URLs」を選択**
4. **「Run workflow」ボタンをクリック**
5. **パラメータを設定:**
   - **更新するCSVファイル名:** `dental_new.csv`（例）
   - **待機時間（秒）:** `2`（デフォルト）
   - **並列実行数:** `4`（デフォルト）
   - **処理する最大件数:** 空欄（全件処理）またはテスト用に少ない数
   - **バックアップを作成しない:** チェックを外す（推奨）

6. **「Run workflow」をクリックして実行開始**

### ローカルで実行

```bash
# 基本的な使用方法
python update_googlemap_urls.py --input results/dental_new.csv

# オプション付き
python update_googlemap_urls.py \
  --input results/dental_new.csv \
  --delay 2 \
  --workers 4 \
  --limit 10

# バックアップなしで実行（非推奨）
python update_googlemap_urls.py \
  --input results/dental_new.csv \
  --no-backup
```

## コマンドラインオプション

| オプション | 説明 | デフォルト |
|----------|------|-----------|
| `--input` | 入力CSVファイルパス（必須） | - |
| `--delay` | 各リクエスト間の待機時間（秒） | 2 |
| `--workers` | 並列実行数 | 4 |
| `--limit` | 処理する最大件数（テスト用） | なし（全件） |
| `--no-backup` | バックアップを作成しない | false |

## バックアップについて

- デフォルトでは、処理前に元のファイルをバックアップします
- バックアップファイル名: `元のファイル名.backup_YYYYMMDD_HHMMSS`
- 例: `dental_new.csv.backup_20260126_153045`

## 処理の流れ

1. **入力ファイルの検証**
   - ファイルの存在確認
   - GoogleMap列の検出

2. **バックアップ作成**
   - 元のファイルをタイムスタンプ付きでバックアップ

3. **URL処理**
   - 各行のGoogleMap URLにアクセス
   - リダイレクト後の最終URLを取得
   - 並列処理で高速化

4. **ファイル更新**
   - 取得したURLで元のCSVを更新
   - 元のファイル構造を保持

5. **結果レポート**
   - 処理件数、成功件数、エラー件数を表示

## 対応するGoogleMap列名

以下の列名を自動検出します（大文字小文字区別なし）:

- `GoogleMap`
- `Google Map`
- `google_map`
- `Googleマップ`
- `URL`
- `map_url`
- `Map URL`

## 注意事項

### 重要な警告

⚠️ **このツールは元のCSVファイルを直接更新します**

- バックアップが自動作成されますが、念のため手動でもバックアップすることを推奨します
- テスト実行時は `--limit` オプションで件数を制限してください

### 処理時間

- 1件あたり約2〜5秒かかります
- 1000件の場合、約30分〜1時間程度
- 並列実行数を増やすと高速化しますが、Googleからブロックされる可能性があります

### エラーハンドリング

- URLにアクセスできない場合は、元のURLをそのまま保持します
- エラーが発生した行は処理完了後にレポートされます

## トラブルシューティング

### GoogleMap列が見つからない

```
❌ GoogleMap列が見つかりません
```

→ CSVファイルのヘッダー行を確認し、GoogleMap関連の列名があるか確認してください

### ファイルが見つからない

```
❌ 入力ファイルが見つかりません
```

→ ファイルパスが正しいか確認してください。`results/`フォルダ内にファイルがあるか確認してください

### リダイレクトが取得できない

一部のURLでリダイレクトが取得できない場合:
- 待機時間を増やす (`--delay 3` など)
- 並列実行数を減らす (`--workers 2` など)

## 使用例

### テスト実行（10件のみ）

```bash
python update_googlemap_urls.py \
  --input results/dental_new.csv \
  --limit 10
```

### 本番実行（全件処理）

```bash
python update_googlemap_urls.py \
  --input results/dental_new.csv \
  --delay 2 \
  --workers 4
```

### 高速実行（並列数を増やす）

```bash
python update_googlemap_urls.py \
  --input results/dental_new.csv \
  --delay 1 \
  --workers 8
```

## 出力例

```
📖 ファイルを読み込んでいます: results/dental_new.csv
✓ 500行のデータを読み込みました
✓ GoogleMap列を発見: 'GoogleMap' (インデックス: 8)
🔄 500件のURLを処理します...
[1/500] 行2: 更新完了
[2/500] 行3: 更新完了
...
📝 CSVファイルを更新しています...

============================================================
✅ 処理完了
============================================================
📊 処理結果:
  - 総行数: 500行
  - 処理対象: 500件
  - 更新成功: 485件
  - エラー: 15件
  - 変更なし: 0件

💾 元のファイルはバックアップされています: results/dental_new.csv.backup_20260126_153045
📄 更新されたファイル: results/dental_new.csv
```
