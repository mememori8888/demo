# PowerShell での実行方法

Windows PowerShell で `run_reviews_local_interactive.py` を実行する方法を説明します。

## 📋 基本的な1行コマンド

### シンプルな実行

```powershell
python run_reviews_local_interactive.py --input results/dental_new.csv --output results/dental_new_reviews.csv --api-token YOUR_API_TOKEN --days-back 10 --start-row 1 --end-row 100 --non-interactive
```

### 複数行で見やすく（バッククォートで改行）

PowerShellでは `` ` `` （バッククォート）で改行できます：

```powershell
python run_reviews_local_interactive.py `
    --input results/dental_new.csv `
    --output results/dental_new_reviews.csv `
    --api-token YOUR_API_TOKEN `
    --days-back 10 `
    --start-row 1 `
    --end-row 100 `
    --non-interactive
```

## 🔐 APIトークンを環境変数で設定

### 一時的な設定（現在のセッションのみ）

```powershell
$env:BRIGHTDATA_API_TOKEN = "your_token_here"
python run_reviews_local_interactive.py --input results/dental_new.csv --output results/dental_new_reviews.csv --non-interactive
```

### 永続的な設定（ユーザー環境変数）

```powershell
[System.Environment]::SetEnvironmentVariable('BRIGHTDATA_API_TOKEN', 'your_token_here', 'User')
```

設定後、PowerShellを再起動してから：

```powershell
python run_reviews_local_interactive.py --input results/dental_new.csv --output results/dental_new_reviews.csv --non-interactive
```

## 📊 実行例（進捗表示付き）

### 例1: 最初の100件を処理

```powershell
python run_reviews_local_interactive.py `
    --input results/dental_new.csv `
    --output results/dental_new_reviews.csv `
    --api-token YOUR_API_TOKEN `
    --start-row 1 `
    --end-row 100 `
    --days-back 10 `
    --non-interactive
```

### 例2: バッチ処理（500件ずつ）

```powershell
# バッチ1
python run_reviews_local_interactive.py `
    --input results/dental_new.csv `
    --output results/dental_new_reviews.csv `
    --update results/dental_new_reviews_batch_1.csv `
    --start-row 1 `
    --end-row 500 `
    --batch-size 50 `
    --non-interactive

# バッチ2
python run_reviews_local_interactive.py `
    --input results/dental_new.csv `
    --output results/dental_new_reviews.csv `
    --update results/dental_new_reviews_batch_2.csv `
    --start-row 501 `
    --end-row 1000 `
    --batch-size 50 `
    --non-interactive
```

### 例3: 環境変数を使った実行

```powershell
$env:BRIGHTDATA_API_TOKEN = "your_token_here"
python run_reviews_local_interactive.py `
    --input results/dental_new.csv `
    --output results/dental_new_reviews.csv `
    --days-back 30 `
    --non-interactive
```

## 📈 進捗表示について

スクリプトは以下の進捗情報を表示します：

### 実行開始時

```
============================================================
🚀 処理を開始します...
============================================================

⏰ 開始時刻: 2026-02-09 15:30:00

✅ APIトークン: ********************abc12345
📁 入力CSV: results/dental_new.csv
📁 出力CSV: results/dental_new_reviews.csv
📊 処理範囲:
   総行数: 1000行
   開始行: 1
   終了行: 100
   処理件数: 100件
```

### 処理中

50行ごとに経過時間が表示されます：

```
⏱️  経過時間: 0:02:15 (50行出力)
⏱️  経過時間: 0:05:30 (100行出力)
⏱️  経過時間: 0:08:45 (150行出力)
```

### 実行終了時

```
============================================================
⏰ 終了時刻: 2026-02-09 15:45:30
⏱️  処理時間: 0:15:30
✅ 処理が完了しました
============================================================
```

## 🔄 複数バッチの自動実行

PowerShellスクリプトで複数バッチを自動実行：

```powershell
# batch_processing.ps1
$env:BRIGHTDATA_API_TOKEN = "your_token_here"

$batchSize = 500
$totalRows = 2000

