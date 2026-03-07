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

@description('IPv4 address of the Platform AKS NGINX Ingress LB (serves agilecloud.ai web app). Empty = skip record.')
param platformWebIngressIp string = ''

@description('IPv4 address of the Dev AKS NGINX Ingress LB (serves api.agilecloud.ai). Empty = skip record.')
param devApiIngressIp string = ''

// --- Platform AKS (CPU-only web hosting cluster) ---

@description('Deploy the Platform AKS cluster for web hosting, metering workers, and webhooks.')
param enablePlatformAks bool = false

// --- Platform PostgreSQL (user/billing/session database) ---

@description('Deploy the Platform PostgreSQL Flexible Server for user, billing, and session data.')
param enablePlatformDb bool = false

// --- Azure AI Content Safety ---

@description('Deploy Azure AI Content Safety for guardrails input/output filtering.')
param enableContentSafety bool = false

@description('Deploy immutable Azure Blob Storage for audit log archival.')
param enableAuditStorage bool = false

@description('Audit blob retention days (immutability policy lock period).')
param auditRetentionDays int = 365

@description('Azure AI Content Safety SKU. Free (F0) = 5K txn/month, Standard (S0) = pay-per-transaction.')
@allowed(['F0', 'S0'])
param contentSafetySku string = 'F0'

@description('PostgreSQL administrator login name.')
param postgresAdminLogin string = 'directaiadmin'

@secure()
@description('PostgreSQL administrator password. Required when enablePlatformDb = true.')
param postgresAdminPassword string = ''

@description('PostgreSQL SKU name (e.g., Standard_B1ms for dev, Standard_D2s_v3 for prod).')
param postgresSkuName string = 'Standard_B1ms'

@description('PostgreSQL pricing tier.')
@allowed(['Burstable', 'GeneralPurpose', 'MemoryOptimized'])
param postgresTier string = 'Burstable'

@description('PostgreSQL storage size in GB.')
param postgresStorageGB int = 32

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

// --- Azure Front Door Premium (latency-based inference API routing) ---

@description('Deploy Azure Front Door Premium for latency-based routing across inference regions.')
param enableFrontDoor bool = false

@description('Inference API origin configs. Each entry: { region: "scus", hostname: "48.192.177.54" }. Empty = no origins (deploy profile only).')
param inferenceApiOrigins array = []

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

// Platform PostgreSQL naming
var postgresServerName = 'psql-${baseName}'

// Content Safety naming
var contentSafetyName = 'cs-${baseName}'

// Audit Storage naming
var auditStorageAccountName = 'stauditdai${take(uniqueSuffix, 6)}'

// Front Door naming
var frontDoorName = 'fd-${baseName}'
var wafPolicyName = 'waf-fd-${baseName}'

// Role Definition IDs (used by Platform AKS RBAC assignments)
var managedIdentityOperatorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'f1a07417-d97a-45cb-824c-7a7467783830'
)
var keyVaultSecretsUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)
var cognitiveServicesUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'a97b65f3-24c7-4388-baec-2e87135dc908'
)
var storageBlobDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
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

// ── 6a. DNS A Records ──────────────────────────────────────────────
// Apex (agilecloud.ai) → Platform AKS NGINX LB (web app)
// api subdomain (api.agilecloud.ai) → Dev/Prod AKS NGINX LB (inference API)
// Records are conditional: only created when the IP parameter is non-empty.

module dnsRecordApex '../modules/dns-record.bicep' = if (enableDnsZone && !empty(platformWebIngressIp)) {
  name: 'dnsRecordApex'
  params: {
    dnsZoneName: dnsZoneName
    recordName: '@'
    ipAddress: platformWebIngressIp
    ttl: 300
  }
  dependsOn: [dnsZone]
}

module dnsRecordWww '../modules/dns-record.bicep' = if (enableDnsZone && !empty(platformWebIngressIp)) {
  name: 'dnsRecordWww'
  params: {
    dnsZoneName: dnsZoneName
    recordName: 'www'
    ipAddress: platformWebIngressIp
    ttl: 300
  }
  dependsOn: [dnsZone]
}

