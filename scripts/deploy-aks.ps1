# ========================================
# Deploy Workers to AKS with GPU Support
# ========================================
# This script deploys the music platform workers to Azure Kubernetes Service
# with GPU-enabled nodes for accelerated audio processing.
#
# Prerequisites:
# - Azure CLI installed and logged in
# - Docker installed and running
# - kubectl installed
# - Bicep infrastructure deployed
#
# Usage:
#   .\deploy-aks.ps1 -ResourceGroup "music-platform-rg" -Environment "dev"
# ========================================

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,
    
    [Parameter(Mandatory=$false)]
    [ValidateSet('dev', 'staging', 'prod')]
    [string]$Environment = 'dev',
    
    [Parameter(Mandatory=$false)]
    [string]$Location = 'eastus'
)

$ErrorActionPreference = 'Stop'

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Deploying Workers to AKS with GPU Support" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host "Resource Group: $ResourceGroup" -ForegroundColor Yellow
Write-Host "Location: $Location" -ForegroundColor Yellow
Write-Host ""

# ========================================
# Step 1: Deploy Infrastructure
# ========================================
Write-Host "Step 1: Deploying Azure Infrastructure..." -ForegroundColor Green

# Check if resource group exists
$rgExists = az group exists --name $ResourceGroup
if ($rgExists -eq "false") {
    Write-Host "Creating resource group: $ResourceGroup" -ForegroundColor Yellow
    az group create --name $ResourceGroup --location $Location
}

# Get SQL credentials (use secure input in production)
if (-not $env:SQL_ADMIN_USERNAME) {
    $sqlUsername = Read-Host "Enter SQL Admin Username"
} else {
    $sqlUsername = $env:SQL_ADMIN_USERNAME
}

if (-not $env:SQL_ADMIN_PASSWORD) {
    $sqlPassword = Read-Host "Enter SQL Admin Password" -AsSecureString
    $sqlPasswordText = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sqlPassword)
    )
} else {
    $sqlPasswordText = $env:SQL_ADMIN_PASSWORD
}

# Deploy Bicep template
Write-Host "Deploying Bicep infrastructure..." -ForegroundColor Yellow
$deploymentOutput = az deployment group create `
    --resource-group $ResourceGroup `
    --template-file "infrastructure/main.bicep" `
    --parameters environment=$Environment `
    --parameters sqlAdminUsername=$sqlUsername `
    --parameters sqlAdminPassword=$sqlPasswordText `
    --parameters location=$Location `
    --output json 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "Deployment output: $deploymentOutput" -ForegroundColor Red
    Write-Error "Infrastructure deployment failed"
    exit 1
}

$deployment = $deploymentOutput | ConvertFrom-Json

Write-Host "Infrastructure deployed successfully!" -ForegroundColor Green

# Extract outputs
$acrName = $deployment.properties.outputs.acrName.value
$acrLoginServer = $deployment.properties.outputs.acrLoginServer.value
$aksName = $deployment.properties.outputs.aksName.value
$storageAccountName = $deployment.properties.outputs.storageAccountName.value

Write-Host ""
Write-Host "Deployment Outputs:" -ForegroundColor Cyan
Write-Host "  ACR Name: $acrName" -ForegroundColor White
Write-Host "  ACR Login Server: $acrLoginServer" -ForegroundColor White
Write-Host "  AKS Name: $aksName" -ForegroundColor White
Write-Host "  Storage Account: $storageAccountName" -ForegroundColor White
Write-Host ""

# ========================================
# Step 2: Build and Push Docker Images
# ========================================
Write-Host "Step 2: Building and Pushing Docker Images..." -ForegroundColor Green

# Login to ACR
Write-Host "Logging into Azure Container Registry..." -ForegroundColor Yellow
az acr login --name $acrName

# Build and push analysis worker
Write-Host "Building analysis-worker image..." -ForegroundColor Yellow
docker build -f workers/analysis/Dockerfile.gpu -t ${acrLoginServer}/analysis-worker:latest workers/analysis
docker push ${acrLoginServer}/analysis-worker:latest

# Build and push generation worker
Write-Host "Building generation-worker image..." -ForegroundColor Yellow
docker build -f workers/generation/Dockerfile.gpu -t ${acrLoginServer}/generation-worker:latest workers/generation
docker push ${acrLoginServer}/generation-worker:latest

Write-Host "Docker images pushed successfully!" -ForegroundColor Green
Write-Host ""

# ========================================
# Step 3: Configure kubectl
# ========================================
Write-Host "Step 3: Configuring kubectl..." -ForegroundColor Green

az aks get-credentials --resource-group $ResourceGroup --name $aksName --overwrite-existing

Write-Host "kubectl configured successfully!" -ForegroundColor Green
Write-Host ""

# ========================================
# Step 4: Install NVIDIA Device Plugin
# ========================================
Write-Host "Step 4: Installing NVIDIA GPU Device Plugin..." -ForegroundColor Green

# Apply namespace and GPU device plugin
kubectl apply -f infrastructure/kubernetes/namespace.yaml

Write-Host "NVIDIA GPU Device Plugin installed!" -ForegroundColor Green
Write-Host ""

# ========================================
# Step 5: Create Kubernetes Secrets
# ========================================
Write-Host "Step 5: Creating Kubernetes Secrets..." -ForegroundColor Green

# Get storage connection string
$storageKey = az storage account keys list --resource-group $ResourceGroup --account-name $storageAccountName --query "[0].value" -o tsv
$storageConnectionString = "DefaultEndpointsProtocol=https;AccountName=$storageAccountName;AccountKey=$storageKey;EndpointSuffix=core.windows.net"

# Create secret
kubectl create secret generic music-platform-secrets `
    --namespace music-platform `
    --from-literal=storage-connection-string=$storageConnectionString `
    --dry-run=client -o yaml | kubectl apply -f -

