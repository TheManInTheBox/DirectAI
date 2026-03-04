// ============================================================================
// DirectAI Regional Stamp — main.bicep
// Deploys the complete set of Azure resources for a DirectAI inference region.
//
// Uses direct resource declarations instead of AVM modules to avoid
// ARM deployment engine issues with nested deployment output evaluation.
// ============================================================================

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@description('Azure region for the stamp.')
param location string = resourceGroup().location

@description('Short region identifier used in resource names (e.g., eus2, wus3).')
@minLength(2)
@maxLength(6)
param regionShort string

@description('Deployment environment.')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Kubernetes version for AKS.')
param kubernetesVersion string = '1.31'

@description('Tags applied to every resource in the stamp.')
param tags object = {}

@description('VNet address space.')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('AKS node subnet CIDR.')
param aksSubnetPrefix string = '10.0.0.0/22'

@description('Private endpoints subnet CIDR.')
param endpointsSubnetPrefix string = '10.0.4.0/24'

@description('Enable GPU node pools. Disable in dev to avoid quota issues.')
param enableGpuPools bool = false

@description('GPU pool tier. "production" deploys A100+H100+embeddings pools. "dev" deploys a single general-purpose T4 pool for all workloads.')
@allowed(['production', 'dev'])
param gpuPoolTier string = 'production'

@description('VM size for the dev GPU pool. Only used when gpuPoolTier is "dev".')
param devGpuVmSize string = 'Standard_NC16as_T4_v3'

@description('Max node count for the dev GPU pool. Only used when gpuPoolTier is "dev".')
param devGpuMaxCount int = 2

@description('Enable Private Endpoints for Storage, Key Vault, and ACR.')
param enablePrivateEndpoints bool = true

@description('AKS system pool min node count.')
param systemPoolMinCount int = 1

@description('AKS system pool max node count.')
param systemPoolMaxCount int = 3

@description('Customer identifier.')
param customerId string

@description('Platform ACR login server. Leave empty to deploy a per-customer ACR.')
param platformAcrLoginServer string = ''

// ---------------------------------------------------------------------------
// Naming
// ---------------------------------------------------------------------------

var prefix = 'dai'
var baseName = '${prefix}-${customerId}-${environment}-${regionShort}'
var uniqueSuffix = uniqueString(resourceGroup().id, baseName)
var customerHash = take(uniqueString(customerId), 8)
var deployPerCustomerAcr = empty(platformAcrLoginServer)

var identityControlPlaneName = 'id-cp-${baseName}'
var identityKubeletName = 'id-kubelet-${baseName}'
var logAnalyticsName = 'log-${baseName}'
var appInsightsName = 'appi-${baseName}'
var vnetName = 'vnet-${baseName}'
var keyVaultName = 'kv${prefix}${customerHash}${take(uniqueSuffix, 6)}'
var storageAccountName = 'st${prefix}${customerHash}${take(uniqueSuffix, 6)}'
var acrName = 'acr${prefix}${customerHash}${take(uniqueSuffix, 6)}'
var aksName = 'aks-${baseName}'

var defaultTags = union(tags, {
  project: 'directai'
  'customer-id': customerId
  environment: environment
  region: regionShort
  'managed-by': 'bicep'
})

// ── Role Definition IDs ────────────────────────────────────────────
var managedIdentityOperatorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'f1a07417-d97a-45cb-824c-7a7467783830'
)
var keyVaultSecretsUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)
var storageBlobDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)
var acrPullRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)

// ===========================================================================
// 1. Managed Identities
// ===========================================================================

resource identityControlPlane 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityControlPlaneName
  location: location
  tags: defaultTags
}

resource identityKubelet 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityKubeletName
  location: location
  tags: defaultTags
}

// Control plane → Managed Identity Operator on kubelet identity
resource roleKubeletOperator 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(identityKubelet.id, identityControlPlane.id, managedIdentityOperatorRoleId)
  scope: identityKubelet
  properties: {
    principalId: identityControlPlane.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: managedIdentityOperatorRoleId
  }
}

// ===========================================================================
// 2. Observability — Log Analytics + Application Insights
// ===========================================================================

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: defaultTags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: environment == 'prod' ? 90 : 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  tags: defaultTags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    RetentionInDays: environment == 'prod' ? 90 : 30
    DisableLocalAuth: true
  }
}

// ===========================================================================
// 3. Networking — VNet, NSG, Private DNS Zones
// ===========================================================================