// When Front Door is enabled, api.agilecloud.ai uses a CNAME → FD endpoint (section 9).
// The A record is only used for direct-to-AKS routing (dev/staging without FD).
module dnsRecordApi '../modules/dns-record.bicep' = if (enableDnsZone && !empty(devApiIngressIp) && !enableFrontDoor) {
  name: 'dnsRecordApi'
  params: {
    dnsZoneName: dnsZoneName
    recordName: 'api'
    ipAddress: devApiIngressIp
    ttl: 300
  }
  dependsOn: [dnsZone]
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
// 8. Platform PostgreSQL — user accounts, API keys, billing, sessions
//
//    Conditional on enablePlatformDb. Uses AVM module.
//    Dev: Burstable B1ms, public access, Azure-only firewall
//    Prod: GeneralPurpose D2s_v3, zone-redundant HA, private endpoint
// ---------------------------------------------------------------------------

module platformDb 'br/public:avm/res/db-for-postgre-sql/flexible-server:0.14.0' = if (enablePlatformDb) {
  name: 'platformDb'
  params: {
    name: postgresServerName
    location: location
    skuName: postgresSkuName
    tier: postgresTier
    storageSizeGB: postgresStorageGB
    version: '17'
    availabilityZone: 1

    // Authentication — password for dev, Entra-only for prod (Phase 2)
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword

    // Entra admin — kubelet identity can authenticate via workload identity
    administrators: enablePlatformAks ? [
      {
        objectId: platformKubeletIdentity.properties.principalId
        principalName: platformKubeletIdentityName
        principalType: 'ServicePrincipal'
      }
    ] : []

    // Network — public access for dev (Azure services only), private endpoint for prod
    firewallRules: [
      {
        name: 'AllowAllWindowsAzureIps'
        startIpAddress: '0.0.0.0'
        endIpAddress: '0.0.0.0'
      }
    ]

    // Default database
    databases: [
      {
        name: 'directai'
        charset: 'UTF8'
        collation: 'en_US.utf8'
      }
    ]

    // High availability — disabled for dev (Burstable doesn't support HA)
    highAvailability: 'Disabled'

    // Backup — 7 days for dev, 35 for prod; no geo-redundancy for dev
    backupRetentionDays: environment == 'prod' ? 35 : 7
    geoRedundantBackup: 'Disabled'

    // Diagnostics → Log Analytics
    diagnosticSettings: [
      {
        workspaceResourceId: logAnalytics.outputs.resourceId
        metricCategories: [
          { category: 'AllMetrics' }
        ]
      }
    ]

    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// 8a. Azure AI Content Safety — Guardrails input/output filtering
//
//     Provides text content classification for hate, violence, self-harm,
//     and sexual content. Used by the ContentSafetyMiddleware in the API server.
//
//     Conditional on enableContentSafety.
//     Dev: Free F0 (5K transactions/month, public endpoint)
//     Prod: Standard S0 (pay-per-transaction, private endpoint — Phase 2)
// ---------------------------------------------------------------------------

resource contentSafety 'Microsoft.CognitiveServices/accounts@2024-10-01' = if (enableContentSafety) {
  name: contentSafetyName
  location: location
  tags: defaultTags
  kind: 'ContentSafety'
  sku: {
    name: contentSafetySku
  }
  properties: {
    customSubDomainName: contentSafetyName
    publicNetworkAccess: 'Enabled'          // Private endpoint in prod (Phase 2)
    disableLocalAuth: false                  // API key auth for dev; managed identity for prod
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

// ── 8a-i. Store Content Safety endpoint + key in Platform Key Vault ─────

resource kvSecretCsEndpoint 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (enableContentSafety && enablePlatformAks) {
  parent: platformKeyVault
  name: 'content-safety-endpoint'
  properties: {
    value: enableContentSafety ? contentSafety!.properties.endpoint : ''
  }
}

resource kvSecretCsKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (enableContentSafety && enablePlatformAks) {
  parent: platformKeyVault
  name: 'content-safety-key'
  properties: {
    value: enableContentSafety ? contentSafety!.listKeys().key1 : ''
  }
}

// ── 8a-i-b. Store App Insights connection string in Platform Key Vault ──

resource kvSecretAppInsights 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (enablePlatformAks) {
  parent: platformKeyVault
  name: 'appinsights-connection-string'
  properties: {
    value: appInsights.outputs.connectionString
  }
}

// ── 8a-ii. RBAC: Platform kubelet → Cognitive Services User ─────────────
//    Allows API server pods to call Content Safety via managed identity
//    once we switch from API key to Entra auth (prod Phase 2).

resource roleCsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableContentSafety && enablePlatformAks) {
  name: guid(contentSafety.id, platformKubeletIdentity.id, cognitiveServicesUserRoleId)
  scope: contentSafety
  properties: {
    principalId: platformKubeletIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: cognitiveServicesUserRoleId
  }
}

// ── 8a-iii. Diagnostics ─────────────────────────────────────────────────

resource csDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableContentSafety) {
  name: 'diag-${contentSafetyName}'
  scope: contentSafety
  properties: {
    workspaceId: logAnalytics.outputs.resourceId
    logs: [
      { category: 'Audit', enabled: true }
      { category: 'RequestResponse', enabled: true }
    ]
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
}

// ---------------------------------------------------------------------------
// 8b. Immutable Audit Blob Storage — tamper-proof audit log archival
//
//     Separate storage account from the engine-cache account. Enforces:
//       - Version-level immutability (WORM — write once, read many)
//       - Time-based retention policy (configurable, default 365 days)
//       - Blob versioning enabled
//       - No shared key access (RBAC only)
//       - No public blob access
//
//     Audit records are gzip-compressed JSON blobs uploaded by the API
//     server audit writer (app/audit/writer.py).
//
//     Conditional on enableAuditStorage.
// ---------------------------------------------------------------------------

resource auditStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = if (enableAuditStorage) {
  name: auditStorageAccountName
  location: location
  tags: union(defaultTags, { purpose: 'audit-archival' })
  kind: 'StorageV2'
  sku: {
    name: environment == 'prod' ? 'Standard_ZRS' : 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true   // Connection string auth for MVP; switch to RBAC-only in prod
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    isHnsEnabled: false
    immutableStorageWithVersioning: {
      enabled: true
      immutabilityPolicy: {
        immutabilityPeriodSinceCreationInDays: auditRetentionDays
        state: 'Unlocked'      // Unlocked for dev; lock to 'Locked' for prod compliance
      }
    }
  }
}

resource auditBlobServices 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = if (enableAuditStorage) {
  parent: auditStorage
  name: 'default'
  properties: {
    isVersioningEnabled: true
    deleteRetentionPolicy: {
      enabled: true
      days: 30
    }
  }
}

resource auditContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (enableAuditStorage) {
  parent: auditBlobServices
  name: 'audit-logs'
  properties: {
    publicAccess: 'None'
    immutableStorageWithVersioning: {
      enabled: true
    }
  }
}

// ── 8b-i. Store connection string in Platform Key Vault ─────────────

resource kvSecretAuditStorage 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (enableAuditStorage && enablePlatformAks) {
  parent: platformKeyVault
  name: 'audit-storage-connection-string'
  properties: {
    value: enableAuditStorage ? 'DefaultEndpointsProtocol=https;AccountName=${auditStorage.name};AccountKey=${auditStorage.listKeys().keys[0].value};EndpointSuffix=${az.environment().suffixes.storage}' : ''
  }
}

// ── 8b-ii. RBAC: Platform kubelet → Storage Blob Data Contributor ───
//    Allows API server pods to upload audit blobs via managed identity
//    once we switch from connection string to Entra auth (prod Phase 2).

resource roleAuditBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableAuditStorage && enablePlatformAks) {
  name: guid(auditStorage.id, platformKubeletIdentity.id, storageBlobDataContributorRoleId)
  scope: auditStorage
  properties: {
    principalId: platformKubeletIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleId
  }
}

// ── 8b-iii. Diagnostics ──────────────────────────────────────────────

resource auditStorageDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableAuditStorage) {
  name: 'diag-${auditStorageAccountName}'
  scope: auditStorage
  properties: {
    workspaceId: logAnalytics.outputs.resourceId
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
}

// ---------------------------------------------------------------------------
// 9. Azure Front Door Premium — Latency-Based Inference API Routing
//
//    Routes api.agilecloud.ai traffic to the closest healthy inference region
//    using latency-based load balancing. Premium SKU enables WAF with managed
//    rule sets (DRS 2.1 + Bot Manager) and custom rate limiting.
//
//    Conditional on enableFrontDoor. Origins are added via inferenceApiOrigins
//    param — each prod AKS cluster's NGINX Ingress LB IP.
//
//    DNS CUTOVER: When enabling Front Door, manually delete the existing
//    api.agilecloud.ai A record before deploying:
//      az network dns record-set a delete -g rg-dai-platform-dev-eus2 \
//        -z agilecloud.ai -n api --yes
//    The CNAME to the Front Door endpoint is created automatically below.
//
//    SSE STREAMING: No cacheConfiguration or compression on the inference
//    route. Front Door passes through chunked/SSE responses transparently
//    when caching is disabled. Backend sets Content-Type: text/event-stream.
// ---------------------------------------------------------------------------

// ── 9a. WAF Policy ──────────────────────────────────────────────────

resource wafPolicy 'Microsoft.Network/FrontDoorWebApplicationFirewallPolicies@2024-02-01' = if (enableFrontDoor) {
  name: wafPolicyName
  location: 'global'
  tags: defaultTags
  sku: {
    name: 'Premium_AzureFrontDoor'
  }
  properties: {
    policySettings: {
      enabledState: 'Enabled'
      mode: 'Prevention'
      requestBodyCheck: 'Enabled'
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetType: 'Microsoft_DefaultRuleSet'
          ruleSetVersion: '2.1'
          ruleSetAction: 'Block'
        }
        {
          ruleSetType: 'Microsoft_BotManagerRuleSet'
          ruleSetVersion: '1.0'
        }
      ]
    }
    customRules: {
      rules: [
        {
          name: 'RateLimitInferenceAPI'
          priority: 100
          ruleType: 'RateLimitRule'
          action: 'Block'
          enabledState: 'Enabled'
          rateLimitDurationInMinutes: 1
          rateLimitThreshold: 1000 // 1000 req/min per IP — coarse edge limit; fine-grained per-key in API server
          matchConditions: [
            {
              matchVariable: 'RequestUri'
              operator: 'Contains'
              matchValue: ['/v1/']
              negateCondition: false
              transforms: []
            }
          ]
        }
      ]
    }
  }
}

// ── 9b. Front Door Profile ──────────────────────────────────────────

resource frontDoorProfile 'Microsoft.Cdn/profiles@2024-09-01' = if (enableFrontDoor) {
  name: frontDoorName
  location: 'global'
  tags: defaultTags
  sku: {
    name: 'Premium_AzureFrontDoor'
  }
  properties: {
    originResponseTimeoutSeconds: 300 // Inference can be slow for large contexts
  }
}

// ── 9c. AFD Endpoint ────────────────────────────────────────────────

resource frontDoorEndpoint 'Microsoft.Cdn/profiles/afdEndpoints@2024-09-01' = if (enableFrontDoor) {
  parent: frontDoorProfile
  name: 'ep-inference'
  location: 'global'
  tags: defaultTags
  properties: {
    enabledState: 'Enabled'
  }
}

// ── 9d. Origin Group — latency-based routing across inference regions ──

resource frontDoorOriginGroup 'Microsoft.Cdn/profiles/originGroups@2024-09-01' = if (enableFrontDoor) {
  parent: frontDoorProfile
  name: 'og-inference'
  properties: {
    loadBalancingSettings: {
      additionalLatencyInMilliseconds: 50 // 50ms tolerance for latency routing
      sampleSize: 4
      successfulSamplesRequired: 3
    }
    healthProbeSettings: {
      probePath: '/readyz'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 30
      probeRequestType: 'GET'
    }
    sessionAffinityState: 'Disabled'
    trafficRestorationTimeToHealedOrNewEndpointsInMinutes: 5
  }
}

// ── 9e. Origins — one per inference region ──────────────────────────

resource frontDoorOrigins 'Microsoft.Cdn/profiles/originGroups/origins@2024-09-01' = [for (origin, i) in inferenceApiOrigins: if (enableFrontDoor) {
  parent: frontDoorOriginGroup
  name: 'origin-${origin.region}'
  properties: {
    hostName: origin.hostname
    httpPort: 80
    httpsPort: 443
    originHostHeader: 'api.${dnsZoneName}'
    priority: 1 // All origins equal priority — latency decides
    weight: 1000
    enabledState: 'Enabled'
    enforceCertificateNameCheck: true
  }
}]

// ── 9f. Custom Domain — api.agilecloud.ai with managed TLS cert ────

resource frontDoorCustomDomain 'Microsoft.Cdn/profiles/customDomains@2024-09-01' = if (enableFrontDoor && enableDnsZone) {
  parent: frontDoorProfile
  name: 'api-agilecloud-ai'
  properties: {
    hostName: 'api.${dnsZoneName}'
    tlsSettings: {
      certificateType: 'ManagedCertificate'
      minimumTlsVersion: 'TLS12'
    }
    azureDnsZone: {
      id: dnsZone.id
    }
  }
}

// ── 9g. Route — forwards all /v1/* traffic to inference origins ─────
//    No cacheConfiguration: inference is real-time, every response unique.
//    No compression: SSE streaming must not be buffered by Front Door.

resource frontDoorRoute 'Microsoft.Cdn/profiles/afdEndpoints/routes@2024-09-01' = if (enableFrontDoor) {
  parent: frontDoorEndpoint
  name: 'route-inference-api'
  properties: {
    customDomains: (enableFrontDoor && enableDnsZone) ? [
      { id: frontDoorCustomDomain!.id }
    ] : []
    originGroup: { id: frontDoorOriginGroup!.id }
    supportedProtocols: [ 'Http', 'Https' ]
    patternsToMatch: [ '/*' ]
    forwardingProtocol: 'HttpsOnly'
    httpsRedirect: 'Enabled'
    linkToDefaultDomain: 'Enabled'
  }
  dependsOn: [frontDoorOrigins] // Origins must exist before route
}

// ── 9h. Security Policy — associates WAF with the endpoint ─────────

resource frontDoorSecurityPolicy 'Microsoft.Cdn/profiles/securityPolicies@2024-09-01' = if (enableFrontDoor) {
  parent: frontDoorProfile
  name: 'secpol-waf'
  properties: {
    parameters: {
      type: 'WebApplicationFirewall'
      wafPolicy: { id: wafPolicy!.id }
      associations: [
        {
          domains: concat(
            (enableFrontDoor && enableDnsZone) ? [{ id: frontDoorCustomDomain!.id }] : [],
            [{ id: frontDoorEndpoint!.id }]
          )
          patternsToMatch: [ '/*' ]
        }
      ]
    }
  }
}

// ── 9i. DNS CNAME — api.agilecloud.ai → Front Door endpoint ────────
//    Replaces the A record when Front Door is enabled.
//    IMPORTANT: Delete the existing A record manually before first deploy.

resource dnsRecordApiFrontDoor 'Microsoft.Network/dnsZones/CNAME@2023-07-01-preview' = if (enableDnsZone && enableFrontDoor) {
  parent: dnsZone
  name: 'api'
  properties: {
    TTL: 300
    CNAMERecord: {
      cname: frontDoorEndpoint.properties.hostName
    }
  }
}

// ── 9j. Front Door Diagnostics ──────────────────────────────────────

resource frontDoorDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableFrontDoor) {
  name: 'diag-${frontDoorName}'
  scope: frontDoorProfile
  properties: {
    workspaceId: logAnalytics.outputs.resourceId
    logs: [
      { category: 'FrontDoorAccessLog', enabled: true }
      { category: 'FrontDoorHealthProbeLog', enabled: true }
      { category: 'FrontDoorWebApplicationFirewallLog', enabled: true }
    ]
    metrics: [{ category: 'AllMetrics', enabled: true }]
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

// --- Platform PostgreSQL outputs ---

@description('Platform PostgreSQL server FQDN.')
output platformDbFqdn string = enablePlatformDb ? platformDb.outputs.fqdn : ''

@description('Platform PostgreSQL server name.')
output platformDbName string = enablePlatformDb ? platformDb.outputs.name : ''

@description('Platform PostgreSQL server resource ID.')
output platformDbResourceId string = enablePlatformDb ? platformDb.outputs.resourceId : ''

// --- Content Safety outputs ---

@description('Azure AI Content Safety endpoint URL.')
output contentSafetyEndpoint string = enableContentSafety ? contentSafety!.properties.endpoint : ''

@description('Azure AI Content Safety resource name.')
output contentSafetyName string = enableContentSafety ? contentSafety!.name : ''

@description('Azure AI Content Safety resource ID.')
output contentSafetyResourceId string = enableContentSafety ? contentSafety!.id : ''

// --- Front Door outputs ---

@description('Front Door profile name.')
output frontDoorName string = enableFrontDoor ? frontDoorProfile!.name : ''

@description('Front Door profile resource ID.')
output frontDoorResourceId string = enableFrontDoor ? frontDoorProfile!.id : ''

@description('Front Door endpoint hostname (e.g., ep-inference-xxxxxxxx.z01.azurefd.net).')
output frontDoorEndpointHostName string = enableFrontDoor ? frontDoorEndpoint!.properties.hostName : ''

@description('WAF policy resource ID.')
output wafPolicyResourceId string = enableFrontDoor ? wafPolicy!.id : ''

// --- Audit Storage outputs ---

@description('Audit storage account name.')
output auditStorageAccountName string = enableAuditStorage ? auditStorage!.name : ''

@description('Audit storage account resource ID.')
output auditStorageAccountResourceId string = enableAuditStorage ? auditStorage!.id : ''
