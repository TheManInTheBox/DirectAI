// DirectAI Platform — Prod (East US 2)
// Operations subscription: b03c9eb4-cddc-4987-9673-9ac44b9cc1d9
using '../main.bicep'

param regionShort = 'eus2'
param environment = 'prod'
param acrSku = 'Premium' // Geo-replication, private endpoints, content trust
param enablePrivateEndpoints = true
param enableDnsZone = true
param dnsZoneName = 'agilecloud.ai'
// Prod IPs: set after NGINX Ingress Controller is deployed
param platformWebIngressIp = ''  // TODO: set after prod AKS deploy
param devApiIngressIp = ''       // Prod API will have its own IP
param dataRetention = 90
param enablePlatformAks = true
param kubernetesVersion = '1.33'
param tags = {
  costCenter: 'platform'
  sla: '99.99'
}
