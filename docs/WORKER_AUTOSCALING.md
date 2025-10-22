# Worker Autoscaling Guide

This guide explains how worker autoscaling works in both local Docker Compose and Azure Kubernetes Service (AKS) environments.

## Overview

The music platform automatically scales workers based on job queue depth and resource utilization to ensure optimal performance and cost efficiency.

## Local Development (Docker Compose)

### How It Works

The `WorkerAutoscalerService` monitors the job queue and automatically scales Docker containers:

1. **Monitoring**: Checks job queue every 10 seconds
2. **Scale Up**: When pending/running jobs ≥ threshold
3. **Scale Down**: When pending/running jobs ≤ threshold  
4. **Cooldown**: Waits 60 seconds between scale actions

### Configuration

Edit `appsettings.Development.json`:

```json
{
  "Autoscaling": {
    "Enabled": true,
    "MinWorkers": 1,
    "MaxWorkers": 5,
    "ScaleUpThreshold": 3,
    "ScaleDownThreshold": 1,
    "CooldownSeconds": 60
  }
}
```

**Parameters**:
- **Enabled**: Enable/disable autoscaling
- **MinWorkers**: Minimum worker instances (always running)
- **MaxWorkers**: Maximum worker instances (hard limit)
- **ScaleUpThreshold**: Jobs needed to trigger scale up
- **ScaleDownThreshold**: Jobs needed to trigger scale down
- **CooldownSeconds**: Wait time between scaling actions

### Manual Scaling

Scale workers manually with docker-compose:

```powershell
# Scale analysis workers to 3 instances
docker-compose up -d --scale analysis-worker=3 --no-recreate

# Scale generation workers to 2 instances
docker-compose up -d --scale generation-worker=2 --no-recreate

# Scale both
docker-compose up -d --scale analysis-worker=3 --scale generation-worker=2 --no-recreate
```

### Verify Scaling

```powershell
# Check running containers
docker ps | Select-String "worker"

# Expected output:
# directai-analysis-worker-1    # First instance (port 8001)
# directai-analysis-worker-2    # Second instance (port 8002)
# directai-analysis-worker-3    # Third instance (port 8003)
```

### Port Mapping

Workers are assigned ports dynamically:
- Analysis workers: 8001-8005
- Generation workers: 8002-8006

### Monitoring

View autoscaling metrics:

```powershell
# API endpoint
curl http://localhost:5000/api/metrics/autoscaling

# Response
{
  "autoscaling": {
    "enabled": true,
    "minWorkers": 1,
    "maxWorkers": 5,
    "scaleUpThreshold": 3,
    "scaleDownThreshold": 1,
    "status": "active"
  },
  "analysis": {
    "queue": {
      "pending": 5,
      "running": 2,
      "total": 7
    },
    "metrics": {
      "utilizationPercent": 40,
      "shouldScaleUp": true,
      "shouldScaleDown": false
    }
  }
}
```

### Logs

Check autoscaler logs:

```powershell
# Docker logs
docker logs music-api 2>&1 | Select-String "Autoscal"

# Example output:
# Worker autoscaler enabled: Min=1, Max=5, ScaleUpThreshold=3, ScaleDownThreshold=1
# Scaling UP analysis workers: 1 -> 3 (load: 7)
# Successfully scaled analysis workers to 3
```

## Azure Kubernetes Service (AKS)

### How It Works

Kubernetes Horizontal Pod Autoscaler (HPA) automatically scales pods based on:

1. **CPU Utilization**: Scales when average CPU > 60%
2. **Memory Utilization**: Scales when average memory > 70%
3. **Custom Metrics**: Can add queue depth metrics

### Configuration

The HPA is configured in `infrastructure/kubernetes/*-worker.yaml`:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: analysis-worker
spec:
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        averageUtilization: 60
  - type: Resource
    resource:
      name: memory
      target:
        averageUtilization: 70
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
```

**Key Features**:
- **Scale up immediately** when load increases
- **Wait 5 minutes** before scaling down (prevent flapping)
- **Double pods** on scale up (100% increase)
- **Remove 50%** on scale down (gradual)

### Verify HPA

```powershell
# Check HPA status
kubectl get hpa -n music-platform

# Expected output:
NAME                  REFERENCE                       TARGETS           MINPODS   MAXPODS   REPLICAS
analysis-worker       Deployment/analysis-worker      30%/60%, 45%/70%  1         10        3
generation-worker     Deployment/generation-worker    25%/60%, 40%/70%  1         10        2

# Describe HPA for details
kubectl describe hpa analysis-worker -n music-platform

# Watch HPA in real-time
kubectl get hpa -n music-platform --watch
```

### Manual Scaling (AKS)

Override HPA temporarily:

```powershell
# Scale to specific number
kubectl scale deployment analysis-worker --replicas=5 -n music-platform

# HPA will resume control after next evaluation
```

### Monitoring (AKS)

```powershell
# Pod status
kubectl get pods -n music-platform -l app=analysis-worker

# Resource usage
kubectl top pods -n music-platform -l app=analysis-worker

