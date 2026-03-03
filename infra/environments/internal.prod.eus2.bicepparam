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
param platformAcrLoginServer = '' // Deploy per-customer ACR for now; will switch to platform ACR
param vnetAddressPrefix = '10.0.0.0/16'
param aksSubnetPrefix = '10.0.0.0/22'
param endpointsSubnetPrefix = '10.0.4.0/24'
param tags = {
  costCenter: 'engineering'
  sla: '99.99'
}
