# AKS GPU Deployment - Quick Reference

## Quick Start

Deploy everything with one command:

```powershell
.\scripts\deploy-aks.ps1 -ResourceGroup "music-platform-rg" -Environment "dev"
```

## Common Commands

### Deployment

```powershell
# Build and push images only
.\scripts\build-workers.ps1 -AcrName "musicdevacr"

# Update running workers
.\scripts\update-workers.ps1 -ResourceGroup "music-platform-rg" -AksName "music-dev-aks" -AcrName "musicdevacr"

# Deploy infrastructure only
az deployment group create --resource-group music-platform-rg --template-file infrastructure/main.bicep --parameters environment=dev
```

### Monitoring

```powershell
# Pod status
kubectl get pods -n music-platform -w

# Logs (follow)
kubectl logs -n music-platform -l app=analysis-worker -f

# GPU usage
kubectl describe nodes -l accelerator=nvidia | Select-String "nvidia.com/gpu"

# Resource usage
kubectl top nodes
kubectl top pods -n music-platform
```

### Scaling

```powershell
# Scale pods manually
kubectl scale deployment analysis-worker --replicas=5 -n music-platform

# Scale node pool
az aks nodepool scale --resource-group music-platform-rg --cluster-name music-dev-aks --name gpupool --node-count 3

# Check HPA
kubectl get hpa -n music-platform
```

### Troubleshooting

```powershell
# Describe pod (shows events and errors)
kubectl describe pod -n music-platform <pod-name>

# View previous crashed container logs
kubectl logs -n music-platform <pod-name> --previous

# Execute into running pod
kubectl exec -it -n music-platform <pod-name> -- /bin/bash

# Check events
kubectl get events -n music-platform --sort-by='.lastTimestamp'

# Restart deployment
kubectl rollout restart deployment/analysis-worker -n music-platform
```

### Testing

```powershell
# Port forward to test locally
kubectl port-forward -n music-platform svc/analysis-worker 8001:8080
kubectl port-forward -n music-platform svc/generation-worker 8002:8080

# Test health endpoint
curl http://localhost:8001/health
curl http://localhost:8002/health
```

## File Structure

```
DirectAI/
├── infrastructure/
│   ├── main.bicep                          # Azure infrastructure
│   └── kubernetes/
│       ├── namespace.yaml                  # K8s namespace, PVC, GPU plugin
│       ├── analysis-worker.yaml            # Analysis worker deployment
│       └── generation-worker.yaml          # Generation worker deployment
├── workers/
│   ├── analysis/
│   │   ├── Dockerfile                      # CPU version
│   │   └── Dockerfile.gpu                  # GPU version (NEW)
│   └── generation/
│       ├── Dockerfile                      # CPU version
│       └── Dockerfile.gpu                  # GPU version (NEW)
└── scripts/
    ├── deploy-aks.ps1                      # Full deployment script
    ├── build-workers.ps1                   # Build and push images
    └── update-workers.ps1                  # Update existing deployments
```

## Resource Sizes

| Component | CPU | Memory | GPU |
|-----------|-----|--------|-----|
| Analysis Worker | 4-8 cores | 8-16 GB | 1x T4 |
| Generation Worker | 4-8 cores | 8-16 GB | 1x T4 |
| GPU Node (NC4as_T4_v3) | 4 cores | 28 GB | 1x T4 |

## Environment Variables

### Analysis Worker
- `AZURE_STORAGE_CONNECTION_STRING` - Azure Storage connection
- `BLOB_CONTAINER_NAME` - Container name (default: "audio-files")
- `DEMUCS_MODEL` - Demucs model (default: "htdemucs")
- `API_BASE_URL` - API endpoint
- `CUDA_VISIBLE_DEVICES` - GPU device ID

### Generation Worker
- `AZURE_STORAGE_CONNECTION_STRING` - Azure Storage connection
- `BLOB_CONTAINER_NAME` - Container name (default: "audio-files")
- `USE_GPU` - Enable GPU (default: "true")
- `CUDA_VISIBLE_DEVICES` - GPU device ID

## GPU Costs (East US)

| VM Size | GPU | Price/hour* | Dev (0-2 nodes) | Prod (1-5 nodes) |
|---------|-----|-------------|-----------------|------------------|
| NC4as_T4_v3 | T4 | $0.526 | $0-1,052/mo | $379-1,896/mo |

*With auto-scaling and proper workload distribution

## Key Features

✅ GPU acceleration for Demucs, MusicGen, Bark  
✅ Auto-scaling (HPA + cluster autoscaler)  
✅ Zero-downtime deployments  
✅ Health checks and self-healing  
✅ Persistent model caching  
✅ Azure Monitor integration  
✅ Cost-optimized T4 GPUs  

## Production Checklist

- [ ] Enable Azure Monitor Container Insights
- [ ] Set up log aggregation
- [ ] Configure alert rules
- [ ] Enable network policies
- [ ] Use Azure Key Vault for secrets
- [ ] Set up backup strategy
- [ ] Configure pod disruption budgets
- [ ] Enable Azure Policy
- [ ] Review GPU quota limits
- [ ] Set up CI/CD pipeline

## Support

For detailed documentation, see:
- [AKS_GPU_DEPLOYMENT.md](./AKS_GPU_DEPLOYMENT.md) - Full deployment guide
- [ARCHITECTURE_VISUAL.md](./ARCHITECTURE_VISUAL.md) - System architecture
- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - General deployment guide
