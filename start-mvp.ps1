# MVP Quick Start Script
# Run this after starting Docker Desktop

Write-Host "🚀 Starting MVP Services..." -ForegroundColor Cyan

# Build and start analysis worker with optimizations
Write-Host "`n📦 Building optimized analysis worker..." -ForegroundColor Yellow
docker compose build analysis-worker

# Start all services
Write-Host "`n🔄 Starting all services..." -ForegroundColor Yellow
docker compose up -d

# Wait for services to initialize
Write-Host "`n⏳ Waiting for services to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check service status
Write-Host "`n✅ Service Status:" -ForegroundColor Green
docker compose ps

# Test API
Write-Host "`n🔍 Testing API connectivity..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:5000/api/audio" -Method Get -ErrorAction Stop
    Write-Host "✅ API is accessible!" -ForegroundColor Green
} catch {
    Write-Host "⚠️  API not ready yet. Wait 10 seconds and try: http://localhost:5000/swagger" -ForegroundColor Yellow
}

Write-Host "`n" -NoNewline
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  MVP READY TO TEST!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 API Swagger UI: " -NoNewline
Write-Host "http://localhost:5000/swagger" -ForegroundColor Cyan
Write-Host "📍 Analysis optimized for ~60 second completion" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor White
Write-Host "  1. Start MAUI app: cd src\MusicPlatform.Maui; dotnet run -f net9.0-windows10.0.19041.0" -ForegroundColor Gray
Write-Host "  2. Upload MP3 file via drag-and-drop" -ForegroundColor Gray
Write-Host "  3. Click 'Analyze' button" -ForegroundColor Gray
Write-Host "  4. Wait ~60 seconds for analysis to complete" -ForegroundColor Gray
Write-Host "  5. Generate stems" -ForegroundColor Gray
Write-Host ""
