# Run the whole stack locally with no Docker and no credentials.
# Usage: .\scripts\dev.ps1

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

# --- Backend ---
Write-Host "==> Starting API on http://127.0.0.1:8000" -ForegroundColor Cyan
$api = Start-Process -NoNewWindow -PassThru -FilePath "$Root\backend\.venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload" `
    -WorkingDirectory "$Root\backend"

# --- Frontend ---
Write-Host "==> Starting frontend on http://127.0.0.1:5173" -ForegroundColor Cyan
$ui = Start-Process -NoNewWindow -PassThru -FilePath "npm" `
    -ArgumentList "run dev" `
    -WorkingDirectory "$Root\frontend"

Write-Host "`nBoth servers running. Press Ctrl+C to stop.`n" -ForegroundColor Green

try {
    Wait-Process -Id $api.Id
} finally {
    # Clean up both processes on exit
    if (!$api.HasExited)  { Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue }
    if (!$ui.HasExited)   { Stop-Process -Id $ui.Id  -Force -ErrorAction SilentlyContinue }
}
