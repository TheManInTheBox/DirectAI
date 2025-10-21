# ========================================
# Build and Push Worker Images to ACR
# ========================================
# This script builds GPU-enabled Docker images for the workers
# and pushes them to Azure Container Registry.
#
# Usage:
#   .\build-workers.ps1 -AcrName "musicdevacr" [-Workers @("analysis", "generation")]
# ========================================

param(
    [Parameter(Mandatory=$true)]
    [string]$AcrName,
    
    [Parameter(Mandatory=$false)]
    [string[]]$Workers = @("analysis", "generation"),
    
    [Parameter(Mandatory=$false)]
    [string]$Tag = "latest"
)

$ErrorActionPreference = 'Stop'

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Building Worker Images for AKS" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "ACR: $AcrName" -ForegroundColor Yellow
Write-Host "Workers: $($Workers -join ', ')" -ForegroundColor Yellow
Write-Host "Tag: $Tag" -ForegroundColor Yellow
Write-Host ""

# Login to ACR
Write-Host "Logging into Azure Container Registry..." -ForegroundColor Green
az acr login --name $AcrName

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to login to ACR"
    exit 1
}

$acrLoginServer = az acr show --name $AcrName --query loginServer -o tsv

# Build and push each worker
foreach ($worker in $Workers) {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "Building $worker worker..." -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Cyan
    
    $imageName = "${acrLoginServer}/${worker}-worker:${Tag}"
    $dockerfilePath = "workers/${worker}/Dockerfile.gpu"
    $contextPath = "workers/${worker}"
    
    if (-not (Test-Path $dockerfilePath)) {
        Write-Warning "Dockerfile not found: $dockerfilePath. Skipping..."
        continue
    }
    
    # Build image
    Write-Host "Building image: $imageName" -ForegroundColor Yellow
    docker build -f $dockerfilePath -t $imageName $contextPath
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to build $worker worker image"
        exit 1
    }
    
    # Push image
    Write-Host "Pushing image: $imageName" -ForegroundColor Yellow
    docker push $imageName
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to push $worker worker image"
        exit 1
    }
    
    Write-Host "$worker worker image built and pushed successfully!" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "All Images Built Successfully!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Images in ACR:" -ForegroundColor Yellow
az acr repository list --name $AcrName --output table
