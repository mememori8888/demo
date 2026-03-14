# FID抽出ツール - 使い方ガイド

## 概要

GoogleマップのURLからFID（Facility ID）を自動抽出するツールです。CSVファイルのGoogleマップURL列を読み込み、各URLにアクセスしてリダイレクト後のURLからFIDを抽出します。

## 機能

- ✅ CSVファイルから自動的にGoogleマップURLを検出
- ✅ Seleniumを使用してURLリダイレクトを追跡
- ✅ リダイレクト後のURLからFIDを抽出
- ✅ 施設ID、施設GID、施設FIDの3列で出力
- ✅ GitHub Actionsで自動実行可能

## 使い方

### GitHub Actionsで実行（推奨）

1. **GitHubリポジトリのActionsタブに移動**
2. **"Extract FID from URLs"** を選択
3. **"Run workflow"** をクリック
4. **パラメータを入力**:
   - `input_file`: 入力CSVファイル名（例: `fid.csv`）
   - `output_file`: 出力ファイル名（デフォルト: `extracted_fid.csv`）
   - `delay`: リクエスト間の待機時間（秒）（デフォルト: 2）
   - `limit`: テスト用の最大件数（空欄で全件処理）
5. **"Run workflow"** をクリックして実行

### ローカルで実行

```bash
# 基本的な使い方
python extract_fid_from_urls.py --input results/fid.csv

# 出力ファイル名を指定
python extract_fid_from_urls.py --input results/fid.csv --output results/my_fid.csv

# 待機時間を調整（レート制限対策）
python extract_fid_from_urls.py --input results/fid.csv --delay 3

# テスト実行（最初の10件のみ）
python extract_fid_from_urls.py --input results/fid.csv --limit 10
```

## 入力ファイル形式

CSVファイルには以下のいずれかの列が必要です:

### 必須列
- **GoogleマップURL列**: `GoogleMap`, `googlemap`, `Google Map`, `URL` など
  - 自動検出されます

### オプション列
- **施設ID列**: `施設ID`, `ID`, `id`, `post_id` など
- **施設GID列**: `施設GID`, `GID`, `gid` など

### 入力例

```csv
施設ID,施設GID,GoogleMap
1,ChIJXXXXXXXXXXXXXXXXXXXX,https://www.google.com/maps/search/...
2,ChIJYYYYYYYYYYYYYYYYYYYY,https://maps.google.com/?cid=...
```

## 出力ファイル形式

出力CSVファイルは以下の形式です:

```csv
施設ID,施設GID,施設FID
82096,ChIJc5Lm4JCbA2ARZBC20BAuiBY,0x60039b90e0e69273:0x16882e10d0b61064
49662,ChIJP78spldxA2ARA41ws1thS6A,0x60037157a62cbf3f:0xa04b615bb3708d03
```

## FID抽出のロジック

### URL形式の例

リダイレクト後のGoogleマップURLは通常以下の形式です:

```
https://www.google.com/maps/place/%E6%9C%AD%E5%B9%8C%E4%B8%AD%E5%A4%AE%E6%96%8E%E5%A0%B4/@43.0533851,141.3563204,17z/data=!3m1!4b1!4m6!3m5!1s0x5f0b2986e543b8fb:0x93f2d5295cb28a5a!8m2!3d43.0533851!4d141.3563204!16s%2Fg%2F1tfdyn2w?entry=ttu
```

### 抽出パターン

スクリプトは以下のパターンでFIDを抽出します:

1. `/1s0x...` の形式
2. `!1s0x...` の形式（URLエンコード対応）
3. `data=...!1s0x...` の形式

### 抽出例

上記URLから `0x5f0b2986e543b8fb:0x93f2d5295cb28a5a` を抽出します。

## パラメータ詳細

### --input, -i (必須)
入力CSVファイルのパスまたはファイル名。
- `results/`フォルダ内のファイルの場合はファイル名のみでOK
- 例: `fid.csv` または `results/fid.csv`

### --output, -o (オプション)
出力CSVファイルのパス。
- デフォルト: `results/extracted_fid.csv`
- 例: `results/my_output.csv`

### --delay, -d (オプション)
各リクエスト間の待機時間（秒）。
- デフォルト: 2秒
- Googleのレート制限を避けるため、1秒以上を推奨

### --limit, -l (オプション)
処理する最大件数（テスト用）。
- 例: `--limit 10` で最初の10件のみ処理

## 注意事項

### レート制限
- Googleマップには厳しいレート制限があります
- `--delay` パラメータで適切な待機時間を設定してください
- 大量のデータを処理する場合は、複数回に分けて実行することを推奨

### タイムアウト
- ネットワーク状況によってはタイムアウトが発生する可能性があります
- その場合は `--limit` で小さいバッチに分けて処理してください

### エラーハンドリング
- URLが空の行はスキップされます
- FIDを抽出できない場合は警告ログが出力されます
- エラーが発生してもプログラムは継続します

## トラブルシューティング

### FIDが抽出できない

**原因1**: URLが古い形式
- 解決策: 最新のGoogleマップURLを取得してください

**原因2**: リダイレクトが正常に動作していない
- 解決策: `--delay` を増やしてページ読み込みを待つ

**原因3**: Googleのレート制限に引っかかった
- 解決策: `--delay` を3秒以上に設定し、処理を分割

### ChromeDriverのエラー

**エラー**: `chromedriver not found`
- 解決策: 
  ```bash
  # GitHub Actionsでは自動的にインストールされます
  # ローカルの場合は、ChromeDriverをインストールしてください
  ```

### メモリ不足

大量のデータを処理する場合、メモリ不足になる可能性があります。
- 解決策: `--limit` で処理を分割してください

```bash
# 例: 1000件ずつ処理
python extract_fid_from_urls.py --input results/large_file.csv --limit 1000 --output results/batch1.csv
```

## GitHub Actions でのバッチ処理例

大量データを処理する場合のワークフロー:

1. **テスト実行（10件）**
   - `limit`: 10
   - 動作確認

2. **小バッチ実行（100件）**
   - `limit`: 100
   - レート制限の確認

3. **本番実行（全件）**
   - `limit`: 空欄
   - 全データを処理

## ログの確認

処理中のログは標準出力に表示されます:

```
2025-12-03 10:00:00 - INFO - FID抽出処理開始
2025-12-03 10:00:01 - INFO - [1/100] 処理中: 施設ID=82096, GID=ChIJc5Lm4JCbA2ARZBC20BAuiBY
2025-12-03 10:00:05 - INFO -   ✓ FID抽出成功: 0x60039b90e0e69273:0x16882e10d0b61064
```

## 参考情報

### GoogleマップのURL形式

- **検索URL**: `https://www.google.com/maps/search/...`
- **Place URL**: `https://www.google.com/maps/place/...`
- **CID URL**: `https://maps.google.com/?cid=...`

いずれの形式でも、アクセス後に標準的なPlace URLにリダイレクトされます。

### FID（Facility ID）について

FIDは16進数の形式 `0xXXXX:0xYYYY` で表されるGoogleマップの施設識別子です。

- 前半部分: エリアや地域を示す
- 後半部分: 施設固有のID

## サポート

問題が発生した場合:

1. ログを確認してエラーメッセージをチェック
2. テスト実行（`--limit 10`）で動作を確認
3. `docs/SELENIUM_SETUP.md` でSeleniumの設定を確認
4. GitHubでIssueを作成

---

**最終更新**: 2025年12月3日
