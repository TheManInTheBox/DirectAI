// ============================================================================
// DirectAI Platform Infrastructure — Centralized Services
//
// Deploys shared resources to the Operations subscription that are consumed
// by ALL customer stamps across all subscriptions:
//
//   - Container Registry (ACR)  — inference images (DirectAI IP)
//   - Storage Account           — pre-compiled engine cache
//   - Log Analytics Workspace   — centralized monitoring sink
//   - Application Insights      — distributed tracing + live metrics
//
// This template is deployed ONCE per region. Customer stamps reference
// these resources via cross-subscription RBAC (AcrPull, Blob Reader).
//
// Operations Subscription: b03c9eb4-cddc-4987-9673-9ac44b9cc1d9
// ============================================================================

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@description('Azure region for shared platform resources.')
param location string = resourceGroup().location

@description('Short region identifier (e.g., eus2, wus3).')
@minLength(2)
@maxLength(6)
param regionShort string

@description('Deployment environment for the platform itself.')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Tags applied to all platform resources.')
param tags object = {}

@description('ACR SKU. Premium required for geo-replication and private endpoints.')
@allowed(['Basic', 'Standard', 'Premium'])
param acrSku string = 'Premium'

@description('Enable Private Endpoints for Storage and ACR.')
param enablePrivateEndpoints bool = false

@description('VNet address space (only used when enablePrivateEndpoints = true).')
param vnetAddressPrefix string = '10.100.0.0/16'

@description('Private endpoints subnet CIDR.')
param endpointsSubnetPrefix string = '10.100.0.0/24'

@description('Log Analytics data retention in days.')
param dataRetention int = environment == 'prod' ? 90 : 30

// ---------------------------------------------------------------------------
// Naming convention: dai-platform-{env}-{regionShort}
// ---------------------------------------------------------------------------

var baseName = 'dai-platform-${environment}-${regionShort}'
var uniqueSuffix = uniqueString(resourceGroup().id, baseName)

var acrName = 'acrplatformdai${take(uniqueSuffix, 6)}'
var storageAccountName = 'stplatformdai${take(uniqueSuffix, 6)}'
var logAnalyticsName = 'log-${baseName}'
var appInsightsName = 'appi-${baseName}'

var defaultTags = union(tags, {
  project: 'directai'
  component: 'platform'
  environment: environment
  region: regionShort
  'managed-by': 'bicep'
})

// ---------------------------------------------------------------------------
// 1. Log Analytics Workspace — centralized observability sink
// ---------------------------------------------------------------------------

