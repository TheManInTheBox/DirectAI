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

@description('Platform DNS zone name (e.g., agilecloud.ai). Used for customer subdomains.')
param dnsZoneName string = 'agilecloud.ai'

@description('Enable the public DNS zone for customer subdomains.')
param enableDnsZone bool = true

// --- Platform AKS (CPU-only web hosting cluster) ---

@description('Deploy the Platform AKS cluster for web hosting, metering workers, and webhooks.')
param enablePlatformAks bool = false

@description('Kubernetes version for Platform AKS.')
param kubernetesVersion string = '1.33'

@description('Platform AKS VNet address space.')
param aksVnetAddressPrefix string = '10.200.0.0/16'

@description('Platform AKS node subnet CIDR.')
param aksSubnetPrefix string = '10.200.0.0/20'

@description('Platform AKS system pool min node count.')
param aksSystemPoolMinCount int = 1

@description('Platform AKS system pool max node count.')
param aksSystemPoolMaxCount int = 3

@description('Platform AKS CPU user pool min node count.')
param aksCpuPoolMinCount int = 1

@description('Platform AKS CPU user pool max node count.')
param aksCpuPoolMaxCount int = 5

// ---------------------------------------------------------------------------
// Naming convention: dai-platform-{env}-{regionShort}
// ---------------------------------------------------------------------------

var baseName = 'dai-platform-${environment}-${regionShort}'
var uniqueSuffix = uniqueString(resourceGroup().id, baseName)

var acrName = 'acrplatformdai${take(uniqueSuffix, 6)}'
var storageAccountName = 'stplatformdai${take(uniqueSuffix, 6)}'
var logAnalyticsName = 'log-${baseName}'
var appInsightsName = 'appi-${baseName}'

// Platform AKS naming
var aksVnetName = 'vnet-aks-${baseName}'
var aksName = 'aks-${baseName}'
var platformCpIdentityName = 'id-cp-${baseName}'
var platformKubeletIdentityName = 'id-kubelet-${baseName}'
var platformKeyVaultName = 'kvplatdai${take(uniqueSuffix, 6)}'

// Role Definition IDs (used by Platform AKS RBAC assignments)
var managedIdentityOperatorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'f1a07417-d97a-45cb-824c-7a7467783830'
)
var keyVaultSecretsUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)

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
// 6. Public DNS Zone — agilecloud.ai
//    Customer subdomains (e.g., acme.agilecloud.ai) are A records pointing
//    to each customer stamp's NGINX Ingress external IP.
//    Deployed once per platform. Stamp deployments create records via
//    cross-subscription RBAC (DNS Zone Contributor on the platform RG).
// ---------------------------------------------------------------------------

resource dnsZone 'Microsoft.Network/dnsZones@2023-07-01-preview' = if (enableDnsZone) {
  name: dnsZoneName
  location: 'global'
  tags: defaultTags
  properties: {
    zoneType: 'Public'
  }
}

// ===========================================================================
// 7. Platform AKS — CPU-only cluster for web app, metering, and webhooks
//
//    Deployed to the Operations subscription alongside ACR and engine cache.
//    No GPU pools — serves the Next.js web app, Stripe webhook handlers,
//    metering workers, and the admin dashboard.
//
//    All resources conditional on enablePlatformAks.
// ===========================================================================

// ── 7a. Managed Identities ─────────────────────────────────────────

resource platformCpIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (enablePlatformAks) {
  name: platformCpIdentityName
  location: location
  tags: defaultTags
}

resource platformKubeletIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (enablePlatformAks) {
  name: platformKubeletIdentityName
  location: location
  tags: defaultTags
}

resource rolePlatformKubeletOperator 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enablePlatformAks) {
  name: guid(platformKubeletIdentity.id, platformCpIdentity.id, managedIdentityOperatorRoleId)
  scope: platformKubeletIdentity
  properties: {
    principalId: platformCpIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: managedIdentityOperatorRoleId
  }
}

// ── 7b. Networking ─────────────────────────────────────────────────

resource aksVnet 'Microsoft.Network/virtualNetworks@2024-01-01' = if (enablePlatformAks) {
  name: aksVnetName
  location: location
  tags: defaultTags
  properties: {
    addressSpace: { addressPrefixes: [aksVnetAddressPrefix] }
    subnets: [
      {
        name: 'snet-aks'
        properties: {
          addressPrefix: aksSubnetPrefix
        }
      }
    ]
  }
}

