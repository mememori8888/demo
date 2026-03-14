# 🔐 API キー設定ガイド

## GitHub Secrets を使用する方法（推奨）

### 1. GitHub リポジトリでの設定

1. **リポジトリページにアクセス**
   - GitHub でリポジトリページを開く

2. **Settings タブをクリック**
   - リポジトリの上部メニューから Settings を選択

3. **Secrets and variables > Actions を選択**
   - 左サイドバーから「Secrets and variables」→「Actions」

4. **New repository secret をクリック**

5. **Secret を追加**
   - Name: `GOOGLE_API_KEY`
   - Secret: `あなたのGoogle AI Studio APIキー`
   - Add secret をクリック

### 2. GitHub Actions での実行

```yaml
# .github/workflows/dental-analysis.yml が自動生成されています
# Actions タブから「Dental Clinic Analysis」ワークフローを実行
```

**実行方法:**
1. GitHub リポジトリの「Actions」タブ
2. 「Dental Clinic Analysis」ワークフロー選択
3. 「Run workflow」ボタンクリック
4. パラメータ設定（件数制限、並列数など）
5. 実行開始

## ローカル環境での設定方法

### 方法1: 環境変数として設定

```bash
# Linux/Mac
export GOOGLE_API_KEY="your_api_key_here"
python dental_clinic_analyzer.py --limit 10

# Windows (PowerShell)
$env:GOOGLE_API_KEY="your_api_key_here"
python dental_clinic_analyzer.py --limit 10

# Windows (コマンドプロンプト)
set GOOGLE_API_KEY=your_api_key_here
python dental_clinic_analyzer.py --limit 10
```

### 方法2: .env ファイル使用

1. **`.env` ファイル作成**
```bash
# .env ファイルに記述
GOOGLE_API_KEY=your_api_key_here
GEMINI_API_KEY=your_api_key_here
```

2. **python-dotenv インストール**
```bash
pip install python-dotenv
```

3. **プログラム実行前に読み込み**
```bash
python -c "from dotenv import load_dotenv; load_dotenv()" && python dental_clinic_analyzer.py
```

## Google AI Studio API キーの取得方法

1. **Google AI Studio にアクセス**
   - https://aistudio.google.com/

2. **「Get API key」をクリック**

3. **新しいプロジェクトまたは既存プロジェクトを選択**

4. **API キーをコピー**
   - 形式: `AIzaSy...` で始まる文字列

## 対応する環境変数名

プログラムは以下の環境変数を順番に確認します：

1. `GOOGLE_API_KEY` (推奨)
2. `GEMINI_API_KEY`
3. `GOOGLE_AI_API_KEY`  
4. `GITHUB_SECRET_GOOGLE_API_KEY`

## セキュリティ注意事項

⚠️ **API キーは絶対に以下に含めないでください:**
- Git コミット
- 公開リポジトリ
- ログファイル
- スクリーンショット

✅ **推奨事項:**
- GitHub Secrets を使用
- ローカルでは環境変数設定
- .env ファイルは .gitignore に追加

## トラブルシューティング

### エラー: "Google API キーが見つかりません"

**原因:** 環境変数が設定されていない

**解決方法:**
1. 上記のいずれかの方法でAPIキーを設定
2. 環境変数が正しく設定されているか確認
   ```bash
   echo $GOOGLE_API_KEY
   ```

### エラー: "API key not valid"

**原因:** 無効なAPIキー

**解決方法:**
1. Google AI Studio で新しいAPIキーを生成
2. APIキーのコピーミスがないか確認
3. APIキーの使用制限を確認

## 実行例

```bash
# GitHub Actions で実行（推奨）
# Actions タブ > Dental Clinic Analysis > Run workflow

# ローカル実行
export GOOGLE_API_KEY="AIzaSy..."
python dental_clinic_analyzer.py --limit 5 --concurrent 2
```