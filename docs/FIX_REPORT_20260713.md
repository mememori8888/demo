# 変更レポート — オーケストレーションのstartup_failure修正とフェイルセーフ強化（2026-07-13）

## 背景

ユーザーがBrightDataのAPIキーを自分のものに更新後、webapp（Issue発行）経由で `/run-reviews-relevance` を実行したところ、GitHub Actionsの「オーケストレーション」ワークフロー（[issue-ops-universal.yml](../.github/workflows/issue-ops-universal.yml)）が `startup_failure` で起動すら出来ない状態になっていた。原因調査・修正・実APIキーによる実地テストまでを実施した。

---

## 発見した問題と対応

### 1. `startup_failure`（ワークフローが起動しない）

- **原因**: `issue-ops-universal.yml` のトップレベル `permissions` が `contents: write` と `issues: write` のみで、呼び出し先の再利用可能ワークフロー（[reviews_local_interactive_sequential.yml](../.github/workflows/reviews_local_interactive_sequential.yml)、[reviews_recent_with_relevance.yml](../.github/workflows/reviews_recent_with_relevance.yml)）が要求する `actions: read` 権限を許可できず、GitHub Actionsが実行前に拒否していた。
  - 実際のエラー: `Error calling workflow '...reviews_local_interactive_sequential.yml@...'. The workflow is requesting 'actions: read', but is only allowed 'actions: none'.`
- **対応**: `issue-ops-universal.yml` のトップレベル `permissions` に `actions: read` を追加。

### 2. マトリックス肥大化によるジョブ失敗（フェイルセーフ設計の欠如）

- **原因**: `rows_per_batch` を小さく設定し `max_batches` を未指定（デフォルト値 `0` = 無制限）のままにすると、対象CSVの行数次第でバッチ数が数千〜万単位に膨れ上がり、GitHub Actionsの制約（matrix上限256件・ジョブ出力上限1MB）を超えて `Job outputs exceed 1,048,576 bytes` という分かりにくいエラーで失敗していた。
  - 実際のテストケース: `rows_per_batch=5`・`max_batches`未指定・CSV行数77,345行 → 選択バッチ数15,469件で失敗。
- **対応（claude.mdの「フェイルセーフ・フールプルーフ設計」要件に基づく）**:
  - `issue-ops-universal.yml` の `validate-request` ジョブに、CSV行数・`rows_per_batch`・`start_from_batch`・`max_batches` から実際に選択されるバッチ数を事前計算し、256件を超える場合はIssueに分かりやすい日本語エラーコメントを出して安全に停止する検証を追加。
  - [reviews_recent_with_relevance.yml](../.github/workflows/reviews_recent_with_relevance.yml) と [reviews_local_interactive_sequential.yml](../.github/workflows/reviews_local_interactive_sequential.yml) の `prepare` ジョブにも同様の256件上限チェックを追加し、二重の安全網とした。

### 3. SERP API呼び出し時のエラーメッセージが不透明

- **原因**: [scripts/enrich_review_relevance_ranks.py](../scripts/enrich_review_relevance_ranks.py) が SERP API のレスポンスをJSONパースする際、失敗時のメッセージが `Expecting value: line 1 column 1 (char 0)` のみで、実際のHTTPステータスやレスポンス本文が分からず原因究明が困難だった。
- **対応**: `fetch_relevance_reviews()` と `parse_response_body()` を修正し、JSONパース失敗時にHTTPステータスコード・`Content-Type`・レスポンス本文の先頭300文字を含めるようにした。これにより実際の原因（BrightDataゾーンからの `502 Bad Gateway`）を特定できた。

### 4. SERP APIゾーン（`serp_api2`）が無効化されていた

- **原因**: BrightDataアカウント側で `serp_api2` ゾーンが無効状態になっており、リクエストが `502 Bad Gateway` で拒否されていた（コードの問題ではなくアカウント設定の問題）。
- **対応**: ユーザーがBrightDataダッシュボードで `serp_api2` ゾーンを有効化。

---

## 変更ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `.github/workflows/issue-ops-universal.yml` | `permissions` に `actions: read` を追加。`validate-request` にバッチ数上限（256件）の事前検証を追加 |
| `.github/workflows/reviews_recent_with_relevance.yml` | `prepare` ジョブにバッチ数上限（256件）チェックを追加 |
| `.github/workflows/reviews_local_interactive_sequential.yml` | `prepare` ジョブにバッチ数上限（256件）チェックを追加 |
| `scripts/enrich_review_relevance_ranks.py` | SERP APIレスポンスのJSONパース失敗時に、HTTPステータス・Content-Type・本文冒頭を含めた診断メッセージを出力するよう変更 |

---

## 実施したテスト

1. Issue [#15](https://github.com/mememori8888/demo/issues/15) に `/承認` を投稿し、`オーケストレーション` ワークフローの再実行を実施。
2. 修正1適用後 → `startup_failure` は解消し、`parse-and-route` / `validate-request` / `prepare` まで正常進行することを確認。
3. 修正2適用後 → 本来失敗するはずの不正パラメータ（バッチ数15,469件）が `validate-request` の段階で安全に検知・停止されることを確認。
4. Issue本文を `max_batches: 1` に修正し、実際にBrightData APIキーで1バッチ（5件）のみの実地テストを実施。
   - Dataset APIによるレビュー取得は成功（3施設分の最新レビューを検出）。
   - SERP APIは `serp_api2` ゾーン無効化により `502 Bad Gateway` で失敗 → 診断メッセージ改善によりゾーン無効化が原因と特定。
5. ユーザーがBrightData側で `serp_api2` ゾーンを有効化後、再度 `/承認` を実行。
   - `run-dataset-batches` → `merge-and-enrich` → `report-completion` まで全ジョブが成功し、Issueが自動クローズされることを確認。
   - 出力: `results/dental_reviews.csv`、`results/dental_relevance_rank_summary.csv`（いずれも `mememori8888/googlemap` プライベートリポジトリに保存）。

---

## 今後の留意点

- BrightDataのゾーンはアカウント単位で作成されるため、APIキーを変更した場合は既存コードがデフォルトで参照するゾーン名（`serp_api2` 等）が新アカウントにも存在し、かつ有効化されているかを必ず確認すること。
- `max_batches` は未指定だと「無制限」として扱われるため、CSVが大きい場合は必ず明示的に指定するか、rows_per_batchを十分大きく設定すること（今回追加したフェイルセーフ検証により、上限超過時はワークフロー起動前にIssueへエラーが通知されるようになった）。