for ($i = 1; $i -le [Math]::Ceiling($totalRows / $batchSize); $i++) {
    $startRow = ($i - 1) * $batchSize + 1
    $endRow = [Math]::Min($i * $batchSize, $totalRows)
    
    Write-Host "========================================"
    Write-Host "バッチ $i 開始（行 $startRow ～ $endRow）"
    Write-Host "========================================"
    
    python run_reviews_local_interactive.py `
        --input results/dental_new.csv `
        --output results/dental_new_reviews.csv `
        --update results/dental_new_reviews_batch_$i.csv `
        --start-row $startRow `
        --end-row $endRow `
        --batch-size 50 `
        --non-interactive
    
    # バッチ間の待機（API制限対策）
    if ($i -lt [Math]::Ceiling($totalRows / $batchSize)) {
        Write-Host "⏳ 120秒待機中..."
        Start-Sleep -Seconds 120
    }
}

Write-Host "✅ すべてのバッチが完了しました"
```

実行：

```powershell
.\batch_processing.ps1
```

## 📝 ログのリアルタイム監視

別のPowerShellウィンドウでログを監視：

```powershell
Get-Content -Path results/logs/dental_reviews.log -Wait -Tail 50
```

または：

```powershell
# 5秒ごとに最新50行を表示
while ($true) {
    Clear-Host
    Get-Content -Path results/logs/dental_reviews.log -Tail 50
    Start-Sleep -Seconds 5
}
```

## 🛠️ トラブルシューティング

### Pythonが見つからない

```powershell
# Pythonのパスを確認
Get-Command python

# またはフルパスで指定
C:\Python312\python.exe run_reviews_local_interactive.py ...
```

### 文字化けする場合

PowerShellのエンコーディングを設定：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

python run_reviews_local_interactive.py ...
```

### 長いコマンドをファイルから実行

`run_command.txt` に保存：

```
--input results/dental_new.csv
--output results/dental_new_reviews.csv
--api-token YOUR_API_TOKEN
--days-back 10
--start-row 1
--end-row 100
--non-interactive
```

実行：

```powershell
$args = Get-Content run_command.txt | Where-Object { $_ -notmatch '^\s*$' }
python run_reviews_local_interactive.py $args
```

## 💡 便利なエイリアス設定

PowerShell プロファイルに追加（`$PROFILE` で確認）：

```powershell
# プロファイルを開く
notepad $PROFILE

# 以下を追加
function Run-Reviews {
    param(
        [string]$Input = "results/dental_new.csv",
        [string]$Output = "results/dental_new_reviews.csv",
        [int]$StartRow = 1,
        [int]$EndRow = 100,
        [int]$DaysBack = 10
    )
    
    python run_reviews_local_interactive.py `
        --input $Input `
        --output $Output `
        --start-row $StartRow `
        --end-row $EndRow `
        --days-back $DaysBack `
        --non-interactive
}

# エイリアス
Set-Alias reviews Run-Reviews
```

使用例：

```powershell
# デフォルト設定で実行
reviews

# カスタム設定で実行
reviews -StartRow 100 -EndRow 200 -DaysBack 30
```

## 📊 処理結果の確認

```powershell
# 出力ファイルの行数を確認
(Get-Content results/dental_new_reviews.csv).Count - 1  # ヘッダー除く

# 最新10行を表示
Get-Content results/dental_new_reviews.csv -Tail 10

# CSVをテーブル表示
Import-Csv results/dental_new_reviews.csv | Select-Object -First 10 | Format-Table

# ファイルサイズを確認
Get-Item results/dental_new_reviews.csv | Select-Object Name, Length, LastWriteTime
```

## 🔍 エラー時の対処

### ログファイルの確認

```powershell
# エラーログの最後の100行を表示
Get-Content results/logs/dental_reviews.log -Tail 100

# エラー行のみ抽出
Get-Content results/logs/dental_reviews.log | Select-String -Pattern "ERROR|❌"
```

### 詳細なエラー情報

```powershell
# エラー出力をファイルに保存
python run_reviews_local_interactive.py --non-interactive 2>&1 | Tee-Object -FilePath error_log.txt
```

---

**作成日**: 2026-02-09  
**対応環境**: Windows PowerShell 5.1, PowerShell 7.x
