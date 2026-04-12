# GitHub Actions ワークフロー エラーハンドリング改善ガイド

## 📋 実施した改善内容

### 1️⃣ ワークフロー側 (.github/workflows/dental_new_reviews_sequential.yml)

#### A. 詳細な環境検証ステップ (Validate Environment)

**改善点:**
- ❌ **APIトークン有効性テスト** - 実際にBrightData APIに接続してトークンの有効性を確認
  - HTTP 401 → 認証エラー
  - HTTP 403 → 権限エラー
  - ネットワークエラー → 詳細な確認手順を提示

- ✅ **入力ファイル検証** - CSVファイルの存在確認、行数、ファイルサイズ表示
- ✅ **環境情報の完全出力** - Python版、ディレクトリ構成も表示

**実行時の出力例:**
```
🔍 環境検証中...
✅ APIトークン: 検証成功 (HTTP 200)
✅ 入力CSV: results/dental_new.csv
✅ 総行数: 1000行（ヘッダー含む）
✅ ファイルサイズ: 2.5M
```

#### B. バッチ実行時のエラーキャプチャ強化

**改善点:**
- 各Pythonスクリプト実行のエラー出力をファイルに記録
- エラー原因を自動検出して分類表示:
  - 🔴 **認証エラー** (401/403)
  - 🟡 **ネットワークエラー** (接続失敗、タイムアウト)
  - 🟡 **APIエラー** (JSON形式エラーなど)

**実行時の出力例:**
```
❌ バッチ 1 でエラー発生
📋 エラーが記録されました: results/errors/batch_1_attempt_1.log
📝 エラー内容（最新50行）:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HTTP Error 401: Unauthorized
  Response: {"error": "Invalid API token"}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 認証エラー検出：
  → APIトークンが無効または期限切れの可能性があります
  → GitHub Secrets の BRIGHTDATA_API_TOKEN を確認してください
```

#### C. 包括的なエラー診断レポート (Generate Error Report)

**新ステップで以下を実施:**

1. **エラーレベル判定**
   - 重大エラー（認証、ネットワーク）を自動検出
   - 各エラータイプの詳細な原因分析

2. **エラータイプ別の解決策表示**

| エラー | 詳細 | 解決策 |
|--------|------|--------|
| 認証エラー(401/403) | APIトークンが無効 | GitHub Secrets確認、トークン再コピー |
| ネットワークエラー | API接続失敗 | ネットワーク確認、ファイアウォール確認 |
| タイムアウト | 処理時間超過 | BATCH_SIZE削減、MAX_WAIT_MINUTES増加 |

3. **ログファイル集約**
   - バッチログから失敗パターンを自動抽出
   - 最初の失敗バッチの詳細を表示

#### D. 失敗時のサマリー表示 (Publish Error Summary)

**GitHub Actions Summary に自動表示:**
```markdown
## ❌ 処理でエラーが発生しました

### エラー内容の確認方法
1. **ワークフロー実行ログ**: 上のステップ出力を確認
2. **詳細ログファイル**: 下の Artifacts からダウンロード
3. **エラー診断レポート**: `results/errors/ERROR_REPORT.md`

### よくある解決策
| エラー | 対策 |
|--------|------|
| 401/403 Unauthorized | GitHub Secrets の BRIGHTDATA_API_TOKEN を確認 |
```

---

### 2️⃣ Pythonスクリプト側 (get_reviews_from_dental_new.py)

#### A. APIトークン検証関数 (validate_api_token)

**実装内容:**
```python
def validate_api_token():
    """APIトークンを検証する"""
    # 1. 環境変数の存在確認
    # 2. トークン形式の基本チェック
    # 3. BrightData API への実際の接続テスト
    # 4. ステータスコード別の詳細エラーメッセージ
```

**出力例:**
```
🔍 APIトークン検証中...
🧪 BrightData API への接続テスト中...
  HTTP Status: 401

❌ エラー: APIトークンが無効です（401 Unauthorized）
確認事項:
  - トークンが正しくコピーされているか
  - トークンの有効期限を確認してください
  - 別のアカウントのトークンでないか確認
```

#### B. 実行環境検証関数 (validate_environment)

**実装内容:**
```python
def validate_environment():
    """実行環境全体を検証する"""
    # 入力ファイルの確認
    # 出力ディレクトリの用意
    # 設定値の表示
```

#### C. 詳細なエラーハンドリング

**改善内容:**

1. **trigger_snapshot() メソッド内**
   - HTTP ステータスコード別のエラーメッセージ
   - 401/403: 認証エラー
   - 429: レート制限
   - 5xx: サーバーエラー

2. **例外処理の強化**
   ```python
   except requests.exceptions.HTTPError as e:
       logging.error(f"HTTP Error {e.response.status_code}: {str(e)}")
       logging.error(f"Response: {e.response.text[:500]}")
   
   except requests.exceptions.Timeout as e:
       logging.error(f"Request timeout: {e}")
   
   except requests.exceptions.ConnectionError as e:
       logging.error(f"Connection error: {e}")
   ```

3. **ロギング出力の強化**
   - すべてのAPI呼び出しをログに記録
   - レスポンス内容の一部をログに出力
   - スタックトレースの完全出力

#### D. メイン処理でのエラー表示

