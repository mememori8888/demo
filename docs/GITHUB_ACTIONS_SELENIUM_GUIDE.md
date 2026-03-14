# GitHub Actions で Selenium を使う完全ガイド

このドキュメントは、GitHub Actions 環境で Selenium/Chrome を安定して動作させるための決定版ガイドです。

## 🚨 絶対にやってはいけないこと

### ❌ `--single-process` オプションを使用しない

```python
# ❌ ダメな例
chrome_options.add_argument('--single-process')  # Chrome が即座にクラッシュ
```

**理由**: このオプションはすべてのプロセスを1つに統合するため、GitHub Actions のようなリソース制限環境では即座にクラッシュします。

---

## ✅ 推奨設定

### 1. 依存関係のインストール（最小構成）

```yaml
# .github/workflows/your-workflow.yml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install selenium
```

**重要**: 
- ✅ `selenium` のみで十分（Selenium 4.6+ は ChromeDriver を自動管理）
- ❌ `webdriver-manager` は不要

### 2. Chrome オプションの推奨設定

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def setup_driver():
    """安定した Chrome 設定"""
    chrome_options = Options()
    
    # 必須オプション
    chrome_options.add_argument('--headless')           # ヘッドレスモード
    chrome_options.add_argument('--no-sandbox')         # サンドボックス無効化
    chrome_options.add_argument('--disable-dev-shm-usage')  # /dev/shm の使用を無効化
    
    # 推奨オプション
    chrome_options.add_argument('--disable-gpu')        # GPU 無効化
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--window-size=1280,720')
    
    # ボット検知回避（オプション）
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # ページ読み込み戦略
    chrome_options.page_load_strategy = 'eager'  # DOMロード後すぐ処理開始
    
    # ドライバー作成
    driver = webdriver.Chrome(options=chrome_options)
    
    # タイムアウト設定
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(30)
    
    return driver
```

### 3. ワークフロー設定

```yaml
name: Selenium Test

on:
  workflow_dispatch:

jobs:
  selenium-job:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install selenium
      
      - name: Run Selenium script
        run: python your_script.py
```

---

## 📊 並列処理の推奨値

### Workers 数の目安

| データ件数 | 推奨 workers | 処理時間の目安 |
|----------|-------------|--------------|
| ~100件   | 1-2         | 10-20分      |
| ~500件   | 2-3         | 30-60分      |
| ~1000件  | 3-5         | 1-2時間      |
| 1000件+  | 5-7         | 3-6時間      |

**GitHub Actions のリソース制限**:
- CPU: 2コア
- RAM: 7GB
- タイムアウト: 6時間（360分）

### 並列処理の実装例

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_urls(urls, workers=3):
    """複数URLを並列処理"""
    def process_chunk(chunk):
        driver = setup_driver()
        results = []
        try:
            for url in chunk:
                # 処理
                driver.get(url)
                results.append(driver.current_url)
                time.sleep(2)  # レート制限対策
        finally:
            driver.quit()
        return results
    
    # チャンク分割
    chunk_size = len(urls) // workers
    chunks = [urls[i:i+chunk_size] for i in range(0, len(urls), chunk_size)]
    
    # 並列実行
    all_results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(process_chunk, chunk) for chunk in chunks]
        for future in as_completed(futures):
            all_results.extend(future.result())
    
    return all_results
```

---

## 🔧 トラブルシューティング

### 問題: "session not created: Chrome instance exited"

**原因**: Chrome の起動に失敗

**解決策**:
1. `--single-process` を削除
2. `--no-sandbox` と `--disable-dev-shm-usage` を確認
3. メモリ不足の場合は workers を減らす

### 問題: "invalid session id"

**原因**: Chrome がクラッシュした

**解決策**:
1. **50件ごとにブラウザを再起動**（メモリリーク対策）
   ```python
   for i, url in enumerate(urls):
       if i % 50 == 0:
           if driver:
               driver.quit()
           driver = setup_driver()
       # 処理
   ```

### 問題: 処理が遅い

**解決策**:
1. workers を増やす（2-5推奨）
2. `page_load_strategy = 'eager'` を使用
3. 不要な待機時間を削減

### 問題: "webdriver-manager がタイムアウト"

**解決策**:
- **削除する**（Selenium 4.6+ では不要）
- ワークフローから `pip install webdriver-manager` を削除

---

## 📝 デバッグのコツ

### ログレベルの設定

```python
import logging

# 開発時: DEBUG
logging.basicConfig(level=logging.DEBUG)

# 本番時: INFO
logging.basicConfig(level=logging.INFO)
```

### テスト用ワークフロー

小規模テストで動作確認してから本番実行：

```yaml
# test-selenium.yml
name: Test Selenium

on:
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: pip install selenium
      
      - name: Quick test
        run: |
          python - <<'EOF'
          from selenium import webdriver
          from selenium.webdriver.chrome.options import Options
          
          options = Options()
          options.add_argument('--headless')
          options.add_argument('--no-sandbox')
          options.add_argument('--disable-dev-shm-usage')
          
          driver = webdriver.Chrome(options=options)
          driver.get("https://www.google.com")
          print(f"✅ Success: {driver.current_url}")
          driver.quit()
          EOF
```

---

## 🎯 チェックリスト

実装前に確認：

- [ ] `--single-process` を使用していない
- [ ] `webdriver-manager` を削除した
- [ ] `--no-sandbox` と `--disable-dev-shm-usage` を設定
- [ ] タイムアウトを設定（60秒推奨）
- [ ] workers 数を適切に設定（2-5推奨）
- [ ] テストワークフローで動作確認済み
- [ ] ログレベルを設定（DEBUG → INFO）
- [ ] 50件ごとのブラウザ再起動を実装（長時間処理の場合）

---

## 📚 参考リンク

- [Selenium Documentation](https://www.selenium.dev/documentation/)
- [GitHub Actions - ubuntu-latest環境](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md)
- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)

---

## 🆘 よくある質問

**Q: Selenium 4.x で webdriver-manager は必要？**  
A: **不要です**。Selenium 4.6+ は Selenium Manager が自動で ChromeDriver を管理します。

**Q: GitHub Actions で Chrome は使える？**  
A: **はい**。ubuntu-latest には Chrome がプリインストールされています。

**Q: workers を増やせば速くなる？**  
A: **ある程度まで**。7以上にしても CPU/メモリ制限で効果は薄いです。

**Q: ローカルでは動くが GitHub Actions で失敗する理由は？**  
A: リソース制限や `--single-process` などの不適切なオプションが原因です。

---

**最終更新**: 2026-02-06  
**バージョン**: 1.0  
**テスト環境**: ubuntu-latest, Python 3.12, Selenium 4.40
