# ========================================
# Update Worker Deployments in AKS
# ========================================
# This script updates the worker deployments in AKS with new images.
# Useful for CI/CD pipelines or manual updates.
#
# Usage:
#   .\update-workers.ps1 -ResourceGroup "music-platform-rg" -AksName "music-dev-aks" -AcrName "musicdevacr"
# ========================================

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,
    
    [Parameter(Mandatory=$true)]
    [string]$AksName,
    
    [Parameter(Mandatory=$true)]
    [string]$AcrName,
    
    [Parameter(Mandatory=$false)]
    [string]$Namespace = "music-platform",
    
    [Parameter(Mandatory=$false)]
    [string]$Tag = "latest"
)

$ErrorActionPreference = 'Stop'

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Updating Worker Deployments in AKS" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Get AKS credentials
Write-Host "Getting AKS credentials..." -ForegroundColor Green
az aks get-credentials --resource-group $ResourceGroup --name $AksName --overwrite-existing

# Get ACR login server
$acrLoginServer = az acr show --name $AcrName --query loginServer -o tsv

# Update analysis worker
Write-Host ""
Write-Host "Updating analysis-worker deployment..." -ForegroundColor Yellow
kubectl set image deployment/analysis-worker `
    analysis-worker="${acrLoginServer}/analysis-worker:${Tag}" `
    --namespace $Namespace

kubectl rollout status deployment/analysis-worker --namespace $Namespace

# Update generation worker
Write-Host ""
Write-Host "Updating generation-worker deployment..." -ForegroundColor Yellow
kubectl set image deployment/generation-worker `
    generation-worker="${acrLoginServer}/generation-worker:${Tag}" `
    --namespace $Namespace

kubectl rollout status deployment/generation-worker --namespace $Namespace

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Deployments Updated Successfully!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Show pod status
Write-Host "Current Pod Status:" -ForegroundColor Cyan
kubectl get pods --namespace $Namespace -o wide

Write-Host ""
Write-Host "Recent Events:" -ForegroundColor Cyan
kubectl get events --namespace $Namespace --sort-by='.lastTimestamp' | Select-Object -Last 10
