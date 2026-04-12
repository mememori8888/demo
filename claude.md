必ずフェイルセールでフールプルーフな設計にしてください。

pythonプログラムを作成する際に、デザインパターンは適したものを適用してください。

ワークフローは
webapp→issue→github actions起動→データ出力


***issue0-ops-universal.ymlの機能を変更する。***

以下のプログラムが動くようにする。
/workspaces/demo/facility_BrightData_20.py　**serp apiのやつ
/workspaces/demo/reviews_BrightData_50.py　　**serp apiのやつ
/workspaces/demo/run_reviews_local_interactive.py　**新仕様のweb scraper api
/workspaces/demo/faiility_brightdata_new_version.py　**新仕様のweb scraper api 

新規に作るファイル
faiility_brightdata_new_version.py
reviews_brightData_new_version.py > これは/workspaces/demo/run_reviews_local_interactive.py　を少し変更する。






