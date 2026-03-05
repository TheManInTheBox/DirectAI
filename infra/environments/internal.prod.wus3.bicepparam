// DirectAI Stamp — Production Environment (West US 3)
// Subscription: 0ae2be9a-f470-4dfe-b2e0-b7e9726acdfb
// GPU: ND96asr_v4 (8× A100 80GB, NVLink, 3.8TB NVMe)
// Purpose: Production inference — multi-model, multi-GPU, latency-based routing via Front Door
using '../main.bicep'

param customerId = 'internal'
param regionShort = 'wus3'
param environment = 'prod'
param kubernetesVersion = '1.33'

// GPU pools — disabled until ND A100 v4 quota (192 vCPU) approved in WUS3.
// Once approved: set enableGpuPools = true. gpuPoolTier = 'production' deploys
// A100 + H100 + embeddings pools. Only A100 pool will scale initially.
param enableGpuPools = false
param gpuPoolTier = 'production'

// Private endpoints disabled for initial deployment — enable once networking is validated.
param enablePrivateEndpoints = false

// System pool — 3-node minimum for zone-redundant HA
param systemPoolMinCount = 3
param systemPoolMaxCount = 5

// Platform ACR in operations subscription (b03c9eb4-cddc-4987-9673-9ac44b9cc1d9).
param platformAcrLoginServer = 'acrplatformdaiv7fgid.azurecr.io'

// VNet — unique CIDR per region within the subscription.
// Dev SCUS: 10.1.0.0/16 | Prod SCUS: 10.2.0.0/16 | Prod EUS2: 10.3.0.0/16 | Prod WUS3: 10.4.0.0/16
param vnetAddressPrefix = '10.4.0.0/16'
param aksSubnetPrefix = '10.4.0.0/22'
param endpointsSubnetPrefix = '10.4.4.0/24'

param tags = {
  costCenter: 'engineering'
  sla: '99.99'
  gpuSku: 'ND96asr_v4'
  tier: 'production'
}
