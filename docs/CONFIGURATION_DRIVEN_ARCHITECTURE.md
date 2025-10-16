# Configuration-Driven Architecture
## One Codebase, Multiple Environments

This document explains how the **same codebase** runs both locally (Docker Desktop) and in Azure (cloud production).

---

## 🎯 Design Principle

**"Configuration over Duplication"**

- ✅ **Same .NET API code** → Works locally and in Azure
- ✅ **Same Python workers** → Docker containers run anywhere  
- ✅ **Same MAUI app** → Cross-platform desktop/mobile client
- ✅ **Configuration only** → Different connection strings, URLs, auth

---

## 🏗️ Architecture Comparison

### Local Development (Docker Desktop)
```
┌──────────────┐
│  MAUI App    │
│ (localhost)  │
└──────┬───────┘
       │ HTTP
       ▼
┌─────────────────────────┐
│  .NET API (Docker)      │
│  Port: 5000             │
└───┬─────────────┬───────┘
    │             │
    ▼             ▼
┌──────────┐  ┌───────────┐
│PostgreSQL│  │  Azurite  │
│(Docker)  │  │  (Docker) │
└──────────┘  └───────────┘
    │             │
    ▼             ▼
┌──────────────────────────┐
│  Python Workers (Docker) │
│  - Analysis              │
│  - Generation            │
└──────────────────────────┘
```

### Azure Production
```
┌──────────────┐
│  MAUI App    │
│ (any device) │
└──────┬───────┘
       │ HTTPS
       ▼
┌─────────────────────────┐
│  .NET API (App Service) │
│  + Durable Functions    │
└───┬─────────────┬───────┘
    │             │
    ▼             ▼
┌──────────┐  ┌────────────┐
│Azure SQL │  │ Blob       │
│Database  │  │ Storage    │
└──────────┘  └────────────┘
    │             │
    ▼             ▼
┌──────────────────────────┐
│  AKS (Kubernetes)        │
│  - Analysis Pods (CPU)   │
│  - Generation Pods (GPU) │
└──────────────────────────┘
```

---

## ⚙️ Configuration Strategy

### Environment Detection

```csharp
public class AppSettings
{
    public string Environment { get; set; } // "Local" or "Azure"
    
    public bool IsLocal => Environment == "Local";
    public bool IsAzure => Environment == "Azure";
}
```

### Connection Strings

| Environment | Database | Storage |
|------------|----------|---------|
| **Local** | PostgreSQL (Docker) | Azurite (localhost:10000) |
| **Azure** | Azure SQL Database | Azure Blob Storage (Managed Identity) |

### Worker URLs

| Environment | Analysis Worker | Generation Worker |
|------------|-----------------|-------------------|
| **Local** | http://localhost:8001 | http://localhost:8002 |
| **Azure** | http://analysis-worker.music-platform.svc.cluster.local:8080 | http://generation-worker.music-platform.svc.cluster.local:8080 |

### Orchestration

| Environment | Type | Storage |
|------------|------|---------|
| **Local** | In-Memory Queue | None (memory-based) |
| **Azure** | Durable Functions | Azure Storage Tables |

---

## 🔐 Authentication

### Local Development
```json
{
  "Authentication": {
    "Enabled": false
  }
}
```
**No auth required** - faster iteration

### Azure Production
```json
{
  "Authentication": {
    "Enabled": true,
    "AzureAd": {
      "Instance": "https://login.microsoftonline.com/",
      "TenantId": "{your-tenant-id}",
      "ClientId": "{your-client-id}"
    }
  }
}
```
**Azure AD authentication** - secure production access

---

## 📦 Component Abstraction

### Storage Service

```csharp
public interface IStorageService
{
    Task<string> UploadAudioAsync(Stream audioStream, string fileName);
    Task<Stream> DownloadAudioAsync(string blobUri);
}

// Implementation switches based on configuration
public class StorageService : IStorageService
{
    public StorageService(IConfiguration config)
    {
        if (config["BlobStorage:UseManagedIdentity"] == "true")
        {
            // Azure: Managed Identity
            _client = new BlobServiceClient(
                new Uri($"https://{config["BlobStorage:AccountName"]}.blob.core.windows.net"),
                new DefaultAzureCredential());
        }
        else
        {
            // Local: Connection string
            _client = new BlobServiceClient(config["BlobStorage:ConnectionString"]);
        }
    }
}
```

### Database Context

```csharp
public class MusicPlatformDbContext : DbContext
{
    protected override void OnConfiguring(DbContextOptionsBuilder options)
    {
        var connectionString = _configuration.GetConnectionString("DefaultConnection");
        
        if (connectionString.Contains("Host="))
        {
            // PostgreSQL (local)
            options.UseNpgsql(connectionString);
        }
        else
        {
            // SQL Server (Azure)
            options.UseSqlServer(connectionString);
        }
    }
}
```

### Orchestration Service

```csharp
public interface IOrchestrationService
{
    Task<string> StartAnalysisAsync(Guid audioFileId);
    Task<JobStatus> GetStatusAsync(string jobId);
}

// Local: Simple in-memory queue
public class InMemoryOrchestrationService : IOrchestrationService
{
    private readonly ConcurrentDictionary<string, JobStatus> _jobs = new();
    // ...
}

// Azure: Durable Functions client
public class DurableFunctionsOrchestrationService : IOrchestrationService
{
    private readonly IDurableClient _client;
    // ...
}
```

