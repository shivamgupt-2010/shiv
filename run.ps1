# ShivAI Server Startup Script
Write-Host "Starting ShivAI Core Backend..." -ForegroundColor Cyan

$VenvPython = ".\.venv\Scripts\python.exe"
$VenvUvicorn = ".\.venv\Scripts\uvicorn.exe"

if (-not (Test-Path $VenvUvicorn)) {
    Write-Host "Virtual environment not found. Please run: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}

Write-Host "Running database migrations..." -ForegroundColor Yellow
& ".\.venv\Scripts\alembic.exe" upgrade head

Write-Host "Launching ShivAI API Gateway on http://localhost:8000..." -ForegroundColor Green
& $VenvUvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
