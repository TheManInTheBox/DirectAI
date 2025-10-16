# 🎵 Music Platform Quick Reference
## Essential Commands & Workflows

---

## 📂 Project Structure

```
DirectAI/
├── docs/
│   ├── MUSIC_PLATFORM_ARCHITECTURE.md    # Full technical spec
│   ├── HIRING_EXPERTS.md                 # Recruitment guide
│   ├── PROJECT_SUMMARY.md                # Executive summary
│   └── QUICK_REFERENCE.md                # This file
├── database/
│   └── schema.sql                        # SQL schema
├── src/
│   ├── DirectML.AI/                      # Existing DirectML inference engine
│   └── MusicPlatform.Domain/             # NEW: Domain models
└── samples/                              # Example projects
```

---

## 🚀 Quick Start for New Team Members

### 1. Prerequisites
```powershell
# Install .NET 8.0 SDK
winget install Microsoft.DotNet.SDK.8

# Install Azure CLI
winget install Microsoft.AzureCLI

# Install Docker Desktop
winget install Docker.DockerDesktop

# Login to Azure
az login
az account set --subscription "YOUR_SUBSCRIPTION_NAME"
```

### 2. Build Domain Models
```powershell
cd src\MusicPlatform.Domain
dotnet build
dotnet test  # (when tests are added)
```

### 3. Deploy Database Schema
```powershell
# Connect to Azure SQL
az sql db show-connection-string --client ado.net

# Run migration (using sqlcmd or SQL Server Management Studio)
sqlcmd -S your-server.database.windows.net -d music-metadata -U sqladmin -P <password> -i database\schema.sql
```

---

## 🏗️ Azure Resource Deployment

### Create Resource Group
```bash
az group create \
  --name rg-music-platform-prod \
  --location eastus
```

### Deploy AKS Cluster
```bash
az aks create \
  --resource-group rg-music-platform-prod \
  --name aks-music-workers \
  --node-count 3 \
  --node-vm-size Standard_D8s_v3 \
  --enable-managed-identity \
  --generate-ssh-keys

# Add GPU node pool
az aks nodepool add \
  --resource-group rg-music-platform-prod \
  --cluster-name aks-music-workers \
  --name gpupool \
  --node-count 2 \
  --node-vm-size Standard_NC6s_v3 \
  --node-taints gpu=true:NoSchedule
```

### Create Storage Account
```bash
az storage account create \
  --name stmusicaudio \
  --resource-group rg-music-platform-prod \
  --location eastus \
  --sku Standard_LRS

# Create blob containers
az storage container create --name raw-audio --account-name stmusicaudio
az storage container create --name stems --account-name stmusicaudio
az storage container create --name generated --account-name stmusicaudio
az storage container create --name jams --account-name stmusicaudio
```

### Create Azure SQL Database
```bash
az sql server create \
  --name sql-music-metadata \
  --resource-group rg-music-platform-prod \
  --location eastus \
  --admin-user sqladmin \
  --admin-password <STRONG_PASSWORD>

az sql db create \
  --resource-group rg-music-platform-prod \
  --server sql-music-metadata \
  --name music-metadata \
  --service-objective S3
```

---

## 🐳 Docker Commands

### Build Analysis Worker
```bash
cd workers/analysis
docker build -t music-analysis-worker:latest .
docker run -p 8080:8080 music-analysis-worker:latest
```

### Build Generation Worker (GPU)
```bash
cd workers/generation
docker build -t music-generation-worker:latest .
docker run --gpus all -p 8080:8080 music-generation-worker:latest
```

### Push to Azure Container Registry
```bash
az acr login --name musicplatformacr
docker tag music-analysis-worker:latest musicplatformacr.azurecr.io/analysis-worker:v1
docker push musicplatformacr.azurecr.io/analysis-worker:v1
```

---

## ☸️ Kubernetes Commands

### Deploy Worker to AKS
```bash
# Get AKS credentials
az aks get-credentials --resource-group rg-music-platform-prod --name aks-music-workers

# Apply manifests
kubectl apply -f k8s/analysis-worker-deployment.yaml
kubectl apply -f k8s/generation-worker-deployment.yaml

# Check pod status
kubectl get pods -n music-platform
kubectl logs -f <pod-name>

# Scale deployment
kubectl scale deployment analysis-worker --replicas=5
```

### GPU Node Verification
```bash
kubectl get nodes -o wide
kubectl describe node <gpu-node-name> | grep -i nvidia
```

---

## 🔧 Development Workflows

### Add New Domain Model
1. Create `src/MusicPlatform.Domain/Models/YourModel.cs`
2. Add corresponding SQL table to `database/schema.sql`
3. Update Entity Framework DbContext
4. Create migration: `dotnet ef migrations add AddYourModel`

