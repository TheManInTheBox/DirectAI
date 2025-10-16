# Local Development Setup
## Music Analysis & Generation Platform

This guide helps you run the entire platform locally using Docker Desktop.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with WSL2 on Windows)
- [.NET 8.0 SDK](https://dotnet.microsoft.com/download/dotnet/8.0)
- [Python 3.11+](https://www.python.org/downloads/)
- 8GB RAM minimum (16GB recommended)

## Quick Start

### 1. Start All Services

```powershell
# From project root
docker-compose up -d
```

This starts:
- PostgreSQL database (port 5432)
- Azurite storage emulator (ports 10000-10002)
- .NET Web API (port 5000)
- Analysis Worker (port 8001)
- Generation Worker (port 8002)
- PgAdmin (port 5050)

### 2. Verify Services

```powershell
# Check all containers are running
docker-compose ps

# Check API health
curl http://localhost:5000/health

# Check Analysis Worker
curl http://localhost:8001/health

# Check Generation Worker
curl http://localhost:8002/health
```

### 3. Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Web API** | http://localhost:5000 | - |
| **API Docs** | http://localhost:5000/swagger | - |
| **PgAdmin** | http://localhost:5050 | admin@music.local / admin |
| **Analysis Worker** | http://localhost:8001 | - |
| **Generation Worker** | http://localhost:8002 | - |

## Development Workflow

### Building the API

```powershell
cd src\MusicPlatform.Api
dotnet build
dotnet run
```

### Building Workers

```powershell
# Analysis Worker
cd workers\analysis
python -m pip install -r requirements.txt
python app.py

# Generation Worker
cd workers\generation
python -m pip install -r requirements.txt
python app.py
```

### Database Management

**Using PgAdmin:**
1. Open http://localhost:5050
2. Login with admin@music.local / admin
3. Add server:
   - Host: db
   - Port: 5432
   - Database: musicplatform
   - Username: postgres
   - Password: DevPassword123!

**Using psql:**
```powershell
docker exec -it music-db psql -U postgres -d musicplatform
```

### View Logs

```powershell
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f analysis-worker
```

## Testing the Pipeline

### 1. Upload Audio File

```powershell
curl -X POST http://localhost:5000/api/audio `
  -F "file=@test-audio.mp3" `
  -H "Content-Type: multipart/form-data"
```

Response:
```json
{
  "audioFileId": "123e4567-e89b-12d3-a456-426614174000",
  "status": "Uploaded",
  "jobId": "job-123"
}
```

### 2. Check Job Status

```powershell
curl http://localhost:5000/api/jobs/job-123
```

### 3. Get Analysis Results

```powershell
curl http://localhost:5000/api/audio/123e4567-e89b-12d3-a456-426614174000/analysis
```

### 4. Request Generation

```powershell
curl -X POST http://localhost:5000/api/generation `
  -H "Content-Type: application/json" `
  -d '{
    "audioFileId": "123e4567-e89b-12d3-a456-426614174000",
    "targetStems": ["vocals", "drums"],
    "parameters": {
      "durationSeconds": 10.0,
      "style": "rock"
    }
  }'
```

## Storage Structure

Azurite (local blob storage) uses these containers:

```
devstoreaccount1/
├── raw-audio/          # Uploaded MP3 files
├── stems/              # Separated audio stems
├── generated/          # AI-generated audio
└── jams/              # JAMS annotation files
```

**Access with Azure Storage Explorer:**
- Connection string: `DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;`

## Troubleshooting

### Services won't start

```powershell
# Clean up and rebuild
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Database connection issues

```powershell
# Check database is healthy
docker exec -it music-db pg_isready -U postgres

# Manually run schema
docker exec -i music-db psql -U postgres -d musicplatform < database/schema.sql
```

### Port conflicts

If ports are in use, edit `docker-compose.yml`:
```yaml
ports:
  - "5001:8080"  # Change 5000 to 5001
```

## Stopping Services

```powershell
# Stop all services
docker-compose down

# Stop and remove volumes (data loss!)
docker-compose down -v
```

## Next Steps

1. Build the Web API project
2. Implement analysis worker logic
3. Create generation worker
4. Add web UI for easier testing

## Architecture

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────────────────────────────┐
│      .NET Web API (port 5000)       │
│  • Audio upload                     │
│  • Metadata query                   │
│  • Job management                   │
└──┬─────────────────────────────┬────┘
   │                             │
   │                             │
   ▼                             ▼
┌──────────────┐        ┌───────────────┐
│  PostgreSQL  │        │   Azurite     │
│  (port 5432) │        │  (port 10000) │
│              │        │               │
│  • Metadata  │        │  • Audio      │
│  • Jobs      │        │  • Stems      │
└──────────────┘        └───────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                           │
        ▼                                           ▼
┌─────────────────┐                     ┌─────────────────┐
│ Analysis Worker │                     │Generation Worker│
│  (port 8001)    │                     │  (port 8002)    │
│                 │                     │                 │
│  • Demucs       │                     │  • Stable Audio │
│  • Essentia     │                     │  • MusicGen     │
│  • madmom       │                     │                 │
└─────────────────┘                     └─────────────────┘
```

## Development Tips

- Use `docker-compose up` (without `-d`) to see logs in real-time
- Changes to Python code are auto-reloaded (volume mounted)
- .NET API requires rebuild: `docker-compose build api && docker-compose up -d api`
- Use PgAdmin to inspect database tables
- Check Azurite with Azure Storage Explorer

---

**Happy Coding!** 🎵🚀
