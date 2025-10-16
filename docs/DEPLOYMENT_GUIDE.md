# 🚀 Deployment Guide
## AI-Powered Music Analysis & Generation Platform

---

## Prerequisites

### Required Software
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) (v2.50+)
- [.NET 8.0 SDK](https://dotnet.microsoft.com/download/dotnet/8.0)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Git](https://git-scm.com/downloads)

### Azure Subscription
- Active Azure subscription
- Contributor or Owner role
- Quota for:
  - Azure Kubernetes Service (AKS)
  - GPU VMs (if using GPU node pool)
  - Azure SQL Database

---

## Step 1: Clone Repository

```bash
git clone https://github.com/YOUR_ORG/DirectAI.git
cd DirectAI
```

---

## Step 2: Azure Login

```bash
# Login to Azure
az login

# Set subscription
az account list --output table
az account set --subscription "YOUR_SUBSCRIPTION_NAME"

# Verify current subscription
az account show
```

---

## Step 3: Create Resource Group

```bash
# Create resource group
az group create \
  --name rg-music-platform-dev \
  --location eastus
```

---

## Step 4: Deploy Infrastructure (Bicep)

### Option A: Deploy with Parameter File

Create `infrastructure/parameters.dev.json`:

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "environment": {
      "value": "dev"
    },
    "sqlAdminUsername": {
      "value": "sqladmin"
    },
    "sqlAdminPassword": {
      "value": "REPLACE_WITH_STRONG_PASSWORD"
    }
  }
}
```

Deploy:

```bash
az deployment group create \
  --resource-group rg-music-platform-dev \
  --template-file infrastructure/main.bicep \
  --parameters infrastructure/parameters.dev.json
```

### Option B: Deploy with Inline Parameters

```bash
az deployment group create \
  --resource-group rg-music-platform-dev \
  --template-file infrastructure/main.bicep \
  --parameters \
    environment=dev \
    sqlAdminUsername=sqladmin \
    sqlAdminPassword='YOUR_STRONG_PASSWORD'
```

**Deployment takes 10-15 minutes.**

---

## Step 5: Get Deployment Outputs

```bash
# Get storage account name
az deployment group show \
  --resource-group rg-music-platform-dev \
  --name main \
  --query properties.outputs.storageAccountName.value

# Get SQL server name
az deployment group show \
  --resource-group rg-music-platform-dev \
  --name main \
  --query properties.outputs.sqlServerName.value

# Get AKS name
az deployment group show \
  --resource-group rg-music-platform-dev \
  --name main \
  --query properties.outputs.aksName.value
```

---

## Step 6: Initialize Database

### Connect to Azure SQL

```bash
# Get SQL connection string
SQL_SERVER=$(az deployment group show \
  --resource-group rg-music-platform-dev \
  --name main \
  --query properties.outputs.sqlServerName.value -o tsv)

SQL_DB=$(az deployment group show \
  --resource-group rg-music-platform-dev \
  --name main \
  --query properties.outputs.sqlDatabaseName.value -o tsv)

# Allow your IP to connect
MY_IP=$(curl -s ifconfig.me)
az sql server firewall-rule create \
  --resource-group rg-music-platform-dev \
  --server ${SQL_SERVER%%.*} \
  --name AllowMyIP \
  --start-ip-address $MY_IP \
  --end-ip-address $MY_IP
```

### Run Database Schema

Using Azure Data Studio or sqlcmd:

```bash
sqlcmd -S $SQL_SERVER -d $SQL_DB -U sqladmin -P 'YOUR_PASSWORD' -i database/schema.sql
```

Or using Azure Portal:
1. Navigate to Azure SQL Database
2. Open Query Editor
3. Paste contents of `database/schema.sql`
4. Click "Run"

---

## Step 7: Configure AKS

```bash
# Get AKS credentials
AKS_NAME=$(az deployment group show \
  --resource-group rg-music-platform-dev \
  --name main \
  --query properties.outputs.aksName.value -o tsv)

az aks get-credentials \
  --resource-group rg-music-platform-dev \
  --name $AKS_NAME

# Verify connection
kubectl get nodes

# Create namespace
kubectl create namespace music-platform
```

---

## Step 8: Build and Push Docker Images

### Build Analysis Worker

```bash
cd workers/analysis
docker build -t music-analysis-worker:v1 .

# Get ACR login server
ACR_NAME=$(az deployment group show \
  --resource-group rg-music-platform-dev \
  --name main \
  --query properties.outputs.acrLoginServer.value -o tsv)

# Login to ACR
az acr login --name ${ACR_NAME%%.*}

# Tag and push
docker tag music-analysis-worker:v1 $ACR_NAME/analysis-worker:v1
docker push $ACR_NAME/analysis-worker:v1
```

### Build Generation Worker

```bash
cd workers/generation
docker build -t music-generation-worker:v1 .

docker tag music-generation-worker:v1 $ACR_NAME/generation-worker:v1
docker push $ACR_NAME/generation-worker:v1
```

---

## Step 9: Deploy Workers to AKS

### Create Kubernetes Manifests

Create `k8s/analysis-worker-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: analysis-worker
  namespace: music-platform
spec:
  replicas: 2
  selector:
    matchLabels:
      app: analysis-worker
  template:
    metadata:
      labels:
        app: analysis-worker
    spec:
      containers:
      - name: worker
        image: YOUR_ACR_NAME.azurecr.io/analysis-worker:v1
        resources:
          requests:
            cpu: "2"
            memory: "4Gi"
          limits:
            cpu: "4"
            memory: "8Gi"
        env:
        - name: STORAGE_CONNECTION_STRING
          valueFrom:
            secretKeyRef:
              name: azure-secrets
              key: storage-connection-string