### Run Local API
```powershell
cd src/MusicPlatform.Api
dotnet watch run
```

### Run Durable Function Locally
```powershell
cd src/MusicPlatform.Orchestrator
func start
```

---

## 📊 Monitoring & Debugging

### View Application Insights Logs
```bash
az monitor app-insights query \
  --app appi-music-platform \
  --analytics-query "traces | where message contains 'AnalysisStarted' | top 10 by timestamp desc"
```

### Check Durable Function Status
```bash
# Get orchestration instance ID from Job table
az functionapp function show \
  --name func-music-orchestrator \
  --resource-group rg-music-platform-prod \
  --function-name AnalysisOrchestrator
```

### Query Blob Storage
```bash
az storage blob list \
  --account-name stmusicaudio \
  --container-name raw-audio \
  --output table
```

---

## 🧪 Testing

### Run Unit Tests
```powershell
dotnet test tests/MusicPlatform.Domain.Tests
dotnet test tests/MusicPlatform.Api.Tests
```

### Run Integration Tests
```powershell
dotnet test tests/MusicPlatform.Integration.Tests --filter Category=Integration
```

### Load Testing (Azure Load Testing)
```bash
az load test create \
  --name music-api-load-test \
  --resource-group rg-music-platform-prod \
  --test-plan load-tests/api-test.jmx
```

---

## 🔐 Security

### Get Secret from Key Vault
```bash
az keyvault secret show \
  --vault-name kv-music-platform \
  --name sql-connection-string
```

### Rotate Storage Account Key
```bash
az storage account keys renew \
  --account-name stmusicaudio \
  --key primary
```

### Assign Managed Identity Role
```bash
az role assignment create \
  --assignee <managed-identity-id> \
  --role "Storage Blob Data Contributor" \
  --scope /subscriptions/<sub-id>/resourceGroups/rg-music-platform-prod
```

---

## 📦 CI/CD

### GitHub Actions Workflow
```yaml
# .github/workflows/deploy.yml
name: Deploy to Azure
on:
  push:
    branches: [main]
jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build .NET
        run: dotnet build
      - name: Run Tests
        run: dotnet test
      - name: Deploy to Azure
        run: az webapp deployment source config-zip ...
```

### Manual Deployment
```bash
# Publish .NET API
dotnet publish -c Release -o ./publish
az webapp deployment source config-zip \
  --resource-group rg-music-platform-prod \
  --name webapp-music-api \
  --src publish.zip
```

---

## 🐛 Common Issues & Solutions

### Issue: AKS GPU nodes not scheduling pods
**Solution:**
```bash
kubectl describe node <gpu-node>
# Check for taints and tolerations
# Ensure NVIDIA device plugin is installed
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml
```

### Issue: Blob upload fails with 403
**Solution:**
```bash
# Check Managed Identity has correct role
az role assignment list --assignee <identity-id>
# Add Storage Blob Data Contributor role if missing
```

### Issue: Durable Function stuck in "Running" state
**Solution:**
```bash
# Check orchestration history in Azure Portal
# Review Application Insights for exceptions
# Manually terminate if needed
```

---

## 📞 Support & Resources

### Documentation
- [Azure Durable Functions Docs](https://learn.microsoft.com/en-us/azure/azure-functions/durable/)
- [AKS GPU Support](https://learn.microsoft.com/en-us/azure/aks/gpu-cluster)
- [JAMS Specification](https://jams.readthedocs.io/)

### Code Repositories
- [Demucs](https://github.com/facebookresearch/demucs)
- [Essentia](https://github.com/MTG/essentia)
- [Stable Audio Tools](https://github.com/Stability-AI/stable-audio-tools)

### Team Communication
- Slack: #music-platform-dev
- GitHub Discussions: For architecture questions
- Azure DevOps: Sprint planning and tracking

---

## 📋 Checklists

### Daily Developer Checklist
- [ ] Pull latest changes from `main`
- [ ] Run `dotnet build` to ensure no breaking changes
- [ ] Run `dotnet test` before committing
- [ ] Check Azure costs dashboard (stay under budget)
- [ ] Review Application Insights for errors

### Weekly Team Checklist
- [ ] Sprint planning meeting (Mondays)
- [ ] Demo completed features (Fridays)
- [ ] Review and merge PRs
- [ ] Update documentation for new features
- [ ] Check AKS node health and GPU utilization

---

**Last Updated:** October 13, 2025  
**Maintained By:** Platform Team  
**Questions?** See `MUSIC_PLATFORM_ARCHITECTURE.md` for full details.
