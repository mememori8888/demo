# 自動実行モード（承認ステップなし）の実装ガイド

はい、管理者の承認ステップをスキップし、**Issueが作成された瞬間に自動でタスクを実行させる**ことは可能です。

承認フローは「フェイルセーフ（安全装置）」の一つですが、高速化やシンプルさを優先する小規模な運用では省略されることもあります。

承認ステップをなくし、Issue作成と同時に実行させるための具体的な設定と、その際に注意すべき**「フールプルーフ（誤操作防止）」**のための対策を解説します。

---

## 1. GitHub Actions の設定変更

Issueが作成されたら、次のステップに移らずすぐに本番のタスクを実行するよう、ActionsのYAMLファイルを調整します。

### 変更点：トリガーと実行内容の直接化

承認フローでは「Issueコメント」をトリガーにしていましたが、それをやめ、「Issue作成」をトリガーに、直接デプロイジョブを実行します。

**（変更後の Actions YAML イメージ）**

```yaml
name: 自動デプロイ
on:
  issues:
    # Issueが作成されたとき (opened) と編集されたとき (edited) に起動
    types: [opened, edited]

jobs:
  auto-deploy:
    runs-on: ubuntu-latest
    # 【重要】実行者を制限する
    # 特定のユーザー（例: 許可された開発者 'authorized-user'）またはBotからのIssueのみ実行する
    if: contains(github.event.issue.title, 'Deploy') && (github.event.sender.login == 'authorized-user' || github.event.sender.login == 'your-bot-name')
    
    steps:
      # 1. Issue本文からパラメータを抽出するステップ（前回同様）
      - name: Parse Issue Body and Extract Parameters
        # ... パラメータ抽出の処理 ...
        
      # 2. 抽出したパラメータを使って本番デプロイを実行するステップ
      - name: Run Production Deployment
        run: |
          echo "Starting deploy to ${{ steps.parse.outputs.environment }}..."
          # ここにデプロイコマンドを記述
          # ...
          
      # 3. 完了通知をIssueにコメントするステップ
      - name: Notify Success
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '✅ 自動デプロイが完了しました。環境: ${{ steps.parse.outputs.environment }}'
            })
```

## 2. フールプルーフ（誤操作防止）の強化

承認ステップがない場合、誤操作をそのまま防ぐためのセキュリティ・防御策が非常に重要になります。

### A. Issue作成者による実行制限（最重要）

**すべてのユーザーのIssue実行を許可してはいけません。** `if` 条件を使い、Actionsの実行者を制限します。

| 設定項目 | 目的 |
|:---|:---|
| **`if: github.event.sender.login == '許可されたユーザーID'`** | Issueを作成したユーザーが、デプロイ権限を持つ特定の人物であることを確認します。 |
| **`if: github.event.issue.title == 'Deploy Request'`** | タイトルが意図した操作であるかを確認します。 |

### B. GitHub Environments の利用

GitHubのセキュリティ機能である **Environments（環境）** を使えば、Actions側でより強力な制御が可能です。

1. GitHubのリポジトリ設定で、`production` という名前のEnvironmentを作成します。
2. このEnvironmentの設定で、「**Required reviewers（承認者）**」を有効にします。

この設定をしておけば、Actionsのジョブ（Job）がこのEnvironmentを参照する場合、**Actions側で自動実行を指示しても、必ず指定された承認者が承認しない限り、処理は保留されます。**

* **メリット:** Webアプリ側は承認ステップを意識せず実行を投げられ、管理者が承認を忘れたとしても、実行自体はGitHubが担保してくれるためフェイルセーフ性が保たれます。

### C. Webアプリ側でのバリデーションの強化

承認がない分、Issueを作成する**「Webアプリのフォーム側」**で入力値チェックを徹底的に行います。

* **必須入力チェック:** 必要なパラメータ（環境名、バージョン名など）が空でないことを確認。
* **値の制限:** プルダウンメニューやラジオボタンを使い、ユーザーに自由な文字列を入力させないようにする（例: 環境は "staging" または "production" のみ）。
* **最終確認:** 実行前に「本当にこのバージョンを本番にデプロイしますか？」という最終確認ポップアップを表示させる。

これらの対策を組み合わせることで、承認ステップがなくても、安全に自動実行できるシステムが構築できます。
