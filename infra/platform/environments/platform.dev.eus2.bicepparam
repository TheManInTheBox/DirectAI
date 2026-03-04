// DirectAI Platform — Dev (East US 2)
// Operations subscription: b03c9eb4-cddc-4987-9673-9ac44b9cc1d9
using '../main.bicep'

param regionShort = 'eus2'
param environment = 'dev'
param acrSku = 'Basic' // Dev doesn't need Premium features
param enablePrivateEndpoints = false
param enableDnsZone = true
param dnsZoneName = 'agilecloud.ai'
param dataRetention = 30
param enablePlatformAks = true
param kubernetesVersion = '1.30'
param tags = {
  costCenter: 'platform'
}
