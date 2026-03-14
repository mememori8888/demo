# ローカルPC実行ガイド

このツールを自分のPC（Windows/Mac/Linux）で実行する方法を説明します。

## 📋 必要なもの

1. **Python 3.8以上**
2. **BrightData APIトークン**
3. **dental_new.csv または dental_new_hokkaido.csv**

---

## 🪟 Windows での実行

### 1. Pythonのインストール

1. https://www.python.org/downloads/ にアクセス
2. 最新版をダウンロード
3. インストール時に **"Add Python to PATH"** にチェック ✅

### 2. ファイルのダウンロード

以下のファイルをダウンロード:
- `get_reviews_from_dental_new.py`
- `run_local.bat`
- `dental_new.csv` または `results/dental_new_hokkaido.csv`

### 3. 実行

1. `run_local.bat` をダブルクリック
2. APIトークンを入力
3. 処理範囲を指定（全件の場合は何も入力せずEnter）
4. 入力CSVを選択
5. 完了まで待つ

### コマンドラインから実行する場合

```cmd
# コマンドプロンプトを開く
cd C:\path\to\googlemap

# 実行
run_local.bat
```

---

## 🍎 Mac での実行

### 1. Pythonのインストール

```bash
# Homebrewを使う場合（推奨）
brew install python3

# または公式サイトからダウンロード
# https://www.python.org/downloads/
```

### 2. ファイルのダウンロード

以下のファイルをダウンロード:
- `get_reviews_from_dental_new.py`
- `run_local.sh`
- `dental_new.csv` または `results/dental_new_hokkaido.csv`

### 3. 実行

```bash
# ターミナルを開く
cd /path/to/googlemap

# 実行権限を付与
chmod +x run_local.sh

# 実行
./run_local.sh
```

対話形式で設定を入力します。

---

## 🐧 Linux での実行

### 1. Pythonのインストール

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip

# CentOS/RHEL
sudo yum install python3 python3-pip
```

### 2. ファイルのダウンロード

```bash
# GitHubからクローン
git clone https://github.com/mememori8888/googlemap.git
cd googlemap
```

### 3. 実行

```bash
# 実行権限を付与
chmod +x run_local.sh

# 実行
./run_local.sh
```

---

## 💡 高度な使い方

### 環境変数で直接実行

```bash
# Mac/Linux
export BRIGHTDATA_API_TOKEN='your-token-here'
export INPUT_CSV='dental_new.csv'
export OUTPUT_CSV='results/dental_new_reviews.csv'
export START_ROW=1
export END_ROW=100
export DAYS_BACK=10

python3 get_reviews_from_dental_new.py
```

```cmd
REM Windows
set BRIGHTDATA_API_TOKEN=your-token-here
set INPUT_CSV=dental_new.csv
set OUTPUT_CSV=results\dental_new_reviews.csv
set START_ROW=1
set END_ROW=100
set DAYS_BACK=10

python get_reviews_from_dental_new.py
```

### バックグラウンド実行（Mac/Linux）

```bash
# nohupで実行（ターミナルを閉じても継続）
nohup ./run_local.sh > logs/local_run.log 2>&1 &

# 進捗確認
tail -f logs/local_run.log

# プロセス確認
ps aux | grep get_reviews_from_dental_new.py
```

### 分割実行（大量データの場合）

```bash
# 500行ずつ処理
for i in {1..154}; do
  START=$((($i-1)*500+1))
  END=$(($i*500))
  echo "処理中: $START - $END"
  
  export START_ROW=$START
  export END_ROW=$END
  python3 get_reviews_from_dental_new.py
  
  sleep 60  # 1分待機
done
```

---

## ⚠️ トラブルシューティング

### Pythonが見つからない

```bash
# Pythonのパスを確認
which python3  # Mac/Linux
where python   # Windows

# バージョン確認
python3 --version
```

### requestsモジュールがない

```bash
# Mac/Linux
pip3 install requests

# Windows
pip install requests
```

### タイムアウトエラー

スクリプト内の `timeout=120` を `timeout=180` に変更:

```python
# get_reviews_from_dental_new.py の120行目付近
resp = requests.post(
    trigger_url,
    params=params,
    headers=self.headers,
    data=json.dumps(payload),
    timeout=180  # 120から180に変更
)
```

### メモリ不足

小さい範囲で実行:

```bash
# 100行ずつ処理
export START_ROW=1
export END_ROW=100
python3 get_reviews_from_dental_new.py
```

---

## 📊 実行時間の目安

| データ量 | 処理時間 | 取得レビュー数 |
|---------|---------|--------------|
| 100施設 | 約5-10分 | 約20-50件 |
| 500施設 | 約30-60分 | 約100-300件 |
| 3,000施設（北海道） | 約2-3時間 | 約500-1,000件 |
| 77,000施設（全国） | 約50-100時間 | 約10,000-30,000件 |

※ BrightData APIの応答速度により変動します

---

## 💰 コスト

- **BrightData Web Scraper API**: 使用量に応じた課金
- 100施設 = 約100クレジット
- 詳細は BrightData ダッシュボードで確認

---

## 📝 実行ログ

ログは自動的に保存されます:
- コンソール出力: リアルタイムで表示
- ファイル: `results/dental_new_reviews.csv` に追記保存

進捗確認:

```bash
# 行数確認
wc -l results/dental_new_reviews.csv

# 最新5件
tail -5 results/dental_new_reviews.csv
```

---

## 🔒 セキュリティ

- APIトークンは環境変数で管理
- `.gitignore` に `results/*.csv` を追加済み
- APIトークンをコードに直接書かない

---

## 📞 サポート

問題が発生した場合:
1. エラーメッセージを確認
2. Python/ライブラリのバージョンを確認
3. BrightData APIトークンが有効か確認
4. GitHubリポジトリのIssueに報告
