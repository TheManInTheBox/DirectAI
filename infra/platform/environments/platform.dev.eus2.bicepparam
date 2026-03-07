// DirectAI Platform — Dev (East US 2)
// Operations subscription: b03c9eb4-cddc-4987-9673-9ac44b9cc1d9
using '../main.bicep'

param regionShort = 'eus2'
param environment = 'dev'
param acrSku = 'Basic' // Dev doesn't need Premium features
param enablePrivateEndpoints = false
param enableDnsZone = true
param dnsZoneName = 'agilecloud.ai'
param platformWebIngressIp = '4.153.165.222'    // Platform AKS NGINX LB (agilecloud.ai)
param devApiIngressIp = '48.192.177.54'         // Dev AKS NGINX LB (api.agilecloud.ai)
param dataRetention = 30
param enablePlatformAks = true
param enablePlatformDb = true
param enableContentSafety = true
param contentSafetySku = 'F0'
param enableAuditStorage = true
param auditRetentionDays = 365
param postgresAdminLogin = 'directaiadmin'
param postgresAdminPassword = readEnvironmentVariable('POSTGRES_ADMIN_PASSWORD', 'ChangeMeInCI!')
param postgresSkuName = 'Standard_B1ms'
param postgresTier = 'Burstable'
param postgresStorageGB = 32
param kubernetesVersion = '1.33'
param tags = {
  costCenter: 'platform'
}

// --- Front Door Premium ---
// Disabled until prod AKS clusters are deployed and have NGINX LB IPs.
// Once prod clusters are online:
//   1. Delete the api.agilecloud.ai A record: az network dns record-set a delete -g rg-dai-platform-dev-eus2 -z agilecloud.ai -n api --yes
//   2. Set enableFrontDoor = true
//   3. Add prod AKS IPs to inferenceApiOrigins
//   4. Redeploy
param enableFrontDoor = false
param inferenceApiOrigins = [
  // { region: 'scus', hostname: '48.192.177.54' }     // Dev SCUS AKS (current)
  // { region: 'scus', hostname: '<prod-scus-ip>' }    // Prod SCUS AKS
  // { region: 'eus2', hostname: '<prod-eus2-ip>' }    // Prod EUS2 AKS
  // { region: 'wus3', hostname: '<prod-wus3-ip>' }    // Prod WUS3 AKS
]