resource nsgEndpoints 'Microsoft.Network/networkSecurityGroups@2024-01-01' = if (enablePrivateEndpoints) {
  name: 'nsg-snet-endpoints-${baseName}'
  location: location
  tags: defaultTags
  properties: {
    securityRules: [
      {
        name: 'AllowVNetInbound'
        properties: {
          access: 'Allow'
          direction: 'Inbound'
          priority: 100
          protocol: '*'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '*'
        }
      }
      {
        name: 'DenyAllInternetInbound'
        properties: {
          access: 'Deny'
          direction: 'Inbound'
          priority: 4096
          protocol: '*'
          sourceAddressPrefix: 'Internet'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: vnetName
  location: location
  tags: defaultTags
  properties: {
    addressSpace: { addressPrefixes: [vnetAddressPrefix] }
    subnets: [
      {
        name: 'snet-aks'
        properties: {
          addressPrefix: aksSubnetPrefix
        }
      }
      {
        name: 'snet-endpoints'
        properties: {
          addressPrefix: endpointsSubnetPrefix
          privateEndpointNetworkPolicies: 'Disabled'
          networkSecurityGroup: enablePrivateEndpoints
            ? { id: nsgEndpoints.id }
            : null
        }
      }
    ]
  }
}

resource vnetDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-${vnetName}'
  scope: vnet
  properties: {
    workspaceId: logAnalytics.id
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
}

// Private DNS Zones
resource dnsZoneBlob 'Microsoft.Network/privateDnsZones@2024-06-01' = if (enablePrivateEndpoints) {
  name: 'privatelink.blob.${az.environment().suffixes.storage}'
  location: 'global'
  tags: defaultTags
}

resource dnsZoneBlobLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = if (enablePrivateEndpoints) {
  parent: dnsZoneBlob
  name: 'link-${vnetName}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

resource dnsZoneVault 'Microsoft.Network/privateDnsZones@2024-06-01' = if (enablePrivateEndpoints) {
  name: 'privatelink.vaultcore.azure.net'
  location: 'global'
  tags: defaultTags
}

resource dnsZoneVaultLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = if (enablePrivateEndpoints) {
  parent: dnsZoneVault
  name: 'link-${vnetName}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

resource dnsZoneAcr 'Microsoft.Network/privateDnsZones@2024-06-01' = if (enablePrivateEndpoints && deployPerCustomerAcr) {
  name: 'privatelink.azurecr.io'
  location: 'global'
  tags: defaultTags
}

resource dnsZoneAcrLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = if (enablePrivateEndpoints && deployPerCustomerAcr) {
  parent: dnsZoneAcr
  name: 'link-${vnetName}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

// ===========================================================================
// 4. Key Vault
// ===========================================================================

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: defaultTags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enablePurgeProtection: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    networkAcls: {
      defaultAction: enablePrivateEndpoints ? 'Deny' : 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource roleKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, identityKubelet.id, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    principalId: identityKubelet.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleId
  }
}

resource kvSecretAppInsights 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'appinsights-connection-string'
  properties: {
    value: appInsights.properties.ConnectionString
  }
}

resource kvDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-${keyVaultName}'
  scope: keyVault
  properties: {
    workspaceId: logAnalytics.id
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
}

resource kvPe 'Microsoft.Network/privateEndpoints@2024-01-01' = if (enablePrivateEndpoints) {
  name: 'pe-${keyVaultName}'
  location: location
  tags: defaultTags
  properties: {
    subnet: { id: vnet.properties.subnets[1].id }
    privateLinkServiceConnections: [
      {
        name: 'vault'
        properties: {
          privateLinkServiceId: keyVault.id
          groupIds: ['vault']
        }
      }
    ]
  }
}

resource kvPeDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = if (enablePrivateEndpoints) {
  parent: kvPe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'vault'
        properties: { privateDnsZoneId: dnsZoneVault.id }
      }
    ]
  }
}

// ===========================================================================
// 5. Storage Account
// ===========================================================================

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: defaultTags
  kind: 'StorageV2'
  sku: { name: environment == 'prod' ? 'Standard_ZRS' : 'Standard_LRS' }
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    networkAcls: {
      defaultAction: enablePrivateEndpoints ? 'Deny' : 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource containerModels 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'models'
  properties: { publicAccess: 'None' }
}

resource containerEngines 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'engines'
  properties: { publicAccess: 'None' }
}

resource containerCheckpoints 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'checkpoints'
  properties: { publicAccess: 'None' }
}

resource containerConfigs 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'configs'
  properties: { publicAccess: 'None' }
}

resource roleStorageBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, identityKubelet.id, storageBlobDataContributorRoleId)
  scope: storage
  properties: {
    principalId: identityKubelet.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleId
  }
}

resource storageDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-${storageAccountName}'
  scope: storage
  properties: {
    workspaceId: logAnalytics.id
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
}

resource storagePe 'Microsoft.Network/privateEndpoints@2024-01-01' = if (enablePrivateEndpoints) {
  name: 'pe-${storageAccountName}'
  location: location
  tags: defaultTags
  properties: {
    subnet: { id: vnet.properties.subnets[1].id }
    privateLinkServiceConnections: [
      {
        name: 'blob'
        properties: {
          privateLinkServiceId: storage.id
          groupIds: ['blob']
        }
      }
    ]
  }
}

