# 介護施設取得スクリプト

## 概要
Bright Data Web Scraper APIを使用して、Google Mapsから介護施設のリストを取得するPythonプログラムです。

## 機能
- ✅ **非同期処理**: `/datasets/v3/trigger` → `/snapshot` の2段階処理
- ✅ **重複チェック**: 施設IDとURLで重複を自動除外
- ✅ **地域フィルタ**: コスト削減のため特定都道府県のみ対象
- ✅ **複数キーワード対応**: 介護施設、老人ホーム、グループホーム
- ✅ **コスト予測**: 実行前に予想コストを表示

## 対象地域
以下の4都道府県に限定（コスト削減のため）:
- 東京都
- 神奈川県
- 大阪府
- 愛知県

## 検索キーワード
- 介護施設
- 老人ホーム
- グループホーム

## 料金
- **$1.5 / 1000レコード**
- 各クエリで最大100件取得
- 予想コスト: 実行前にログに表示されます

## セットアップ

### 1. 必要なパッケージのインストール
```bash
pip install requests pandas
```

### 2. 入力ファイルの準備
`settings/address.csv` が必要です:
```csv
a,b
東京都,渋谷区
東京都,新宿区
神奈川県,横浜市
...
```

### 3. API設定
APIトークンは以下の方法で設定できます:

**方法1: 環境変数**
```bash
export BRIGHTDATA_API_TOKEN='51396ae0-f0b3-4897-87e9-de2441a65976'
```

**方法2: コードに埋め込み済み**
デフォルトでコードに含まれています（すでに設定済み）

## 使い方

### テスト実行（推奨）
まずは小規模なテストで動作確認:
```bash
python test_care_facilities.py
```

このテストでは:
- 大阪府大阪市の介護施設を10件だけ取得
- APIの応答形式を確認
- データ構造を表示

### 本番実行
```bash
python get_care_facilities.py
```

## 出力

### 出力ファイル
`results/care_facilities.csv` (UTF-8 BOM付き、Excel対応)

### 出力カラム
| カラム名 | 説明 |
|---------|------|
| 施設名 | 介護施設の名前 |
| 住所 | 所在地 |
| 電話番号 | 連絡先 |
| GoogleMap URL | Google Mapsのリンク |
| 施設ID | 一意の識別子（GIDまたはplace_id） |

## 重複チェックの仕組み
1. 既存の `care_facilities.csv` を読み込み
2. 施設IDまたはURLで重複を判定
3. 新規施設のみを追記

既存データは自動的に保持されます。

## ログ
実行中のログには以下が表示されます:
- 📤 API リクエスト送信
- ⏳ スナップショット完了待機
- 📥 データダウンロード
- 💰 コスト情報（予測と実績）
- ✅ 取得件数

## トラブルシューティング

### エラー: "snapshot_idが取得できませんでした"
**原因**: APIトークンまたはデータセットIDが不正

**対処**:
1. APIトークンを確認: `51396ae0-f0b3-4897-87e9-de2441a65976`
2. データセットIDを確認: `gd_lpov5p5dn6g5eipuo`
3. Bright Dataのダッシュボードで確認

### エラー: "タイムアウト"
**原因**: クエリ数が多すぎる、またはAPIの処理に時間がかかっている

**対処**:
1. `max_wait_minutes` を増やす（デフォルト30分）
2. クエリ数を減らす（TARGET_PREFECTURESを調整）

### データが取得できない
**原因**: レスポンスフォーマットが想定と異なる

**対処**:
1. `test_care_facilities.py` でデータ構造を確認
2. `parse_facility_data` メソッドを調整

## コスト管理

### 予想コストの確認
実行前にログに表示されます:
```
💰 コスト予測:
   クエリ数: 500 件
   予想レコード数: 50,000 件
   予想コスト: $75.00 USD
```

### コスト削減のヒント
1. **地域を絞る**: `TARGET_PREFECTURES` を調整
2. **取得件数を減らす**: `limit_per_query` を調整（デフォルト100）
3. **キーワードを減らす**: `CARE_KEYWORDS` を調整

## カスタマイズ

### 対象地域の変更
`get_care_facilities.py` の `TARGET_PREFECTURES` を編集:
```python
TARGET_PREFECTURES = ['北海道', '福岡県']  # 例: 北海道と福岡県のみ
```

### キーワードの追加
`CARE_KEYWORDS` に追加:
```python
CARE_KEYWORDS = ['介護施設', '老人ホーム', 'グループホーム', 'デイサービス']
```

### 取得件数の変更
`main()` 関数内の `limit_per_query` を調整:
```python
fetcher.run(
    keywords=CARE_KEYWORDS,
    target_prefectures=TARGET_PREFECTURES,
    limit_per_query=50  # 100 → 50 に変更
)
```

## 技術仕様

### API仕様
- **エンドポイント**: `https://api.brightdata.com/datasets/v3`
- **認証**: Bearer Token
- **データセット**: Google Maps Search (Discovery)
- **フォーマット**: JSON

### 処理フロー
1. 既存データ読み込み
2. address.csvからクエリ生成
3. `/trigger` でジョブ開始 → snapshot_id取得
4. `/snapshot/{snapshot_id}` で完了待機（15秒間隔ポーリング）
5. `/snapshot/{snapshot_id}?format=json` でデータダウンロード
6. データ解析・重複除外
7. CSV保存（既存データに追記）

## 参考資料
- [Bright Data Web Scraper API ドキュメント](https://docs.brightdata.com/scraping-automation/web-scraper-api/overview)
- [Google Maps スクレイパー](https://brightdata.com/products/web-scraper/google-maps)
