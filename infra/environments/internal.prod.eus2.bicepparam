// DirectAI Stamp — Prod Environment (East US 2)
using '../main.bicep'

param customerId = 'internal'
param regionShort = 'eus2'
param environment = 'prod'
param kubernetesVersion = '1.30'
param enableGpuPools = true // Full GPU node pools
param enablePrivateEndpoints = true // Production security baseline — all PaaS behind PEs
param systemPoolMinCount = 3
param systemPoolMaxCount = 5
// Platform ACR in operations subscription (b03c9eb4-cddc-4987-9673-9ac44b9cc1d9).
// Value is the output of: az deployment group show -g rg-dai-platform-prod-eus2 -n acr --query properties.outputs.acrLoginServer.value
// Leave empty to deploy a per-stamp ACR instead.
param platformAcrLoginServer = '' // TODO: set after first deploy-platform run
param vnetAddressPrefix = '10.0.0.0/16'
param aksSubnetPrefix = '10.0.0.0/22'
param endpointsSubnetPrefix = '10.0.4.0/24'
param tags = {
  costCenter: 'engineering'
  sla: '99.99'
}
