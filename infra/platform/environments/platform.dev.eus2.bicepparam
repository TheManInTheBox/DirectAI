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
param postgresAdminLogin = 'directaiadmin'
param postgresAdminPassword = readEnvironmentVariable('POSTGRES_ADMIN_PASSWORD', 'ChangeMeInCI!')
param postgresSkuName = 'Standard_B1ms'
param postgresTier = 'Burstable'
param postgresStorageGB = 32
param kubernetesVersion = '1.33'
param tags = {
  costCenter: 'platform'
}
