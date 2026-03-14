# Issue オーケストレーション機能レポート

## 1. 概要
このレポートは、Issue を起点にデータ処理ジョブを承認実行する仕組み（issue-ops-universal）を整理したものです。

対象ワークフロー:
- .github/workflows/issue-ops-universal.yml

この仕組みは、次の運用フローを実現します。
- webapp → issue 作成
- issue 本文のコマンド解析
- 概算コスト提示
- 管理者承認
- GitHub Actions 実行
- データ出力と結果通知

## 2. 起動条件と実行方式
### 起動イベント
- issues: opened
- issue_comment: created

### 実行方式の特徴
- Actions 画面の手動実行（workflow_dispatch）ではない
- Issue 本文とコメントを API 的に扱うイベント駆動方式
- ワークフロー名が「実行不可」でも、Issue イベントでは実行される

## 3. 対応コマンド
Issue 本文で受け付けるコマンド:
- /run-reviews
- /run-facility
- /run-facility-heatmap
- /run-generate-heatmap
- /run-extract-fid

承認コメント:
- /承認

## 4. 実行シーケンス
1. Issue 作成時
- 本文から実行対象を判定
- 実行パラメータ（json ブロック）を抽出
- should_run=preview で見積もりモードに入る

2. プレビューコメント
- 予想リクエスト数
- 予想コスト
- 内訳
- 管理者へ承認依頼

3. 承認処理
- issue_comment で /承認 を検知
- 実行者が OWNER または指定ユーザーなら should_run=true
- 未権限は should_run=false で停止

4. ジョブ分岐実行
- reviews: 再利用ワークフロー brightdata_reviews.yml 呼び出し
- facility: Python 実行で施設データ更新
- facility_heatmap: Python 実行でヒートマップ向け施設取得
- generate_heatmap: ヒートマップ生成処理
- extract_fid: 再利用ワークフロー extract-fid.yml 呼び出し

5. 完了報告
- 成功時: 出力ファイルリンクをコメント
- 失敗時: Actions ログ案内コメント
- 成功時は Issue をクローズ

## 5. 出力とコミット
主な出力先:
- results 配下 csv
- settings/settings.json
- docs/webapp/files.json（generate_heatmap 系）

コミット方針:
- 差分がある場合のみコミット
- origin main に push

## 6. 現状の既知課題
リポジトリ確認時点で、次の参照スクリプトが未配置です。
- apply_custom_settings.py
- search_optimizer.py

影響:
- run-facility / run-facility-heatmap の設定反映ステップが失敗し得る
- run-generate-heatmap の生成ステップが失敗し得る

## 7. フェイルセーフ / フールプルーフ観点の評価
現状で良い点:
- 承認フローがあり誤実行を抑制
- 概算コストの事前提示
- 権限チェックで実行制御

不足している点:
- 依存スクリプト存在チェックが実行前にない
- json パラメータ形式不正時の明確なエラーメッセージが弱い
- ジョブごとの入力必須項目バリデーションが十分ではない
- 失敗時リカバリ手順の定型コメントがない

## 8. 改善提案（優先順）
1. 事前バリデーションジョブ追加
- 必須ファイル存在
- 必須パラメータ
- json 構文
- 不正時は実行せず Issue に理由を返信

2. コマンド契約の明文化
- 各 /run-xxx の必須キー・任意キー・デフォルト値を docs に明記

3. 実行可否の明示
- should_run=false 時に必ず理由コメント

4. 失敗時の案内強化
- 失敗ジョブ名
- 想定原因
- 次に確認すべきファイル

5. 競合対策
- 同一 Issue の重複承認を防止する簡易ロック導入

## 9. 運用ガイド（最小）
1. webapp から Issue を作成（本文に /run-xxx と json）
2. Bot の見積もりコメントを確認
3. 管理者が /承認 コメント
4. 完了コメントの出力リンクを確認
5. 必要なら Issue を再オープンして再実行

## 10. まとめ
issue-ops-universal は、Issue ベースで実行要求を受け、承認後に処理を振り分けるオーケストレーターです。
運用設計としては実用的ですが、依存ファイルの事前検証と入力バリデーションを追加すると、フェイルセーフ性とフールプルーフ性が大きく向上します。
