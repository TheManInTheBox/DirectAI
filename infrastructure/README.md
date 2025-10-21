# Infrastructure as Code (IaC)

This directory contains all infrastructure code for deploying the music platform to Azure.

## Contents

### Bicep Templates

- **`main.bicep`** - Main infrastructure template
  - Azure Kubernetes Service (AKS) with GPU node pools
  - Azure Container Registry (ACR)
  - Azure SQL Database
  - Azure Storage Account
  - Application Insights & Log Analytics
  - Azure Functions (Durable Functions)
  - Azure Key Vault

### Kubernetes Manifests

Located in `kubernetes/`:

- **`namespace.yaml`** - Namespace, PVC, NVIDIA GPU device plugin, ConfigMap
- **`analysis-worker.yaml`** - Analysis worker deployment, service, HPA
- **`generation-worker.yaml`** - Generation worker deployment, service, HPA

## Deployment Options

### Option 1: Automated Deployment (Recommended)

Use the deployment script:

```powershell
cd ..
.\scripts\deploy-aks.ps1 -ResourceGroup "music-platform-rg" -Environment "dev"
```

### Option 2: Manual Deployment

Deploy infrastructure:

```powershell
az group create --name music-platform-rg --location eastus

az deployment group create \
  --resource-group music-platform-rg \
  --template-file main.bicep \
  --parameters environment=dev \
  --parameters sqlAdminUsername=sqladmin \
  --parameters sqlAdminPassword='YourPassword123!'
```

Deploy to Kubernetes:

```powershell
# Get AKS credentials
az aks get-credentials --resource-group music-platform-rg --name music-dev-aks

# Apply manifests
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/analysis-worker.yaml
kubectl apply -f kubernetes/generation-worker.yaml
```

## Architecture

```
Azure Subscription
│
├── Resource Group: music-platform-rg
│   │
│   ├── AKS Cluster: music-dev-aks
│   │   ├── CPU Node Pool (system)
│   │   └── GPU Node Pool (T4 GPUs)
│   │
│   ├── Container Registry: musicdevacr
│   │   ├── analysis-worker:latest
│   │   └── generation-worker:latest
│   │
│   ├── Storage Account: stmusicdevaudio
│   │   ├── audio-files (container)
│   │   ├── stems (container)
│   │   ├── generated (container)
│   │   └── jams (container)
│   │
│   ├── SQL Server: music-dev-sql
│   │   └── Database: music-metadata
│   │
│   ├── Key Vault: music-dev-kv
│   ├── App Insights: music-dev-appi
│   └── Log Analytics: music-dev-logs
```

## Resource Naming Convention

Format: `{resourceType}-{environment}-{purpose}`

Examples:
- `music-dev-aks` - AKS cluster for dev environment
- `musicdevacr` - ACR (no hyphens allowed)
- `music-dev-sql` - SQL Server for dev environment

## Parameters

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `sqlAdminUsername` | securestring | SQL admin username |
| `sqlAdminPassword` | securestring | SQL admin password (min 12 chars) |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `environment` | string | `dev` | Environment (dev, staging, prod) |
| `location` | string | Resource Group location | Azure region |

## Outputs

The Bicep template outputs the following values:

| Output | Description |
|--------|-------------|
| `storageAccountName` | Storage account name |
| `sqlServerName` | SQL server FQDN |
| `sqlDatabaseName` | SQL database name |
| `aksName` | AKS cluster name |
| `acrName` | Container registry name |
| `acrLoginServer` | ACR login server URL |
| `functionAppName` | Function app name |
| `appInsightsConnectionString` | Application Insights connection string |
| `keyVaultName` | Key Vault name |

## GPU Node Pool Configuration

The infrastructure includes a GPU node pool with:

- **VM Size**: `Standard_NC4as_T4_v3` (NVIDIA T4)
- **Auto-scaling**: 0-2 nodes (dev), 1-5 nodes (prod)
- **Node Taints**: `sku=gpu:NoSchedule` (GPU workloads only)
- **Node Labels**: 
  - `accelerator: nvidia`
  - `gpu-type: t4`
  - `workload: ai`

