# セキュリティ推奨事項

## 現在の Issue Ops 実装のセキュリティ状態

### ✅ 実装済みの対策

1. **承認フロー**
   - Issue作成後、管理者の `/approve` コメントが必須
   - 承認者は `OWNER` または `mememori8888` のみ
   - 未承認のIssueは自動実行されない

2. **Secrets管理**
   - `BRIGHTDATA_API_TOKEN` と `GEMINI_API_KEY` はGitHub Secretsで保護
   - ログに出力されない設定

3. **コマンド制限**
   - 定義済みコマンドのみ実行可能 (`/run-*`)
   - 任意のシェルコマンドは実行不可

---

## ⚠️ リスクと対策

### 1. パブリックリポジトリの場合

#### リスク
- 誰でもIssueを作成できる → スパム・DoS攻撃の可能性
- GitHub Pages (`docs/webapp/`) が公開される

#### 対策オプション

**A. リポジトリをプライベート化**
```bash
# GitHubリポジトリ設定 → Danger Zone → Change visibility → Private
```
- 最も安全だが、GitHub Pagesも非公開になる

**B. Issue作成を制限**
```yaml
# .github/workflows/issue-ops-universal.yml
jobs:
  parse-and-route:
    if: |
      github.event.issue.author_association == 'OWNER' ||
      github.event.issue.author_association == 'COLLABORATOR' ||
      github.event.issue.author_association == 'MEMBER'
```

**C. Rate Limitingを実装**
- 同一ユーザーからの連続Issue作成を制限
- GitHub Actions の `concurrency` 設定を活用

---

### 2. パラメータインジェクション

#### リスク
```json
{
  "custom_settings": {
    "facility_file": "../../../etc/passwd",
    "query": "'; DROP TABLE users; --"
  }
}
```

#### 対策: Pythonスクリプトでバリデーション

**apply_custom_settings.py に追加:**
```python
import os
import re

def validate_file_path(path: str) -> bool:
    """ファイルパスのバリデーション"""
    # パストラバーサルをブロック
    if '..' in path or path.startswith('/'):
        raise ValueError(f"Invalid path: {path}")
    
    # 許可されたディレクトリのみ
    allowed_dirs = ['settings/', 'results/']
    if not any(path.startswith(d) for d in allowed_dirs):
        raise ValueError(f"Path must start with {allowed_dirs}")
    
    # CSVファイルのみ
    if not path.endswith('.csv'):
        raise ValueError(f"Only CSV files allowed: {path}")
    
    return True

def validate_query(query: str) -> bool:
    """検索クエリのバリデーション"""
    # 最大長制限
    if len(query) > 100:
        raise ValueError("Query too long")
    
    # 危険な文字を除外
    dangerous_chars = [';', '--', '/*', '*/', 'DROP', 'DELETE', 'INSERT']
    for char in dangerous_chars:
        if char.lower() in query.lower():
            raise ValueError(f"Invalid character in query: {char}")
    
    return True

# apply_custom_settings() 関数内で使用
if 'facility_file' in custom_settings:
    validate_file_path(custom_settings['facility_file'])
if 'query' in custom_settings:
    validate_query(custom_settings['query'])
```

---

### 3. API Rate Limit (GitHub API)

#### 問題
- `docs/webapp/app.js` でGitHub APIを呼び出す
- 匿名アクセス: **60リクエスト/時**
- 認証済み: **5000リクエスト/時**

#### 対策オプション

**A. Personal Access Token (PAT) を使用**
```javascript
// app.js
const response = await fetch(url, {
    headers: {
        'Authorization': 'token YOUR_GITHUB_PAT'
    }
});
```
⚠️ **注意**: PATをHTMLに埋め込むと公開されるため危険

**B. GitHub Actionsでファイルリスト生成**
```yaml
# .github/workflows/generate-file-list.yml
name: Generate File List

on:
  push:
    paths:
      - 'settings/**'
      - 'results/**'

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Generate file list JSON
        run: |
          echo '{"settings":' > docs/webapp/files.json
          ls settings/*.csv | jq -R -s 'split("\n")[:-1]' >> docs/webapp/files.json
          echo ',"results":' >> docs/webapp/files.json
          ls results/*.csv | jq -R -s 'split("\n")[:-1]' >> docs/webapp/files.json
          echo '}' >> docs/webapp/files.json
      
      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add docs/webapp/files.json
          git commit -m "chore: Update file list" || exit 0
          git push
```

**app.js で静的JSONを読み込み:**
```javascript
async function loadFileOptions() {
    const response = await fetch('./files.json');
    const files = await response.json();
    // ...
}
```

---

### 4. Workflow実行の監視

#### 推奨: 通知設定
```yaml
# issue-ops-universal.yml に追加
- name: Notify on approval
  uses: actions/github-script@v7
  with:
    script: |
      await github.rest.issues.createComment({
        owner: context.repo.owner,
        repo: context.repo.repo,
        issue_number: context.issue.number,
        body: '🚀 Workflow started by @${{ github.actor }}\n\n⏰ Started at: ' + new Date().toISOString()
      });
```

---

## 🎯 優先順位別推奨事項

### 優先度: 高 🔴

1. **パラメータバリデーションの実装**
   - `apply_custom_settings.py` にバリデーション関数を追加
   - パストラバーサル、SQLインジェクション対策

2. **Issueテンプレートの作成**
   ```yaml
   # .github/ISSUE_TEMPLATE/job-request.yml
   name: Job Request
   description: Request a BrightData job execution
   title: "[JOB] "
   labels: ["job-request"]
   assignees:
     - mememori8888
   body:
     - type: dropdown
       id: workflow
       attributes:
         label: Workflow Type
         options:
           - reviews
           - facility
           - facility_heatmap
           - count
           - dental_analysis
       validations:
         required: true
   ```

### 優先度: 中 🟡

3. **GitHub Actionsでファイルリスト生成**
   - API Rate Limitを回避
   - 静的JSONファイルを自動生成

4. **Workflow実行ログの監視**
   - Slackやメールで通知
   - 異常な実行パターンを検知

### 優先度: 低 🟢

5. **リポジトリのプライベート化**
   - 完全に制御したい場合
   - GitHub Pagesも非公開になる

6. **IP制限 (GitHub Enterprise)**
   - 特定IPからのみアクセス許可
   - GitHub Free/Proでは不可

---

## 📊 現在のリスク評価

| 項目 | リスクレベル | 影響度 | 対策状況 |
|------|--------------|--------|----------|
| 未承認実行 | 🟢 低 | 高 | ✅ 承認フロー実装済み |
| Secrets漏洩 | 🟢 低 | 高 | ✅ GitHub Secrets使用 |
| パラメータインジェクション | 🟡 中 | 中 | ⚠️ 未対策 |
| Issue スパム | 🟡 中 | 低 | ⚠️ 未対策 |
| API Rate Limit | 🟢 低 | 低 | ⚠️ 未対策 |
| DoS攻撃 | 🟢 低 | 中 | ✅ 承認フローで緩和 |

---

## ✅ 結論

**現在のIssue Ops実装は基本的に安全ですが、以下の対策を推奨:**

1. **必須**: パラメータバリデーション実装
2. **推奨**: ファイルリスト生成の自動化 (API Rate Limit対策)
3. **検討**: リポジトリの可視性設定の見直し

承認フローにより、管理者が内容を確認してから実行するため、**悪意のあるパラメータは承認時に検知可能**です。