**改善内容:**
```python
if __name__ == '__main__':
    try:
        setup_logging()
        validate_environment()
        validate_api_token()
        main()
    except FileNotFoundError as e:
        logging.error(f'ファイルエラー: {e}')
        sys.exit(2)
    except ValueError as e:
        logging.error(f'設定エラー: {e}')
        sys.exit(3)
    except Exception as e:
        logging.error(f'予期しないエラー: {e}')
        logging.error(f'エラー型: {type(e).__name__}')
        # 詳細なスタックトレースをログに出力
        sys.exit(1)
```

---

## 🔍 エラー検出フロー

### ワークフロー実行時の流れ

```
1. Validate Environment ステップ
   ↓
   - APIトークンの有効性テスト
   - 入力ファイルの確認
   - 環境情報の表示
   ↓
   [失敗 → 即座に終了、原因を表示]

2. Python スクリプト実行
   ↓
   - setup_logging()
   - validate_environment()
   - validate_api_token()
   - main()
   ↓
   [各ステップでエラーが発生 → ログに出力]

3. Generate Error Report ステップ
   ↓
   - ログファイルを解析
   - エラーパターンを分類
   - 解決策を表示
   ↓
   [GitHub Actions Summary に表示]

4. Artifacts にログをアップロード
   ↓
   [ユーザーが詳細ログをダウンロード可能]
```

---

## 📊 エラーログの確認方法

### 1. **GitHub Actions 画面での確認**

1. リポジトリ → Actions タブ
2. 失敗したワークフロー実行を選択
3. 各ステップを展開してログを確認

### 2. **Artifacts からのダウンロード**

1. ワークフロー実行ページ下部の "Artifacts" セクション
2. 以下のファイルが利用可能:
   - `dental-reviews-logs-*` (メインログ、バッチログ)
   - `dental-reviews-logs-*` (エラーログ)

### 3. **ローカルでのログ確認**

```bash
# ログの確認
tail -f results/logs/dental_reviews.log

# エラーログの確認
ls -la results/errors/

# 特定パターンのエラーを抽出
grep "ERROR\|❌" results/logs/dental_reviews.log | head -20
```

---

## 🔧 主なエラーと対処法

### エラー1: 401 Unauthorized

**症状:**
```
HTTP Error 401: Unauthorized
❌ エラー: APIトークンが無効です（401 Unauthorized）
```

**確認項目:**
1. GitHub リポジトリの [Settings] → [Secrets and variables] → [Actions]
2. BRIGHTDATA_API_TOKEN が設定されているか確認
3. トークン値に余分なスペースや文字がないか確認
4. BrightData Web コンソールでトークンを確認

**解決策:**
```bash
# 新しいトークンをコピーして再設定
# Settings → Secrets and variables → Actions → BRIGHTDATA_API_TOKEN の編集
```

### エラー2: Connection timeout

**症状:**
```
Connection error: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
❌ エラー: BrightData API への接続に失敗しました
```

**確認項目:**
1. ネットワーク接続確認
2. ファイアウォール設定
3. BrightData API ステータス

**解決策:**
```bash
# ワークフロー入力で以下を調整
- BATCH_SIZE を 50 → 25 に削減
- MAX_WAIT_MINUTES を 90 → 120 に増加
```

### エラー3: Request timeout (スナップショット待機)

**症状:**
```
❌ Timeout after 90 minutes
  → API レスポンス待機がタイムアウしました
```

**解決策:**
- BATCH_SIZE をさらに削減（10～20程度に）
- 複数回に分けて処理を実行
- ワークフロー timeout-minutes を増やす

---

## ✅ チェックリスト

ワークフロー実行前に確認:

- [ ] GitHub Secrets に BRIGHTDATA_API_TOKEN が設定されている
- [ ] トークンに余分なスペースがない
- [ ] 入力 CSV ファイルが存在する
- [ ] ネットワーク接続が正常
- [ ] BrightData API が稼働中 (ステータスページ確認)

エラー発生時の対応:

- [ ] ワークフロー実行ログを確認
- [ ] Artifacts からログファイルをダウンロード
- [ ] ログからエラーパターンを特定
- [ ] 該当する解決策を実行
- [ ] ワークフロー入力パラメータを調整
- [ ] 再度実行

---

## 📝 追加情報

### ログ出力形式

```
YYYY-MM-DD HH:MM:SS INFO メッセージ
YYYY-MM-DD HH:MM:SS WARNING 警告
YYYY-MM-DD HH:MM:SS ERROR エラー
```

### ログファイル場所

```
results/
├── logs/
│   ├── dental_reviews.log    (メインログ)
│   ├── batch_1.log            (バッチ1のログ)
│   ├── batch_2.log
│   └── ...
└── errors/
    ├── batch_1_attempt_1.log (バッチ1の試行1)
    ├── batch_1_attempt_2.log (バッチ1の試行2)
    └── ERROR_REPORT.md       (エラー診断レポート)
```

---

## 🚀 今後の改善予定

1. **メール通知機能** - エラー時にメール通知を追加
2. **Slack 連携** - Slack チャネルにエラー通知を送信
3. **自動リトライ** - 特定のエラーについて自動でリトライ
4. **メトリクス収集** - 処理時間、成功率などをグラフ化

---

## 中止方法

ワークフロー実行中に中止する必要がある場合:

1. GitHub Actions ページの実行中ワークフローを選択
2. "Cancel workflow run" ボタンをクリック
3. 処理済みデータは results/ ディレクトリに保存されます

---

**最終更新**: 2025-04-12
**対応ファイル**: 
- `.github/workflows/dental_new_reviews_sequential.yml`
- `get_reviews_from_dental_new.py`
