# AURA-VIP Setup Script for Windows PowerShell

Write-Host "🚀 Setting up AURA-VIP Orchestration System..." -ForegroundColor Green

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "📝 Creating .env file from template..." -ForegroundColor Yellow
    Copy-Item .env.template .env
    Write-Host "✅ .env file created. Please update with your configuration." -ForegroundColor Green
} else {
    Write-Host "✅ .env file already exists." -ForegroundColor Green
}

# Backend setup
Write-Host ""
Write-Host "🐍 Setting up Python backend..." -ForegroundColor Cyan
Set-Location backend

if (-not (Test-Path venv)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

Set-Location ..

# Frontend setup
Write-Host ""
Write-Host "⚛️  Setting up React frontend..." -ForegroundColor Cyan
Set-Location frontend

if (-not (Test-Path node_modules)) {
    Write-Host "Installing Node dependencies..." -ForegroundColor Yellow
    npm install
} else {
    Write-Host "✅ Node modules already installed." -ForegroundColor Green
}

Set-Location ..

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To start the backend:" -ForegroundColor Cyan
Write-Host "  cd backend"
Write-Host "  .\venv\Scripts\Activate.ps1"
Write-Host "  python main.py"
Write-Host ""
Write-Host "To start the frontend:" -ForegroundColor Cyan
Write-Host "  cd frontend"
Write-Host "  npm run dev"
