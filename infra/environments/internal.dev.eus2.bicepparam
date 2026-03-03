// DirectAI Stamp — Dev Environment (East US 2)
using '../main.bicep'

param customerId = 'internal'
param regionShort = 'eus2'
param environment = 'dev'
param kubernetesVersion = '1.30'
param enableGpuPools = false // No GPU quota needed for dev
param enablePrivateEndpoints = false // Simplifies dev iteration; enable for security testing
param systemPoolMinCount = 1
param systemPoolMaxCount = 3
param platformAcrLoginServer = '' // Deploy per-customer ACR for dev
param vnetAddressPrefix = '10.0.0.0/16'
param aksSubnetPrefix = '10.0.0.0/22'
param endpointsSubnetPrefix = '10.0.4.0/24'
param tags = {
  costCenter: 'engineering'
}