# Node usage
kubectl top nodes -l accelerator=nvidia
```

## Scaling Strategies

### Conservative (Production)

For stable, predictable workloads:

```json
{
  "Autoscaling": {
    "MinWorkers": 2,
    "MaxWorkers": 5,
    "ScaleUpThreshold": 5,
    "ScaleDownThreshold": 2,
    "CooldownSeconds": 120
  }
}
```

**Characteristics**:
- Higher minimums (always ready)
- Higher thresholds (scale less frequently)
- Longer cooldown (more stable)

### Aggressive (Dev/Testing)

For bursty workloads with cost optimization:

```json
{
  "Autoscaling": {
    "MinWorkers": 1,
    "MaxWorkers": 10,
    "ScaleUpThreshold": 2,
    "ScaleDownThreshold": 1,
    "CooldownSeconds": 30
  }
}
```

**Characteristics**:
- Lower minimums (save cost when idle)
- Lower thresholds (scale quickly)
- Shorter cooldown (responsive)

### Cost-Optimized

Minimize costs while handling load:

```json
{
  "Autoscaling": {
    "MinWorkers": 0,  # Scale to zero when idle (AKS only with KEDA)
    "MaxWorkers": 3,
    "ScaleUpThreshold": 1,
    "ScaleDownThreshold": 0,
    "CooldownSeconds": 180
  }
}
```

## Troubleshooting

### Workers Not Scaling

**Issue**: Autoscaler not creating new workers

**Checks**:

```powershell
# 1. Verify autoscaling is enabled
curl http://localhost:5000/api/metrics/autoscaling | ConvertFrom-Json | Select-Object -ExpandProperty autoscaling

# 2. Check API logs
docker logs music-api --tail 100 | Select-String "autoscal"

# 3. Verify Docker is accessible
docker version

# 4. Check queue depth
curl http://localhost:5000/api/metrics/autoscaling | ConvertFrom-Json | Select-Object -ExpandProperty analysis
```

**Solutions**:
- Set `Autoscaling:Enabled = true`
- Ensure Docker Desktop is running
- Check cooldown period hasn't been exceeded
- Verify queue depth exceeds threshold

### Pods Stuck in Pending (AKS)

**Issue**: Pods created but not starting

```powershell
kubectl describe pod -n music-platform <pod-name>
```

**Common Causes**:
- Insufficient GPU nodes
- Resource limits too high
- Image pull errors

**Solutions**:

```powershell
# Scale GPU node pool
az aks nodepool scale --resource-group music-platform-rg --cluster-name music-dev-aks --name gpupool --node-count 3

# Check node resources
kubectl describe nodes -l accelerator=nvidia
```

### Excessive Scaling (Flapping)

**Issue**: Workers scaling up and down rapidly

**Solutions**:
- Increase cooldown period
- Adjust thresholds (wider gap)
- Add stabilization window (AKS)

```json
{
  "CooldownSeconds": 180,  // Increase from 60
  "ScaleUpThreshold": 5,
  "ScaleDownThreshold": 1   // Wider gap
}
```

### High Memory Usage

**Issue**: Workers consuming too much memory

**Check**:

```powershell
# Docker
docker stats

# AKS
kubectl top pods -n music-platform
```

**Solutions**:
- Reduce `MaxConcurrentJobs` in orchestration
- Increase memory limits in deployment
- Add more workers to distribute load

## Best Practices

### 1. Set Appropriate Limits

```yaml
# Kubernetes resources
resources:
  requests:
    memory: "8Gi"
    cpu: "4"
    nvidia.com/gpu: 1
  limits:
    memory: "16Gi"  # 2x requests
    cpu: "8"
    nvidia.com/gpu: 1
```

### 2. Monitor Queue Depth

```powershell
# Set up alerts for high queue depth
# Azure Monitor, Prometheus, or custom alerts
```

### 3. Test Scaling

```powershell
# Generate load to test autoscaling
# Upload multiple files simultaneously
for ($i=1; $i -le 10; $i++) {
    Start-Job -ScriptBlock {
        curl -F "file=@test.mp3" http://localhost:5000/api/audio/upload
    }
}

# Watch scaling in action
docker ps --format "table {{.Names}}\t{{.Status}}" | Select-String "worker"
```

### 4. Optimize Cooldown

Balance responsiveness vs stability:
- **Short cooldown (30-60s)**: Responsive but may flap
- **Long cooldown (120-300s)**: Stable but slower to react

### 5. Right-Size Workers

Start with moderate limits and adjust:
- Monitor actual resource usage
- Set requests = average usage
- Set limits = peak usage

## Metrics to Monitor

### Key Indicators

1. **Queue Depth**: Jobs waiting to be processed
2. **Processing Time**: Average job duration
3. **Worker Utilization**: % of workers actively processing
4. **Scale Events**: Frequency of scale up/down
5. **Error Rate**: Failed jobs due to resource issues

### Dashboards

Create dashboards tracking:
- Real-time queue depth
- Worker count over time
- Job throughput (jobs/hour)
- Resource utilization (CPU/memory/GPU)
- Cost per job

## Cost Optimization

### Docker Compose (Local)

- Set `MinWorkers: 1` to minimize resource usage
- Use aggressive scale-down for dev work
- Stop unused workers: `docker-compose stop analysis-worker`

### AKS (Cloud)

- Enable cluster autoscaler to scale nodes
- Use spot instances for batch workloads (70-90% savings)
- Scale GPU node pool to 0 when idle (dev only)
- Set pod disruption budgets for graceful shutdowns

```powershell
# Scale GPU node pool to 0 (dev only)
az aks nodepool scale --resource-group music-platform-rg --cluster-name music-dev-aks --name gpupool --node-count 0

# Re-enable autoscaling
az aks nodepool update --resource-group music-platform-rg --cluster-name music-dev-aks --name gpupool --enable-cluster-autoscaler --min-count 0 --max-count 5
```

## Additional Resources

- [Docker Compose Scaling](https://docs.docker.com/compose/reference/up/)
- [Kubernetes HPA](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [AKS Autoscaling](https://learn.microsoft.com/en-us/azure/aks/concepts-scale)
- [GPU Autoscaling Best Practices](https://learn.microsoft.com/en-us/azure/aks/gpu-cluster)
