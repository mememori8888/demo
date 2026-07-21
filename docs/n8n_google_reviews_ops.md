# n8n Google Reviews 操作ガイド

このn8n構成は、既存のPython処理を置き換えるものではなく、手動実行しやすい操作画面として使います。

## できること

- ローカルPCのGoogleログイン済みChromeプロファイルを使って関連度ランクを取得する
- 10件テスト、途中再開、全件実行をn8n画面から切り替える
- 実行ログ、summary、detail、unmatched CSVの場所をn8n画面で確認する
- 失敗施設があっても続けるか、異常時に止めるかを設定で切り替える

## 初回起動

PowerShellで以下を実行します。

```powershell
cd D:\python\demo\demo
powershell.exe -ExecutionPolicy Bypass -File .\n8n\start_n8n_windows.ps1
```

n8nが起動したら、ブラウザで以下を開きます。

```text
http://localhost:5678
```

## ワークフローの取り込み

n8n画面で `Import from file` を選び、以下のファイルを読み込みます。

```text
D:\python\demo\demo\n8n\google_reviews_local_relevance_workflow.json
```

## 10件テスト

取り込み直後の初期値は10件テストです。

- `rank_limit`: `10`
- `start`: `1`
- `limit`: `10`
- `allow_failures`: `true`

n8n上で `Execute workflow` を押すと、以下のPowerShellラッパー経由でローカル関連度取得が動きます。

```text
D:\python\demo\demo\n8n\run_local_relevance.ps1
```

## 途中から再開

`Edit run settings` ノードを開き、以下を変更します。

- `start`: 再開したい施設番号。1始まり。
- `limit`: 実行する施設数。空ではなく、全件に近い数を指定する場合もまず小さく試してください。
- `allow_failures`: 失敗施設があっても進めるなら `true`、異常時に止めるなら `false`。

例:

```text
start = 401
limit = 100
```

## 全件に近い実行

まず100件程度で動作確認してから、`limit` を大きくします。

長時間実行では、PCのスリープを切ってください。Chromeプロファイルを使うため、同じプロファイルを別のChromeで開いたままにしない方が安定します。

## 出力ファイル

初期設定では以下に出力されます。

```text
C:\Users\user\Downloads\dental_reviews.csv
C:\Users\user\Downloads\relevance_rank_summary_local.csv
C:\Users\user\Downloads\relevance_rank_detail_local.csv
C:\Users\user\Downloads\relevance_rank_unmatched_reviews_local.csv
```

## よく使う設定

### 新規レビューだけに関連度を付ける

`recent_review_glob` に新規取得分のCSVを指定します。

```text
D:\python\googlemap\results\increments\reviews_increment_XXXXXXXX.csv
```

複数ファイルを対象にする場合はワイルドカードを使います。

```text
D:\python\googlemap\results\increments\*.csv
```

### 既存ランクを消して付け直す

既存スクリプト側で対象施設の関連度列だけを更新します。レビュー本文、レビューGID、施設IDなどの既存列は変更しません。

### 失敗時に止めたい

`allow_failures` を `false` にします。

レビューが0件、Google Maps表示異常、ログイン画面などで止まりやすくなります。全件実行の前の検証に使います。

## 注意

- n8nはWindowsローカルで動かしてください。Docker上のn8nでは、Windows側のChromeプロファイルやファイルに触りにくいため、この用途には向きません。
- SERP APIの `/reviews?fid=` が空を返す問題はn8nでは解決しません。このワークフローはローカル直接スクレイピング用です。
- GitHub ActionsでBright Dataレビュー取得を行い、その後このn8nワークフローでローカル関連度ランクを付ける流れが基本です。