```

### Deploy

```bash
kubectl apply -f k8s/analysis-worker-deployment.yaml
kubectl apply -f k8s/generation-worker-deployment.yaml

# Check status
kubectl get pods -n music-platform
```

---

## Step 10: Deploy .NET API

### Publish .NET API

```bash
cd src/MusicPlatform.Api
dotnet publish -c Release -o ./publish

# Create zip
cd publish
zip -r ../api.zip .
cd ..
```

### Deploy to Azure App Service (or AKS)

**Option A: Azure App Service**

```bash
az webapp create \
  --resource-group rg-music-platform-dev \
  --plan music-dev-plan \
  --name music-api-dev \
  --runtime "DOTNETCORE:8.0"

az webapp deployment source config-zip \
  --resource-group rg-music-platform-dev \
  --name music-api-dev \
  --src api.zip
```

**Option B: AKS**

Create `k8s/api-deployment.yaml` and deploy.

---

## Step 11: Deploy Durable Functions

### Build and Deploy

```bash
cd src/MusicPlatform.Orchestrator

# Install Functions Core Tools (if not installed)
npm install -g azure-functions-core-tools@4

# Publish
func azure functionapp publish music-dev-func
```

---

## Step 12: Verify Deployment

### Check All Resources

```bash
# Check AKS pods
kubectl get pods -n music-platform

# Check Function App logs
az functionapp log tail \
  --resource-group rg-music-platform-dev \
  --name music-dev-func

# Check API endpoint
API_URL="https://music-api-dev.azurewebsites.net"
curl $API_URL/health
```

### Run Smoke Test

```bash
# Upload test audio file
curl -X POST $API_URL/api/audio \
  -F "file=@test-audio.mp3" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Check job status
curl $API_URL/api/jobs/YOUR_JOB_ID
```

---

## Step 13: Configure Monitoring

### Application Insights

```bash
# Get App Insights connection string
AI_CONN=$(az deployment group show \
  --resource-group rg-music-platform-dev \
  --name main \
  --query properties.outputs.appInsightsConnectionString.value -o tsv)

# Set in Function App
az functionapp config appsettings set \
  --resource-group rg-music-platform-dev \
  --name music-dev-func \
  --settings "APPLICATIONINSIGHTS_CONNECTION_STRING=$AI_CONN"
```

### Create Alerts

```bash
# Alert on high error rate
az monitor metrics alert create \
  --name HighErrorRate \
  --resource-group rg-music-platform-dev \
  --scopes /subscriptions/YOUR_SUB_ID/resourceGroups/rg-music-platform-dev/providers/Microsoft.Web/sites/music-api-dev \
  --condition "avg requests/failed > 10" \
  --window-size 5m \
  --evaluation-frequency 1m
```

---

## Step 14: Set Up CI/CD (Optional)

### GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Azure

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup .NET
        uses: actions/setup-dotnet@v3
        with:
          dotnet-version: '8.0.x'
      
      - name: Build
        run: dotnet build --configuration Release
      
      - name: Test
        run: dotnet test
      
      - name: Publish
        run: dotnet publish -c Release -o ./publish
      
      - name: Deploy to Azure
        uses: azure/webapps-deploy@v2
        with:
          app-name: music-api-dev
          publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
          package: ./publish
```

---

## Troubleshooting

### Issue: AKS pods not pulling from ACR

**Solution:**
```bash
# Verify ACR role assignment
az role assignment list --scope /subscriptions/YOUR_SUB_ID/resourceGroups/rg-music-platform-dev/providers/Microsoft.ContainerRegistry/registries/YOUR_ACR
```

### Issue: SQL connection timeout

**Solution:**
```bash
# Check firewall rules
az sql server firewall-rule list \
  --resource-group rg-music-platform-dev \
  --server YOUR_SQL_SERVER

# Add your IP if missing
az sql server firewall-rule create \
  --resource-group rg-music-platform-dev \
  --server YOUR_SQL_SERVER \
  --name AllowMyIP \
  --start-ip-address YOUR_IP \
  --end-ip-address YOUR_IP
```

### Issue: Function App not starting

**Solution:**
```bash
# Check logs
az functionapp log tail \
  --resource-group rg-music-platform-dev \
  --name music-dev-func

# Check app settings
az functionapp config appsettings list \
  --resource-group rg-music-platform-dev \
  --name music-dev-func
```

---

## Clean Up (Development Only)

```bash
# Delete entire resource group
az group delete \
  --name rg-music-platform-dev \
  --yes --no-wait
```

---

## Next Steps

1. **Configure Authentication**: Set up Azure AD B2C or Azure AD
2. **Enable HTTPS**: Configure custom domain and SSL certificate
3. **Set Up Backups**: Configure Azure SQL backups and Blob snapshots
4. **Optimize Costs**: Review and adjust SKUs for production
5. **Load Testing**: Use Azure Load Testing to validate performance

---

## Production Deployment Checklist

- [ ] Change `environment` parameter to `prod`
- [ ] Use Azure Key Vault for all secrets
- [ ] Enable VNet integration for AKS and SQL
- [ ] Configure Azure Front Door or Application Gateway
- [ ] Set up Azure Monitor alerts
- [ ] Enable diagnostic logging for all resources
- [ ] Configure Azure Backup for SQL Database
- [ ] Implement disaster recovery plan
- [ ] Review and harden NSG rules
- [ ] Enable Azure Security Center recommendations

---

**Deployment Time:** ~30-45 minutes (initial)  
**Cost:** ~$100-300/month (dev environment)  
**Last Updated:** October 13, 2025