resource storagePeDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = if (enablePrivateEndpoints) {
  parent: storagePe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'blob'
        properties: { privateDnsZoneId: dnsZoneBlob.id }
      }
    ]
  }
}

// ===========================================================================
// 6. Container Registry (per-customer only)
// ===========================================================================

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = if (deployPerCustomerAcr) {
  name: acrName
  location: location
  tags: defaultTags
  sku: { name: environment == 'prod' ? 'Premium' : 'Basic' }
  properties: {
    adminUserEnabled: false
  }
}

resource roleAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployPerCustomerAcr) {
  name: guid(acr.id, identityKubelet.id, acrPullRoleId)
  scope: acr
  properties: {
    principalId: identityKubelet.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleId
  }
}

resource acrDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (deployPerCustomerAcr) {
  name: 'diag-${acrName}'
  scope: acr
  properties: {
    workspaceId: logAnalytics.id
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
}

resource acrPe 'Microsoft.Network/privateEndpoints@2024-01-01' = if (enablePrivateEndpoints && deployPerCustomerAcr) {
  name: 'pe-${acrName}'
  location: location
  tags: defaultTags
  properties: {
    subnet: { id: vnet.properties.subnets[1].id }
    privateLinkServiceConnections: [
      {
        name: 'registry'
        properties: {
          privateLinkServiceId: acr.id
          groupIds: ['registry']
        }
      }
    ]
  }
}

resource acrPeDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = if (enablePrivateEndpoints && deployPerCustomerAcr) {
  parent: acrPe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'acr'
        properties: { privateDnsZoneId: dnsZoneAcr.id }
      }
    ]
  }
}

// ===========================================================================
// 7. AKS Cluster
// ===========================================================================

var productionGpuPools = [
  {
    name: 'gpua100'
    mode: 'User'
    vmSize: 'Standard_ND96asr_v4'
    count: 0
    minCount: 0
    maxCount: 4
    enableAutoScaling: true
    osType: 'Linux'
    osDiskSizeGB: 128
    type: 'VirtualMachineScaleSets'
    vnetSubnetID: vnet.properties.subnets[0].id
    nodeLabels: {
      'directai.io/gpu-pool': 'a100'
      'directai.io/pool': 'inference'
    }
    nodeTaints: ['nvidia.com/gpu=a100:NoSchedule']
  }
  {
    name: 'gpuh100'
    mode: 'User'
    vmSize: 'Standard_ND96isr_H100_v5'
    count: 0
    minCount: 0
    maxCount: 2
    enableAutoScaling: true
    osType: 'Linux'
    osDiskSizeGB: 128
    type: 'VirtualMachineScaleSets'
    vnetSubnetID: vnet.properties.subnets[0].id
    nodeLabels: {
      'directai.io/gpu-pool': 'h100'
      'directai.io/pool': 'inference'
    }
    nodeTaints: ['nvidia.com/gpu=h100:NoSchedule']
  }
  {
    name: 'embeddings'
    mode: 'User'
    vmSize: 'Standard_NC24ads_A100_v4'
    count: 0
    minCount: 0
    maxCount: 4
    enableAutoScaling: true
    osType: 'Linux'
    osDiskSizeGB: 128
    type: 'VirtualMachineScaleSets'
    vnetSubnetID: vnet.properties.subnets[0].id
    nodeLabels: {
      'directai.io/gpu-pool': 'embeddings'
      'directai.io/pool': 'embeddings'
    }
    nodeTaints: ['directai.io/workload=embeddings:NoSchedule']
  }
]

var devGpuPools = [
  {
    name: 'gput4'
    mode: 'User'
    vmSize: devGpuVmSize
    count: 0
    minCount: 0
    maxCount: devGpuMaxCount
    enableAutoScaling: true
    osType: 'Linux'
    osDiskSizeGB: 128
    type: 'VirtualMachineScaleSets'
    vnetSubnetID: vnet.properties.subnets[0].id
    nodeLabels: {
      'directai.io/gpu-pool': 't4'
      'directai.io/pool': 'inference'
    }
    nodeTaints: ['nvidia.com/gpu=t4:NoSchedule']
  }
]

var gpuAgentPools = enableGpuPools
  ? (gpuPoolTier == 'dev' ? devGpuPools : productionGpuPools)
  : []

