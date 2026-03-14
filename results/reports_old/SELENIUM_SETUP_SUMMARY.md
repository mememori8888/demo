# Selenium セットアップ完了 ✅

## 変更内容

GitHub ActionsでSeleniumが使用できるように以下の設定を行いました。

### 1. 既存ワークフローの修正

**ファイル**: `.github/workflows/check-business-status.yml`

- ChromeとChromeDriverのインストール処理を改善
- `browser-actions/setup-chrome@v1`を使用した自動セットアップに変更
- ステップの順序を最適化

### 2. 新規ファイルの追加

#### ワークフローファイル

1. **`.github/workflows/selenium-template.yml`**
   - 汎用的なSeleniumテスト用テンプレート
   - 任意のPythonスクリプトを実行可能
   - 手動実行（workflow_dispatch）対応

2. **`.github/workflows/test-selenium.yml`**
   - Selenium動作確認用テストワークフロー
   - 自動テスト実行とスクリーンショット保存

#### Pythonスクリプト

3. **`test_selenium.py`**
   - Selenium動作確認用のテストスクリプト
   - Google、Google Mapsへのアクセステスト
   - スクリーンショット機能のテスト

#### ドキュメント

4. **`docs/SELENIUM_SETUP.md`**
   - Seleniumセットアップの詳細ガイド
   - トラブルシューティング情報
   - ベストプラクティス
   - 新規ワークフロー作成方法

5. **`README.md`** (更新)
   - Seleniumドキュメントへのリンクを追加

## 使い方

### テスト実行

Seleniumが正しく動作するか確認:

```bash
# ローカルでのテスト
python test_selenium.py

# GitHub Actionsでのテスト
# 1. GitHubリポジトリのActionsタブに移動
# 2. "Test Selenium Setup"を選択
# 3. "Run workflow"をクリック
```

### 既存のワークフローを使用

営業ステータス確認（Selenium使用）:

1. GitHubリポジトリの **Actions** タブに移動
2. **Check Business Status** を選択
3. **Run workflow** をクリック
4. パラメータを入力して実行

### 新しいSeleniumスクリプトの作成

詳細は `docs/SELENIUM_SETUP.md` を参照してください。

基本的な手順:

1. Pythonスクリプトを作成（headlessモード必須）
2. `.github/workflows/`にワークフローファイルを作成
3. `browser-actions/setup-chrome@v1`を使用してChromeをセットアップ

## 重要なポイント

### 必須のChromeオプション

GitHub Actions（Ubuntu）で実行する場合、以下のオプションは必須です:

```python
chrome_options = Options()
chrome_options.add_argument('--headless')  # 必須
chrome_options.add_argument('--no-sandbox')  # 必須
chrome_options.add_argument('--disable-dev-shm-usage')  # 必須
```

### ワークフローでの必須ステップ

```yaml
- name: Set up Chrome and ChromeDriver
  uses: browser-actions/setup-chrome@v1
  with:
    chrome-version: stable
```

## トラブルシューティング

問題が発生した場合:

1. `docs/SELENIUM_SETUP.md`のトラブルシューティングセクションを確認
2. GitHub ActionsのログでChromeバージョンを確認
3. スクリーンショットをアップロードしてデバッグ
4. ローカル環境（Dev Container）でテスト

## 次のステップ

- [ ] `test_selenium.py`を実行してセットアップを確認
- [ ] GitHub Actionsで "Test Selenium Setup" ワークフローを実行
- [ ] 既存の`check_business_status.py`が正常に動作することを確認
- [ ] 必要に応じて新しいSeleniumスクリプトを作成

## 参考資料

- [Selenium公式ドキュメント](https://www.selenium.dev/documentation/)
- [browser-actions/setup-chrome](https://github.com/browser-actions/setup-chrome)
- [GitHub Actions公式ドキュメント](https://docs.github.com/en/actions)

---

セットアップは完了しました！問題があれば `docs/SELENIUM_SETUP.md` を参照するか、Issue を作成してください。