### Alternative GPU VMs

To use different GPU VMs, update `main.bicep`:

```bicep
resource aksGpuNodePool 'Microsoft.ContainerService/managedClusters/agentPools@2024-02-01' = {
  properties: {
    vmSize: 'Standard_NC6s_v3'  // NVIDIA V100 (more powerful)
    // or
    vmSize: 'Standard_NC24ads_A100_v4'  // NVIDIA A100 (highest performance)
  }
}
```

## Cost Optimization

### Development Environment

- GPU node pool scales to 0 when idle
- Use smaller VM sizes
- Single-region deployment
- Basic SKUs for ACR

### Production Environment

- Reserved instances (40-65% savings)
- Spot instances for batch workloads (70-90% savings)
- Premium ACR with geo-replication
- Backup and disaster recovery

## Security

### Managed Identities

All services use managed identities:
- AKS → ACR (pull images)
- Function App → Storage (access blobs)
- Function App → Key Vault (read secrets)

### Network Security

For production:
1. Enable private endpoints for Storage, SQL, ACR
2. Use Azure Private Link
3. Configure NSGs and firewall rules
4. Enable Azure Policy

### Secret Management

Secrets are stored in:
- **Azure Key Vault** - Application secrets
- **Kubernetes Secrets** - Runtime configuration (storage connection strings)

## Monitoring

### Application Insights

Collects:
- Application telemetry
- Custom events
- Performance metrics
- Exceptions

### Log Analytics

Queries:
- Container logs
- AKS cluster logs
- Resource diagnostics

### Example KQL Queries

```kql
// Failed pods in last hour
KubePodInventory
| where TimeGenerated > ago(1h)
| where PodStatus == "Failed"

// GPU node metrics
Perf
| where ObjectName == "K8SNode"
| where CounterName == "gpuUsagePercent"
| summarize avg(CounterValue) by bin(TimeGenerated, 5m)
```

## Updating Infrastructure

### Update GPU Node Pool

```powershell
az aks nodepool update \
  --resource-group music-platform-rg \
  --cluster-name music-dev-aks \
  --name gpupool \
  --min-count 2 \
  --max-count 10
```

### Update Kubernetes Deployments

```powershell
kubectl apply -f kubernetes/analysis-worker.yaml
kubectl rollout status deployment/analysis-worker -n music-platform
```

## Cleanup

### Delete All Resources

```powershell
az group delete --name music-platform-rg --yes --no-wait
```

### Delete Kubernetes Resources Only

```powershell
kubectl delete namespace music-platform
```

## Documentation

- **[AKS_GPU_DEPLOYMENT.md](../docs/AKS_GPU_DEPLOYMENT.md)** - Complete deployment guide
- **[AKS_QUICK_REFERENCE.md](../docs/AKS_QUICK_REFERENCE.md)** - Quick reference commands
- **[DEPLOYMENT_GUIDE.md](../docs/DEPLOYMENT_GUIDE.md)** - General deployment guide

## Troubleshooting

### Bicep Validation Errors

```powershell
az deployment group validate \
  --resource-group music-platform-rg \
  --template-file main.bicep \
  --parameters environment=dev
```

### What-If Preview

```powershell
az deployment group what-if \
  --resource-group music-platform-rg \
  --template-file main.bicep \
  --parameters environment=dev
```

### Common Issues

1. **GPU quota exceeded** - Request quota increase in Azure Portal
2. **ACR authentication failed** - Run `az acr login --name <acr-name>`
3. **Kubernetes API unreachable** - Check AKS is running and get credentials again
4. **NVIDIA plugin not running** - Verify GPU nodes exist and plugin is deployed

## Support

For issues or questions:
1. Check troubleshooting section in [AKS_GPU_DEPLOYMENT.md](../docs/AKS_GPU_DEPLOYMENT.md)
2. Review Azure Monitor logs
3. Check Kubernetes events: `kubectl get events -n music-platform`
