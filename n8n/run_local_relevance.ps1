param(
  [Parameter(Mandatory = $true)]
  [string]$ReviewFile,

  [Parameter(Mandatory = $true)]
  [string]$FacilityFile,

  [Parameter(Mandatory = $true)]
  [string]$RecentReviewGlob,

  [Parameter(Mandatory = $true)]
  [string]$ProfileDir,

  [string]$OutputFile = "",
  [string]$SummaryFile = "",
  [string]$RankDetailFile = "",
  [string]$UnmatchedReviewFile = "",
  [int]$RankLimit = 10,
  [int]$Start = 1,
  [int]$Limit = 0,
  [int]$Timeout = 120,
  [int]$MaxScrolls = 14,
  [int]$SlowMo = 0,
  [switch]$Headless,
  [switch]$ForceSortClick,
  [switch]$AllowFailures
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$scriptPath = Join-Path $repoRoot "scripts\enrich_review_relevance_ranks_local.py"

if (-not (Test-Path -LiteralPath $scriptPath)) {
  throw "Local relevance script not found: $scriptPath"
}
if (-not (Test-Path -LiteralPath $ReviewFile)) {
  throw "review-file not found: $ReviewFile"
}
if (-not (Test-Path -LiteralPath $FacilityFile)) {
  throw "facility-file not found: $FacilityFile"
}
if (-not (Test-Path -LiteralPath $ProfileDir)) {
  throw "profile-dir not found: $ProfileDir"
}

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
  $OutputFile = $ReviewFile
}
if ([string]::IsNullOrWhiteSpace($SummaryFile)) {
  $SummaryFile = Join-Path (Split-Path -Parent $OutputFile) "relevance_rank_summary_local.csv"
}
if ([string]::IsNullOrWhiteSpace($RankDetailFile)) {
  $RankDetailFile = Join-Path (Split-Path -Parent $OutputFile) "relevance_rank_detail_local.csv"
}
if ([string]::IsNullOrWhiteSpace($UnmatchedReviewFile)) {
  $UnmatchedReviewFile = Join-Path (Split-Path -Parent $OutputFile) "relevance_rank_unmatched_reviews_local.csv"
}

$arguments = @(
  $scriptPath,
  "--review-file", $ReviewFile,
  "--output-file", $OutputFile,
  "--facility-file", $FacilityFile,
  "--recent-review-glob", $RecentReviewGlob,
  "--profile-dir", $ProfileDir,
  "--rank-limit", $RankLimit,
  "--start", $Start,
  "--timeout", $Timeout,
  "--max-scrolls", $MaxScrolls,
  "--slow-mo", $SlowMo,
  "--summary-file", $SummaryFile,
  "--rank-detail-file", $RankDetailFile,
  "--unmatched-review-file", $UnmatchedReviewFile
)

if ($Limit -gt 0) {
  $arguments += @("--limit", $Limit)
}
if ($Headless) {
  $arguments += "--headless"
}
if ($ForceSortClick) {
  $arguments += "--force-sort-click"
}
if ($AllowFailures) {
  $arguments += "--allow-failures"
}

Write-Host "repoRoot=$repoRoot"
Write-Host "reviewFile=$ReviewFile"
Write-Host "outputFile=$OutputFile"
Write-Host "facilityFile=$FacilityFile"
Write-Host "recentReviewGlob=$RecentReviewGlob"
Write-Host "profileDir=$ProfileDir"
Write-Host "rankLimit=$RankLimit start=$Start limit=$Limit"

Set-Location -LiteralPath $repoRoot
python @arguments

Write-Host "done"
Write-Host "summaryFile=$SummaryFile"
Write-Host "rankDetailFile=$RankDetailFile"
Write-Host "unmatchedReviewFile=$UnmatchedReviewFile"
