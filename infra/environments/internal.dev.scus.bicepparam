// DirectAI Stamp — Dev Environment (South Central US)
// Subscription: 0ae2be9a-f470-4dfe-b2e0-b7e9726acdfb
using '../main.bicep'

param customerId = 'internal'
param regionShort = 'scus'
param environment = 'dev'
param kubernetesVersion = '1.30'
param enableGpuPools = true
param gpuPoolTier = 'dev' // Single T4 pool for all workloads
param devGpuVmSize = 'Standard_NC16as_T4_v3' // 1× T4 16GB, 16 vCPUs, 112 GB RAM
param devGpuMaxCount = 2
param enablePrivateEndpoints = false // Simplifies dev iteration; enable for security testing
param systemPoolMinCount = 1
param systemPoolMaxCount = 3
// Platform ACR in operations subscription (b03c9eb4-cddc-4987-9673-9ac44b9cc1d9).
// Value is the output of: az deployment group show -g rg-dai-platform-dev-eus2 -n acr --query properties.outputs.acrLoginServer.value
// Leave empty to deploy a per-stamp ACR instead.
param platformAcrLoginServer = 'acrplatformdaiv7fgid.azurecr.io'
param vnetAddressPrefix = '10.1.0.0/16'
param aksSubnetPrefix = '10.1.0.0/22'
param endpointsSubnetPrefix = '10.1.4.0/24'
param tags = {
  costCenter: 'engineering'
}
