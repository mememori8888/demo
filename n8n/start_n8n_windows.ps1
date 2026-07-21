$ErrorActionPreference = "Stop"

if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
  throw "npx is not available. Install Node.js first: https://nodejs.org/"
}

$env:N8N_USER_FOLDER = "D:\python\demo\demo\n8n\.n8n-user"
$env:N8N_SECURE_COOKIE = "false"
$env:N8N_DIAGNOSTICS_ENABLED = "false"
$env:N8N_PERSONALIZATION_ENABLED = "false"

New-Item -ItemType Directory -Force -Path $env:N8N_USER_FOLDER | Out-Null

Write-Host "Starting n8n..."
Write-Host "Open: http://localhost:5678"
Write-Host "Import workflow: D:\python\demo\demo\n8n\google_reviews_local_relevance_workflow.json"

npx n8n start