---

## 🐳 Docker Images

### Same Dockerfile, Different Deployment

**Analysis Worker Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Runs in:**
- ✅ Docker Compose (local)
- ✅ Azure Kubernetes Service (cloud)

No code changes needed!

---

## 📱 MAUI Frontend

### Configuration

```csharp
public class ApiSettings
{
    public string BaseUrl { get; set; }
    
    // Set at runtime based on environment
    public static string GetApiUrl()
    {
#if DEBUG
        return "http://localhost:5000"; // Local development
#else
        return "https://music-api.azurewebsites.net"; // Azure production
#endif
    }
}
```

### API Client

```csharp
public class MusicApiClient
{
    private readonly HttpClient _httpClient;
    
    public MusicApiClient()
    {
        _httpClient = new HttpClient
        {
            BaseAddress = new Uri(ApiSettings.GetApiUrl())
        };
    }
    
    public async Task<AudioFile> UploadAudioAsync(Stream audio, string fileName)
    {
        var content = new MultipartFormDataContent();
        content.Add(new StreamContent(audio), "file", fileName);
        
        var response = await _httpClient.PostAsync("/api/audio", content);
        return await response.Content.ReadFromJsonAsync<AudioFile>();
    }
}
```

**Same code works for both local and Azure!**

---

## 🚀 Deployment

### Local Development

```powershell
# Start everything
docker-compose up -d

# MAUI app automatically connects to localhost:5000
```

### Azure Deployment

```powershell
# Deploy infrastructure
az deployment group create --template-file infrastructure/main.bicep

# Push Docker images to ACR
docker tag music-analysis-worker myacr.azurecr.io/analysis-worker:v1
docker push myacr.azurecr.io/analysis-worker:v1

# Deploy to AKS
kubectl apply -f k8s/

# Publish API to App Service
dotnet publish -c Release
az webapp deployment source config-zip --src api.zip

# MAUI app automatically connects to Azure URL
```

---

## 🧪 Testing

### Unit Tests
```csharp
// Use in-memory database for both local and CI
services.AddDbContext<MusicPlatformDbContext>(options =>
    options.UseInMemoryDatabase("TestDb"));
```

### Integration Tests
```csharp
// Mock external services
services.AddTransient<IWorkerClient, MockWorkerClient>();
```

### End-to-End Tests
```csharp
// Can run against local Docker or Azure
var apiUrl = Environment.GetEnvironmentVariable("TEST_API_URL") 
             ?? "http://localhost:5000";
```

---

## 📊 Monitoring

### Local Development
- Console logs
- Docker logs: `docker-compose logs -f`
- PgAdmin for database inspection

### Azure Production
- Application Insights
- Azure Monitor
- Log Analytics
- Custom dashboards

---

## ✅ Benefits

### Single Codebase
- ✅ No environment-specific branches
- ✅ Same bugs in dev and prod
- ✅ Easy to test locally before deploying

### Configuration-Driven
- ✅ Change behavior without code changes
- ✅ Environment variables in production
- ✅ appsettings.json in development

### Cost-Effective
- ✅ Free local development (Docker Desktop)
- ✅ Only pay for Azure when needed
- ✅ Easy to scale up/down

### Developer Experience
- ✅ Fast local iteration
- ✅ Test full pipeline locally
- ✅ Deploy with confidence

---

## 🔄 Migration Path

### Start Local (Week 1-8)
1. Build features in Docker
2. Test with MAUI app
3. Use PostgreSQL and Azurite
4. No cloud costs

### Deploy to Azure (Week 9+)
1. Change configuration only
2. Deploy infrastructure with Bicep
3. Push Docker images to ACR
4. Update MAUI app URL

### Hybrid (Ongoing)
1. Develop locally
2. Test in staging (Azure)
3. Deploy to production (Azure)

---

## 📁 Project Structure

```
DirectAI/
├── src/
│   ├── MusicPlatform.Api/              # .NET API (works everywhere)
│   ├── MusicPlatform.Domain/           # Shared domain models
│   ├── MusicPlatform.Infrastructure/   # Storage, DB, abstractions
│   └── MusicPlatform.Maui/             # Cross-platform frontend
├── workers/
│   ├── analysis/                       # Python worker (Docker)
│   └── generation/                     # Python worker (Docker)
├── database/
│   └── schema.sql                      # Works for PostgreSQL & SQL Server
├── infrastructure/
│   └── main.bicep                      # Azure deployment
├── docker-compose.yml                  # Local orchestration
└── appsettings.*.json                  # Environment configs
```

---

## 🎯 Summary

**One Codebase, Multiple Environments**

- Same .NET API → App Service or Docker
- Same Python workers → Docker Compose or AKS
- Same MAUI app → Any device
- Different configs → Connection strings, URLs, auth

**Benefits:**
- Faster development
- Lower maintenance
- Fewer bugs
- Easy deployment

**This is production-ready architecture done right.** 🚀