module logAnalytics 'br/public:avm/res/operational-insights/workspace:0.9.1' = {
  name: 'logAnalytics'
  params: {
    name: logAnalyticsName
    location: location
    skuName: 'PerGB2018'
    dataRetention: dataRetention
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// 2. Application Insights — distributed tracing + live metrics
//    Workspace-based (backed by Log Analytics above).
// ---------------------------------------------------------------------------

module appInsights 'br/public:avm/res/insights/component:0.4.2' = {
  name: 'appInsights'
  params: {
    name: appInsightsName
    workspaceResourceId: logAnalytics.outputs.resourceId
    location: location
    applicationType: 'web'
    retentionInDays: dataRetention
    disableLocalAuth: true
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// 3. Network (conditional — only when private endpoints enabled)
// ---------------------------------------------------------------------------

module vnet 'br/public:avm/res/network/virtual-network:0.5.2' = if (enablePrivateEndpoints) {
  name: 'vnet'
  params: {
    name: 'vnet-${baseName}'
    location: location
    addressPrefixes: [vnetAddressPrefix]
    subnets: [
      {
        name: 'snet-endpoints'
        addressPrefix: endpointsSubnetPrefix
        privateEndpointNetworkPolicies: 'Disabled'
      }
    ]
    tags: defaultTags
  }
}

module dnsZoneAcr 'br/public:avm/res/network/private-dns-zone:0.7.0' = if (enablePrivateEndpoints) {
  name: 'dnsZoneAcr'
  params: {
    name: 'privatelink.azurecr.io'
    location: 'global'
    virtualNetworkLinks: [
      {
        virtualNetworkResourceId: vnet!.outputs.resourceId
        registrationEnabled: false
      }
    ]
    tags: defaultTags
  }
}

module dnsZoneBlob 'br/public:avm/res/network/private-dns-zone:0.7.0' = if (enablePrivateEndpoints) {
  name: 'dnsZoneBlob'
  params: {
    name: 'privatelink.blob.${az.environment().suffixes.storage}'
    location: 'global'
    virtualNetworkLinks: [
      {
        virtualNetworkResourceId: vnet!.outputs.resourceId
        registrationEnabled: false
      }
    ]
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// 4. Container Registry (ACR) — stores all inference images
//    Premium SKU enables geo-replication, private endpoints, and content trust.
//    Customer kubelet identities get AcrPull via cross-subscription RBAC.
// ---------------------------------------------------------------------------

module acr 'br/public:avm/res/container-registry/registry:0.6.0' = {
  name: 'acr'
  params: {
    name: acrName
    location: location
    acrSku: acrSku
    // No roleAssignments here — customer kubelets are assigned AcrPull
    // cross-subscription after their stamp deploys (see onboard-customer.yml).
    privateEndpoints: enablePrivateEndpoints
      ? [
          {
            service: 'registry'
            subnetResourceId: vnet!.outputs.subnetResourceIds[0]
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  privateDnsZoneResourceId: dnsZoneAcr!.outputs.resourceId
                }
              ]
            }
          }
        ]
      : []
    diagnosticSettings: [
      {
        workspaceResourceId: logAnalytics.outputs.resourceId
        metricCategories: [{ category: 'AllMetrics' }]
      }
    ]
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// 5. Storage Account — pre-compiled TRT-LLM engine cache
//    Stores compiled engines keyed by:
//      {architecture}_{parameter_count}_{quantization}_tp{tp_degree}_{gpu_sku}_trtllm{version}
//    Customer stamps pull cached engines at deploy time.
// ---------------------------------------------------------------------------

module storage 'br/public:avm/res/storage/storage-account:0.15.0' = {
  name: 'storage'
  params: {
    name: storageAccountName
    location: location
    kind: 'StorageV2'
    skuName: environment == 'prod' ? 'Standard_ZRS' : 'Standard_LRS'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    blobServices: {
      containers: [
        { name: 'engine-cache', publicAccess: 'None' }
        { name: 'model-registry', publicAccess: 'None' }
        { name: 'build-artifacts', publicAccess: 'None' }
      ]
    }
    privateEndpoints: enablePrivateEndpoints
      ? [
          {
            service: 'blob'
            subnetResourceId: vnet!.outputs.subnetResourceIds[0]
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  privateDnsZoneResourceId: dnsZoneBlob!.outputs.resourceId
                }
              ]
            }
          }
        ]
      : []
    diagnosticSettings: [
      {
        workspaceResourceId: logAnalytics.outputs.resourceId
        metricCategories: [{ category: 'AllMetrics' }]
      }
    ]
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('ACR login server (e.g., acrplatformdaiXXXXXX.azurecr.io).')
output acrLoginServer string = acr.outputs.loginServer

@description('ACR name.')
output acrName string = acr.outputs.name

@description('ACR resource ID.')
output acrResourceId string = acr.outputs.resourceId

@description('Storage account name for engine cache.')
output storageAccountName string = storage.outputs.name

@description('Storage account resource ID.')
output storageAccountResourceId string = storage.outputs.resourceId

@description('Log Analytics workspace resource ID.')
output logAnalyticsWorkspaceId string = logAnalytics.outputs.resourceId

@description('Application Insights connection string.')
output appInsightsConnectionString string = appInsights.outputs.connectionString

@description('Application Insights resource ID.')
output appInsightsResourceId string = appInsights.outputs.resourceId