resource aksVnetDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enablePlatformAks) {
  name: 'diag-${aksVnetName}'
  scope: aksVnet
  properties: {
    workspaceId: logAnalytics.outputs.resourceId
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
}

// ── 7c. Key Vault ──────────────────────────────────────────────────
//    Stores Stripe API keys, NextAuth secret, DB connection strings.
//    Kubelet identity gets Secrets User (read-only).

resource platformKeyVault 'Microsoft.KeyVault/vaults@2023-07-01' = if (enablePlatformAks) {
  name: platformKeyVaultName
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
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource rolePlatformKvSecrets 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enablePlatformAks) {
  name: guid(platformKeyVault.id, platformKubeletIdentity.id, keyVaultSecretsUserRoleId)
  scope: platformKeyVault
  properties: {
    principalId: platformKubeletIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleId
  }
}

resource platformKvDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enablePlatformAks) {
  name: 'diag-${platformKeyVaultName}'
  scope: platformKeyVault
  properties: {
    workspaceId: logAnalytics.outputs.resourceId
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
}

// ── 7d. RBAC: Kubelet → Platform ACR (AcrPull) ────────────────────

module platformAcrPull '../modules/acr-role-assignment.bicep' = if (enablePlatformAks) {
  name: 'platformAcrPull'
  params: {
    acrName: acrName
    principalId: platformKubeletIdentity!.properties.principalId
  }
  dependsOn: [acr]
}

// ── 7e. AKS Cluster ───────────────────────────────────────────────
//    CPU-only: system pool + cpu user pool. No GPU pools.
//    Direct resource declaration (not AVM) for consistency with stamp
//    and to avoid ARM nested deployment output evaluation issues.

resource platformAks 'Microsoft.ContainerService/managedClusters@2024-09-01' = if (enablePlatformAks) {
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
      '${platformCpIdentity.id}': {}
    }
  }
  properties: {
    kubernetesVersion: kubernetesVersion
    dnsPrefix: aksName
    identityProfile: {
      kubeletidentity: {
        resourceId: platformKubeletIdentity.id
        clientId: platformKubeletIdentity!.properties.clientId
        objectId: platformKubeletIdentity!.properties.principalId
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
    agentPoolProfiles: [
      {
        name: 'system'
        mode: 'System'
        vmSize: 'Standard_DS2_v2'
        count: aksSystemPoolMinCount
        minCount: aksSystemPoolMinCount
        maxCount: aksSystemPoolMaxCount
        enableAutoScaling: true
        osType: 'Linux'
        osDiskSizeGB: 128
        type: 'VirtualMachineScaleSets'
        availabilityZones: environment == 'prod' ? ['1', '2', '3'] : ['1']
        vnetSubnetID: aksVnet!.properties.subnets[0].id
        nodeTaints: ['CriticalAddonsOnly=true:NoSchedule']
      }
      {
        name: 'cpu'
        mode: 'User'
        vmSize: 'Standard_DS2_v2'
        count: aksCpuPoolMinCount
        minCount: aksCpuPoolMinCount
        maxCount: aksCpuPoolMaxCount
        enableAutoScaling: true
        osType: 'Linux'
        osDiskSizeGB: 128
        type: 'VirtualMachineScaleSets'
        availabilityZones: environment == 'prod' ? ['1', '2', '3'] : ['1']
        vnetSubnetID: aksVnet!.properties.subnets[0].id
      }
    ]
    addonProfiles: {
      omsagent: {
        enabled: true
        config: { logAnalyticsWorkspaceResourceID: logAnalytics.outputs.resourceId }
      }
      azureKeyvaultSecretsProvider: {
        enabled: true
        config: { enableSecretRotation: 'true' }
      }
    }
    oidcIssuerProfile: { enabled: true }
    securityProfile: { workloadIdentity: { enabled: true } }
    workloadAutoScalerProfile: { keda: { enabled: true } }
    azureMonitorProfile: { metrics: { enabled: true } }
    autoUpgradeProfile: { upgradeChannel: 'stable', nodeOSUpgradeChannel: 'SecurityPatch' }
  }
  dependsOn: [rolePlatformKubeletOperator]
}

resource platformAksDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enablePlatformAks) {
  name: 'diag-${aksName}'
  scope: platformAks
  properties: {
    workspaceId: logAnalytics.outputs.resourceId
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

// ── 7f. Federated Identity Credential ──────────────────────────────

resource platformFederatedCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = if (enablePlatformAks) {
  parent: platformKubeletIdentity
  name: 'fic-aks-directai'
  properties: {
    issuer: platformAks!.properties.oidcIssuerProfile.issuerURL
    subject: 'system:serviceaccount:directai:directai'
    audiences: ['api://AzureADTokenExchange']
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

@description('DNS zone name (e.g., agilecloud.ai).')
output dnsZoneName string = enableDnsZone ? dnsZone!.name : ''

@description('DNS zone resource ID.')
output dnsZoneResourceId string = enableDnsZone ? dnsZone!.id : ''

@description('DNS zone name servers — delegate these at your domain registrar.')
output dnsZoneNameServers array = enableDnsZone ? dnsZone!.properties.nameServers : []

// --- Platform AKS outputs ---

@description('Platform AKS cluster name.')
output platformAksName string = enablePlatformAks ? aksName : ''

@description('Platform AKS cluster resource ID.')
output platformAksResourceId string = enablePlatformAks ? platformAks!.id : ''

@description('Platform AKS OIDC issuer URL.')
output platformAksOidcIssuerUrl string = enablePlatformAks ? platformAks!.properties.oidcIssuerProfile.issuerURL : ''

@description('Platform AKS control plane FQDN.')
output platformAksControlPlaneFqdn string = enablePlatformAks ? platformAks!.properties.fqdn : ''

@description('Platform Key Vault URI.')
output platformKeyVaultUri string = enablePlatformAks ? platformKeyVault!.properties.vaultUri : ''

@description('Platform kubelet identity principal ID.')
output platformKubeletIdentityPrincipalId string = enablePlatformAks ? platformKubeletIdentity!.properties.principalId : ''

@description('Platform kubelet identity client ID.')
output platformKubeletIdentityClientId string = enablePlatformAks ? platformKubeletIdentity!.properties.clientId : ''
