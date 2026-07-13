# BrightDataサポート問い合わせ文（2026-07-13作成）

以下をそのままコピーしてBrightDataサポートに送信してください。

---

## 件名

SERP API (zone: serp_api2) 経由でGoogleマップのレビュー本文を取得できない（bodyが常に空）

## 本文

お世話になっております。
SERP API製品のゾーン `serp_api2` を使用して、Googleマップの施設レビュー本文を取得しようとしていますが、リクエスト自体は成功（HTTPステータス200、エラーコードなし）するものの、返ってくる `body` が常に空（`"{}"`）になってしまい、レビュー本文を取得できません。

### 実行環境
- Zone: `serp_api2`（SERP API）
- エンドポイント: `https://api.brightdata.com/request`
- 用途: Googleマップの特定施設（place ID / fid指定）のレビューを、関連度順（またはその他の並び順）で本文付きで取得したい

### 試したリクエストと結果

**パターン1: `google.com/reviews?fid=...` + `brd_json=1`（正しい16進数fid形式）**

リクエスト:
```json
{
  "zone": "serp_api2",
  "url": "https://www.google.com/reviews?fid=0x6000e2cfeb9f9daf:0x8eb9dda76a18ba2f&hl=ja&sort=qualityScore&brd_json=1",
  "format": "json",
  "data_format": "parsed",
  "method": "GET"
}
```

結果:
```json
{
  "status_code": 200,
  "headers": { "host": "unblocker-parser-6f85c9fcdb-rxpvr", "content-type": "application/json", ... },
  "body": "{}"
}
```
→ `sort=newestFirst` に変更しても同様に `body: "{}"`。

**パターン2: `google.com/maps/place/data=!3m1!4b1!4m2!3m1!1s{fid}` + `brd_json=1`**

結果: `body` に `place` オブジェクト（title / address / phone / rating / **reviews_cnt**（件数のみ）等）は返るが、レビュー本文の配列（reviews）は含まれない。

**パターン3: 完全な正規URL（`https://www.google.com/maps/place/{店名}/@{lat},{lng},17z/data=...?entry=ttu&g_ep=...`）+ `brd_json=1`**

→ パターン2と同一の `place` スキーマが返り、レビュー本文は含まれない。

**パターン4: `format=raw`（生HTML取得）**

結果:
```
This endpoint has been disabled due to low success rate, please add &brd_json=1 to URL to retrieve parsed results
```
→ このゾーンでは生HTML取得自体が無効化されている。

### 確認したいこと

1. `serp_api2`（SERP API製品）のゾーンで、Googleマップの**レビュー本文**を関連度順・新着順などで取得する**正しいリクエスト形式**（URL・パラメータ）を教えてください。
2. もしSERP API製品ではGoogleマップのレビュー本文取得に対応していない場合、対応している製品（例: Web Unlocker、Web Scraper API / Datasets等）と、その場合の推奨リクエスト形式を教えてください。
3. 上記いずれのリクエストも `status_code: 200` でエラーは出ていませんが、`body` が空になる原因（対象施設に有効なレビューが無い、fidの解釈方法が異なる、ゾーン設定不足など）に心当たりがあれば教えてください。

よろしくお願いいたします。

---

## 参考: すでに正常動作している取得方法

同アカウントの **Dataset API**（`dataset_id: gd_luzfs1dn2oa0teb81`, Google Maps Reviews）経由では、実際にレビュー本文（投稿者名・評価・本文・日時等）を正常に取得できています。SERP API経由での関連度ランク取得ができない場合、こちらの方法を継続利用する想定です。