resource aks 'Microsoft.ContainerService/managedClusters@2024-09-01' = {
  name: aksName
  location: location
  tags: defaultTags
  sku: {
    name: 'Base'
    tier: environment == 'prod' ? 'Standard' : 'Free'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityControlPlane.id}': {}
    }
  }
  properties: {
    kubernetesVersion: kubernetesVersion
    dnsPrefix: aksName
    identityProfile: {
      kubeletidentity: {
        resourceId: identityKubelet.id
        clientId: identityKubelet.properties.clientId
        objectId: identityKubelet.properties.principalId
      }
    }
    aadProfile: {
      enableAzureRBAC: true
      managed: true
    }
    disableLocalAccounts: true
    networkProfile: {
      networkPlugin: 'azure'
      networkPluginMode: 'overlay'
      networkDataplane: 'azure'
      networkPolicy: 'azure'
      dnsServiceIP: '10.10.200.10'
      serviceCidr: '10.10.200.0/24'
    }
    agentPoolProfiles: concat(
      [
        {
          name: 'system'
          mode: 'System'
          vmSize: 'Standard_DS4_v2'
          count: systemPoolMinCount
          minCount: systemPoolMinCount
          maxCount: systemPoolMaxCount
          enableAutoScaling: true
          osType: 'Linux'
          osDiskSizeGB: 128
          type: 'VirtualMachineScaleSets'
          availabilityZones: environment == 'prod' ? ['1', '2', '3'] : ['1']
          vnetSubnetID: vnet.properties.subnets[0].id
          nodeTaints: ['CriticalAddonsOnly=true:NoSchedule']
        }
        {
          name: 'cpu'
          mode: 'User'
          vmSize: 'Standard_DS2_v2'
          count: 1
          minCount: 1
          maxCount: 3
          enableAutoScaling: true
          osType: 'Linux'
          osDiskSizeGB: 128
          type: 'VirtualMachineScaleSets'
          availabilityZones: environment == 'prod' ? ['1', '2', '3'] : ['1']
          vnetSubnetID: vnet.properties.subnets[0].id
        }
      ],
      gpuAgentPools
    )
    addonProfiles: {
      omsagent: {
        enabled: true
        config: { logAnalyticsWorkspaceResourceID: logAnalytics.id }
      }
      azureKeyvaultSecretsProvider: {
        enabled: true
        config: { enableSecretRotation: 'true' }
      }
    }
    oidcIssuerProfile: { enabled: true }
    securityProfile: { workloadIdentity: { enabled: true } }
    storageProfile: {
      blobCSIDriver: { enabled: true }
      diskCSIDriver: { enabled: true }
    }
    workloadAutoScalerProfile: { keda: { enabled: true } }
    azureMonitorProfile: { metrics: { enabled: true } }
    autoUpgradeProfile: { upgradeChannel: 'stable', nodeOSUpgradeChannel: 'SecurityPatch' }
  }
  dependsOn: [roleKubeletOperator]
}

resource aksDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-${aksName}'
  scope: aks
  properties: {
    workspaceId: logAnalytics.id
    logs: [
      { category: 'kube-apiserver', enabled: true }
      { category: 'kube-controller-manager', enabled: true }
      { category: 'kube-scheduler', enabled: true }
      { category: 'cluster-autoscaler', enabled: true }
      { category: 'kube-audit-admin', enabled: true }
      { category: 'guard', enabled: true }
    ]
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
}

// ===========================================================================
// 8. Observability Workbook
// ===========================================================================

module observabilityWorkbook 'modules/workbook.bicep' = {
  name: 'observabilityWorkbook'
  params: {
    location: location
    logAnalyticsWorkspaceId: logAnalytics.id
    appInsightsResourceId: appInsights.id
    tags: defaultTags
  }
}

// ===========================================================================
// 9. Federated Identity Credential — Workload Identity for K8s pods
// ===========================================================================

resource kubeletFederatedCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: identityKubelet
  name: 'fic-aks-directai'
  properties: {
    issuer: aks.properties.oidcIssuerProfile.issuerURL
    subject: 'system:serviceaccount:directai:directai'
    audiences: ['api://AzureADTokenExchange']
  }
}

// ===========================================================================
// Outputs
// ===========================================================================

output aksName string = aks.name
output aksResourceId string = aks.id
output aksOidcIssuerUrl string = aks.properties.oidcIssuerProfile.issuerURL
output aksControlPlaneFqdn string = aks.properties.fqdn
output storageAccountName string = storage.name
output acrLoginServer string = deployPerCustomerAcr ? acr!.properties.loginServer : platformAcrLoginServer
output keyVaultUri string = keyVault.properties.vaultUri
output logAnalyticsWorkspaceId string = logAnalytics.id
output controlPlaneIdentityPrincipalId string = identityControlPlane.properties.principalId
output controlPlaneIdentityClientId string = identityControlPlane.properties.clientId
output kubeletIdentityPrincipalId string = identityKubelet.properties.principalId
output kubeletIdentityClientId string = identityKubelet.properties.clientId
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output appInsightsResourceId string = appInsights.id
output observabilityWorkbookId string = observabilityWorkbook.outputs.workbookResourceId