Write-Host "Secrets created successfully!" -ForegroundColor Green
Write-Host ""

# ========================================
# Step 6: Deploy Workers
# ========================================
Write-Host "Step 6: Deploying Workers to Kubernetes..." -ForegroundColor Green

# Replace placeholders in YAML files
$analysisYaml = Get-Content -Path "infrastructure/kubernetes/analysis-worker.yaml" -Raw
$analysisYaml = $analysisYaml -replace '\$\{ACR_NAME\}', $acrName
$analysisYaml | kubectl apply -f -

$generationYaml = Get-Content -Path "infrastructure/kubernetes/generation-worker.yaml" -Raw
$generationYaml = $generationYaml -replace '\$\{ACR_NAME\}', $acrName
$generationYaml | kubectl apply -f -

Write-Host "Workers deployed successfully!" -ForegroundColor Green
Write-Host ""

# ========================================
# Step 7: Verify Deployment
# ========================================
Write-Host "Step 7: Verifying Deployment..." -ForegroundColor Green
Write-Host ""

Write-Host "Waiting for pods to be ready..." -ForegroundColor Yellow
kubectl wait --for=condition=ready pod -l app=analysis-worker --namespace music-platform --timeout=300s
kubectl wait --for=condition=ready pod -l app=generation-worker --namespace music-platform --timeout=300s

Write-Host ""
Write-Host "Pod Status:" -ForegroundColor Cyan
kubectl get pods --namespace music-platform -o wide

Write-Host ""
Write-Host "GPU Allocation:" -ForegroundColor Cyan
kubectl describe nodes -l accelerator=nvidia | Select-String -Pattern "nvidia.com/gpu"

Write-Host ""
Write-Host "Service Status:" -ForegroundColor Cyan
kubectl get services --namespace music-platform

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Test workers: kubectl port-forward -n music-platform svc/analysis-worker 8001:8080" -ForegroundColor White
Write-Host "  2. View logs: kubectl logs -n music-platform -l app=analysis-worker -f" -ForegroundColor White
Write-Host "  3. Monitor GPU usage: kubectl top nodes" -ForegroundColor White
Write-Host ""
