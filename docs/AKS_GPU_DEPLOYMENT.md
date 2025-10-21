# Deploying Workers to Azure Kubernetes Service (AKS) with GPU Support

This guide walks you through deploying the music platform's analysis and generation workers to Azure Kubernetes Service with GPU-accelerated nodes.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Architecture](#architecture)
- [Cost Considerations](#cost-considerations)
- [Deployment Steps](#deployment-steps)
- [Verification](#verification)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Scaling](#scaling)

## Overview

The workers are deployed to AKS with dedicated GPU nodes to accelerate:
- **Analysis Worker**: Audio separation (Demucs), beat detection, chord recognition
- **Generation Worker**: Music generation (MusicGen), voice synthesis (Bark)

### GPU Configuration

- **VM Size**: `Standard_NC4as_T4_v3` (NVIDIA T4 GPU)
- **GPU per Pod**: 1 NVIDIA T4 GPU
- **Node Pool**: Auto-scaling from 0-2 nodes (dev) or 1-5 nodes (prod)

## Prerequisites

### Local Tools

1. **Azure CLI** (v2.50.0+)
   ```powershell
   az --version
   az login
   ```

2. **Docker Desktop** (for building images)
   ```powershell
   docker --version
   ```

3. **kubectl** (Kubernetes CLI)
   ```powershell
   kubectl version --client
   ```

4. **Bicep** (included with Azure CLI)
   ```powershell
   az bicep version
   ```

### Azure Subscription

- Active Azure subscription with sufficient quota for:
  - GPU VMs (NC4as_T4_v3)
  - Azure Container Registry (Premium recommended for production)
  - Azure SQL Database
  - Azure Storage

### Quota Check

Before deployment, check your GPU quota:

```powershell
az vm list-usage --location eastus --query "[?contains(name.value, 'NC')]" -o table
```

If you need more quota, submit a support request in the Azure Portal.

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Azure Kubernetes Service              │
│                                                 │
│  ┌──────────────────┐  ┌──────────────────┐   │
│  │  CPU Node Pool   │  │  GPU Node Pool   │   │
│  │                  │  │  (T4 GPUs)       │   │
│  │  - System Pods   │  │                  │   │
│  │  - API Gateway   │  │  - Analysis      │   │
│  │                  │  │  - Generation    │   │
│  └──────────────────┘  └──────────────────┘   │
│                                                 │
└─────────────────────────────────────────────────┘
         │                            │
         ▼                            ▼
┌─────────────────┐         ┌──────────────────┐
│ Azure Container │         │ Azure Storage    │
│ Registry (ACR)  │         │ (Blob Storage)   │
└─────────────────┘         └──────────────────┘
```

## Cost Considerations

### GPU Node Pricing (East US - as of 2024)

| VM Size | GPUs | vCPUs | Memory | Price/hour* |
|---------|------|-------|--------|-------------|
| Standard_NC4as_T4_v3 | 1 T4 | 4 | 28 GB | ~$0.526 |
| Standard_NC6s_v3 | 1 V100 | 6 | 112 GB | ~$3.06 |
| Standard_NC24ads_A100_v4 | 1 A100 | 24 | 220 GB | ~$3.67 |

*Prices vary by region and commitment. Check [Azure Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator/).

### Cost Optimization Tips

1. **Auto-scaling**: Set `minCount: 0` in dev to scale to zero when idle
2. **Spot Instances**: Use spot VMs for non-critical workloads (70-90% savings)
3. **Reserved Instances**: Commit to 1-3 years for 40-65% savings
4. **Right-sizing**: Start with T4 GPUs, upgrade only if needed

## Deployment Steps

### Step 1: Set Environment Variables

```powershell
# Configuration
$resourceGroup = "music-platform-rg"
$location = "eastus"
$environment = "dev"

# SQL credentials (use Azure Key Vault in production)
$env:SQL_ADMIN_USERNAME = "sqladmin"
$env:SQL_ADMIN_PASSWORD = "YourSecurePassword123!"
```

### Step 2: Deploy Infrastructure

Run the automated deployment script:

```powershell
.\scripts\deploy-aks.ps1 `
    -ResourceGroup $resourceGroup `
    -Environment $environment `
    -Location $location
```

This script will:
1. Create resource group
2. Deploy Bicep infrastructure (AKS, ACR, Storage, SQL)
3. Build and push Docker images to ACR
4. Configure kubectl
5. Install NVIDIA GPU device plugin
6. Create Kubernetes secrets
7. Deploy workers to AKS
8. Verify deployment

**Estimated Time**: 15-20 minutes

### Step 3: Manual Deployment (Alternative)

If you prefer step-by-step deployment:

#### 3.1. Deploy Infrastructure

```powershell
az group create --name $resourceGroup --location $location

az deployment group create `
    --resource-group $resourceGroup `
    --template-file infrastructure/main.bicep `
    --parameters environment=$environment `
    --parameters sqlAdminUsername=$env:SQL_ADMIN_USERNAME `
    --parameters sqlAdminPassword=$env:SQL_ADMIN_PASSWORD
```

#### 3.2. Get Deployment Outputs

```powershell
$acrName = az deployment group show `
    --resource-group $resourceGroup `
    --name main `
    --query properties.outputs.acrName.value -o tsv

$aksName = az deployment group show `
    --resource-group $resourceGroup `
    --name main `
    --query properties.outputs.aksName.value -o tsv
```

#### 3.3. Build and Push Images

```powershell
.\scripts\build-workers.ps1 -AcrName $acrName
```

#### 3.4. Configure kubectl

```powershell
az aks get-credentials --resource-group $resourceGroup --name $aksName
```

#### 3.5. Deploy to Kubernetes

```powershell
# Create namespace and GPU device plugin
kubectl apply -f infrastructure/kubernetes/namespace.yaml

# Create secrets
$storageAccountName = az deployment group show `
    --resource-group $resourceGroup `
    --name main `
    --query properties.outputs.storageAccountName.value -o tsv

$storageKey = az storage account keys list `
    --resource-group $resourceGroup `
    --account-name $storageAccountName `
    --query "[0].value" -o tsv

$connectionString = "DefaultEndpointsProtocol=https;AccountName=$storageAccountName;AccountKey=$storageKey;EndpointSuffix=core.windows.net"

kubectl create secret generic music-platform-secrets `
    --namespace music-platform `
    --from-literal=storage-connection-string=$connectionString

# Deploy workers
$acrLoginServer = az acr show --name $acrName --query loginServer -o tsv

(Get-Content infrastructure/kubernetes/analysis-worker.yaml -Raw) `
    -replace '\$\{ACR_NAME\}', $acrName | kubectl apply -f -

(Get-Content infrastructure/kubernetes/generation-worker.yaml -Raw) `
    -replace '\$\{ACR_NAME\}', $acrName | kubectl apply -f -
```

## Verification

### Check Pod Status

```powershell
kubectl get pods -n music-platform -o wide
```

Expected output:
```
NAME                                  READY   STATUS    RESTARTS   AGE   NODE
analysis-worker-xxxxx-yyyyy           1/1     Running   0          5m    aks-gpupool-xxxxx
generation-worker-xxxxx-yyyyy         1/1     Running   0          5m    aks-gpupool-xxxxx
```

### Check GPU Allocation

```powershell
kubectl describe nodes -l accelerator=nvidia | Select-String "nvidia.com/gpu"
```

Expected output:
```
  nvidia.com/gpu:         1
  nvidia.com/gpu:         1
```

### Test Worker Health

```powershell
# Port-forward to analysis worker
kubectl port-forward -n music-platform svc/analysis-worker 8001:8080

# In another terminal, test health endpoint
curl http://localhost:8001/health
```

### View Logs

```powershell
# Analysis worker logs
kubectl logs -n music-platform -l app=analysis-worker -f

# Generation worker logs
kubectl logs -n music-platform -l app=generation-worker -f
```

## Monitoring

### GPU Utilization

Install metrics server (if not already installed):

```powershell
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

Check node metrics:

```powershell
kubectl top nodes
kubectl top pods -n music-platform
```

### Azure Monitor

The infrastructure includes Application Insights and Log Analytics. View metrics in the Azure Portal:

1. Navigate to your AKS cluster
2. Click "Insights" under Monitoring
3. View Container logs, performance metrics, and alerts

### Custom Dashboards

Create a Grafana dashboard for GPU metrics:

```powershell
# Install DCGM exporter for GPU metrics
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/dcgm-exporter/main/dcgm-exporter.yaml
```

## Troubleshooting

### Pods Not Starting

**Issue**: Pods stuck in `Pending` state

```powershell
kubectl describe pod -n music-platform <pod-name>
```

**Common Causes**:
- **No GPU nodes available**: Scale up the GPU node pool
- **GPU not detected**: Check NVIDIA device plugin is running
- **Image pull errors**: Verify ACR integration

**Solutions**:

```powershell
# Check GPU device plugin
kubectl get pods -n kube-system -l name=nvidia-device-plugin-ds

# Manually scale GPU node pool
az aks nodepool scale `
    --resource-group $resourceGroup `
    --cluster-name $aksName `
    --name gpupool `
    --node-count 1
```

### CUDA Out of Memory

**Issue**: Worker crashes with CUDA OOM errors

**Solutions**:
1. Reduce batch size in worker configuration
2. Increase GPU memory by using larger VM sizes (V100/A100)
3. Limit concurrent requests

### Worker Crashes

**Issue**: Pods restarting frequently

```powershell
kubectl logs -n music-platform <pod-name> --previous
```

**Common Causes**:
- Memory limits too low
- Model download failures
- Missing dependencies

**Solutions**:

```powershell
# Increase memory limits in deployment YAML
# Edit: infrastructure/kubernetes/analysis-worker.yaml
# Update resources.limits.memory to 32Gi

kubectl apply -f infrastructure/kubernetes/analysis-worker.yaml
```

## Scaling

### Horizontal Pod Autoscaling (HPA)

HPA is already configured. Monitor autoscaling:

```powershell
kubectl get hpa -n music-platform
```

Adjust scaling parameters:

```yaml
# In infrastructure/kubernetes/analysis-worker.yaml
spec:
  minReplicas: 1
  maxReplicas: 10  # Increase for higher load
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60  # Scale earlier (was 70)
```

### Node Pool Scaling

Scale the GPU node pool manually:

```powershell
az aks nodepool scale `
    --resource-group $resourceGroup `
    --cluster-name $aksName `
    --name gpupool `
    --node-count 3
```

Or update autoscaling limits:

```powershell
az aks nodepool update `
    --resource-group $resourceGroup `
    --cluster-name $aksName `
    --name gpupool `
    --enable-cluster-autoscaler `
    --min-count 1 `
    --max-count 10
```

## Updating Workers

### Deploy New Image

```powershell
# Build and push new images
.\scripts\build-workers.ps1 -AcrName $acrName -Tag "v1.1.0"

# Update deployments
.\scripts\update-workers.ps1 `
    -ResourceGroup $resourceGroup `
    -AksName $aksName `
    -AcrName $acrName `
    -Tag "v1.1.0"
```

### Rolling Update

Kubernetes performs rolling updates automatically, ensuring zero downtime:

```powershell
kubectl rollout status deployment/analysis-worker -n music-platform
kubectl rollout history deployment/analysis-worker -n music-platform
```

### Rollback

If issues occur:

```powershell
kubectl rollout undo deployment/analysis-worker -n music-platform
```

## Clean Up

To delete all resources:

```powershell
# Delete AKS cluster and all resources
az group delete --name $resourceGroup --yes --no-wait
```

To delete only workers:

```powershell
kubectl delete namespace music-platform
```

## Next Steps

1. **Set up CI/CD**: Integrate with GitHub Actions or Azure DevOps
2. **Configure monitoring alerts**: Set up alerts for pod failures, high GPU usage
3. **Implement logging**: Centralize logs with Azure Log Analytics
4. **Add GPU metrics**: Install DCGM exporter and Prometheus
5. **Optimize costs**: Review usage and consider reserved instances

## Additional Resources

- [AKS GPU Documentation](https://learn.microsoft.com/en-us/azure/aks/gpu-cluster)
- [NVIDIA Kubernetes Device Plugin](https://github.com/NVIDIA/k8s-device-plugin)
- [Azure Container Registry](https://learn.microsoft.com/en-us/azure/container-registry/)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
