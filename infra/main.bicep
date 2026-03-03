// ============================================================================
// DirectAI Regional Stamp — main.bicep
// Deploys the complete set of Azure resources for a DirectAI inference region.
// Uses Azure Verified Modules (AVM) from the Bicep public registry.
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
param kubernetesVersion string = '1.30'

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

@description('Enable Private Endpoints for Storage, Key Vault, and ACR. Strongly recommended for all environments. Disable only if dev subscription lacks Private DNS Zone support.')
param enablePrivateEndpoints bool = true

@description('AKS system pool min node count.')
param systemPoolMinCount int = 1

@description('AKS system pool max node count.')
param systemPoolMaxCount int = 3

@description('Customer identifier (GUID for onboarded customers, or alias like "internal" for platform stamps).')
param customerId string

@description('Platform ACR login server (e.g., acrplatform.azurecr.io). When provided, the stamp skips deploying its own ACR and uses the platform ACR instead. Leave empty to deploy a per-customer ACR.')
param platformAcrLoginServer string = ''

// ---------------------------------------------------------------------------
// Naming convention: dai-{customer}-{resource}-{env}-{regionShort}
// ---------------------------------------------------------------------------

var prefix = 'dai'
var baseName = '${prefix}-${customerId}-${environment}-${regionShort}'
var uniqueSuffix = uniqueString(resourceGroup().id, baseName)
var customerHash = take(uniqueString(customerId), 8) // Deterministic 8-char hash for length-constrained names
var deployPerCustomerAcr = empty(platformAcrLoginServer)

var identityControlPlaneName = 'id-cp-${baseName}'
var identityKubeletName = 'id-kubelet-${baseName}'
var logAnalyticsName = 'log-${baseName}'
var appInsightsName = 'appi-${baseName}'
var vnetName = 'vnet-${baseName}'
var keyVaultName = 'kv${prefix}${customerHash}${take(uniqueSuffix, 6)}' // 3-24 chars
var storageAccountName = 'st${prefix}${customerHash}${take(uniqueSuffix, 6)}' // 3-24 chars
var acrName = 'acr${prefix}${customerHash}${take(uniqueSuffix, 6)}' // 5-50 chars
var aksName = 'aks-${baseName}'

var defaultTags = union(tags, {
  project: 'directai'
  'customer-id': customerId
  environment: environment
  region: regionShort
  'managed-by': 'bicep'
})

// ---------------------------------------------------------------------------
// 1a. Control Plane Identity — used by AKS resource provider
//     Does NOT get data-plane access to Storage/ACR/KV.
// ---------------------------------------------------------------------------

module identityControlPlane 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.0' = {
  name: 'identityControlPlane'
  params: {
    name: identityControlPlaneName
    location: location
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// 1b. Kubelet Identity — assigned to VMSS nodes via identityProfile
//     Least-privilege: pull images, read blobs/secrets. NO write access to KV.
//     Control plane gets Managed Identity Operator here so AKS can assign
//     this identity to the underlying VMSS node pools.
// ---------------------------------------------------------------------------

module identityKubelet 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.0' = {
  name: 'identityKubelet'
  params: {
    name: identityKubeletName
    location: location
    tags: defaultTags
    roleAssignments: [
      {
        principalId: identityControlPlane.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'Managed Identity Operator'
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// 2. Log Analytics Workspace — observability sink for AKS and all resources
// ---------------------------------------------------------------------------

module logAnalytics 'br/public:avm/res/operational-insights/workspace:0.9.1' = {
  name: 'logAnalytics'
  params: {
    name: logAnalyticsName
    location: location
    skuName: 'PerGB2018'
    dataRetention: environment == 'prod' ? 90 : 30
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// 2b. Application Insights — centralized distributed tracing + live metrics
//     Workspace-based (backed by Log Analytics above). Connection string is
//     stored in Key Vault for pods to consume via CSI SecretProviderClass.
// ---------------------------------------------------------------------------

module appInsights 'br/public:avm/res/insights/component:0.4.2' = {
  name: 'appInsights'
  params: {
    name: appInsightsName
    workspaceResourceId: logAnalytics.outputs.resourceId
    location: location
    applicationType: 'web'
    retentionInDays: environment == 'prod' ? 90 : 30
    disableLocalAuth: true
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// 3a. Network Security Group — endpoints subnet
//     Restricts inbound traffic to VNet-internal only. AKS subnet does NOT
//     get a custom NSG — AKS manages its own and custom NSGs conflict.
// ---------------------------------------------------------------------------

module nsgEndpoints 'br/public:avm/res/network/network-security-group:0.5.0' = if (enablePrivateEndpoints) {
  name: 'nsgEndpoints'
  params: {
    name: 'nsg-snet-endpoints-${baseName}'
    location: location
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
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// 3b. Virtual Network — AKS nodes + private endpoints
// ---------------------------------------------------------------------------

module vnet 'br/public:avm/res/network/virtual-network:0.5.2' = {
  name: 'vnet'
  params: {
    name: vnetName
    location: location
    addressPrefixes: [vnetAddressPrefix]
    subnets: [
      {
        name: 'snet-aks'
        addressPrefix: aksSubnetPrefix
        // No NSG — AKS manages its own NSG on the node subnet.
      }
      {
        name: 'snet-endpoints'
        addressPrefix: endpointsSubnetPrefix
        privateEndpointNetworkPolicies: 'Disabled'
        networkSecurityGroupResourceId: enablePrivateEndpoints ? nsgEndpoints!.outputs.resourceId : null
      }
    ]
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
// 3c. Private DNS Zones — required for Private Endpoints to resolve
//     Zone names are Azure-mandated for each PaaS service.
// ---------------------------------------------------------------------------

module dnsZoneBlob 'br/public:avm/res/network/private-dns-zone:0.7.0' = if (enablePrivateEndpoints) {
  name: 'dnsZoneBlob'
  params: {
    name: 'privatelink.blob.${az.environment().suffixes.storage}'
    location: 'global'
    virtualNetworkLinks: [
      {
        virtualNetworkResourceId: vnet.outputs.resourceId
        registrationEnabled: false
      }
    ]
    tags: defaultTags
  }
}

module dnsZoneVault 'br/public:avm/res/network/private-dns-zone:0.7.0' = if (enablePrivateEndpoints) {
  name: 'dnsZoneVault'
  params: {
    name: 'privatelink.vaultcore.azure.net'
    location: 'global'
    virtualNetworkLinks: [
      {
        virtualNetworkResourceId: vnet.outputs.resourceId
        registrationEnabled: false
      }
    ]
    tags: defaultTags
  }
}

module dnsZoneAcr 'br/public:avm/res/network/private-dns-zone:0.7.0' = if (enablePrivateEndpoints && deployPerCustomerAcr) {
  name: 'dnsZoneAcr'
  params: {
    name: 'privatelink.azurecr.io'
    location: 'global'
    virtualNetworkLinks: [
      {
        virtualNetworkResourceId: vnet.outputs.resourceId
        registrationEnabled: false
      }
    ]
    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// 4. Key Vault — secrets, API keys, model configs
// ---------------------------------------------------------------------------

module keyVault 'br/public:avm/res/key-vault/vault:0.11.1' = {
  name: 'keyVault'
  params: {
    name: keyVaultName
    location: location
    enableRbacAuthorization: true
    enablePurgeProtection: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    secrets: [
      {
        name: 'appinsights-connection-string'
        value: appInsights.outputs.connectionString
      }
    ]
    roleAssignments: [
      {
        principalId: identityKubelet.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'Key Vault Secrets User' // Read-only — kubelet should never write secrets
      }
    ]
    privateEndpoints: enablePrivateEndpoints
      ? [
          {
            service: 'vault'
            subnetResourceId: vnet.outputs.subnetResourceIds[1]
            privateDnsZoneGroup: {
              privateDnsZoneGroupConfigs: [
                {
                  privateDnsZoneResourceId: dnsZoneVault!.outputs.resourceId
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
// 5. Storage Account — model weights, compiled engines, checkpoints
//    Identity gets Storage Blob Data Contributor for pull/push.
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
        { name: 'models', publicAccess: 'None' }
        { name: 'engines', publicAccess: 'None' }
        { name: 'checkpoints', publicAccess: 'None' }
        { name: 'configs', publicAccess: 'None' }
      ]
    }
    roleAssignments: [
      {
        principalId: identityKubelet.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'Storage Blob Data Contributor' // Kubelet needs write for checkpoint uploads
      }
    ]
    privateEndpoints: enablePrivateEndpoints
      ? [
          {
            service: 'blob'
            subnetResourceId: vnet.outputs.subnetResourceIds[1]
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
// 6. Container Registry — inference server images
//    Deployed per-customer ONLY when no platform ACR is provided.
//    Commercial customers use the shared platform ACR (cross-sub AcrPull).
//    Gov/air-gapped customers deploy their own (no cross-cloud access).
// ---------------------------------------------------------------------------

module acr 'br/public:avm/res/container-registry/registry:0.6.0' = if (deployPerCustomerAcr) {
  name: 'acr'
  params: {
    name: acrName
    location: location
    acrSku: environment == 'prod' ? 'Premium' : 'Basic'
    roleAssignments: [
      {
        principalId: identityKubelet.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'AcrPull'
      }
    ]
    privateEndpoints: enablePrivateEndpoints
      ? [
          {
            service: 'registry'
            subnetResourceId: vnet.outputs.subnetResourceIds[1]
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
// 7. AKS Cluster — inference orchestration
//    - Azure CNI Overlay (pod IPs separate from VNet)
//    - OIDC + Workload Identity for pod-level auth
//    - KEDA for request-based autoscaling
//    - Key Vault Secrets Provider CSI driver
//    - Blob CSI driver for model weight mounts
//    - System pool tainted for system workloads only
//    - GPU node pools added conditionally
// ---------------------------------------------------------------------------

var gpuAgentPools = enableGpuPools
  ? [
      // A100 80GB pool — large LLMs and STT (TP up to 8-way)
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
        vnetSubnetResourceId: vnet.outputs.subnetResourceIds[0]
        nodeLabels: {
          'directai.io/gpu-pool': 'a100'
          'directai.io/pool': 'inference'
        }
        nodeTaints: ['nvidia.com/gpu=a100:NoSchedule']
      }
      // H100 80GB pool — highest throughput (TP up to 8-way)
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
        vnetSubnetResourceId: vnet.outputs.subnetResourceIds[0]
        nodeLabels: {
          'directai.io/gpu-pool': 'h100'
          'directai.io/pool': 'inference'
        }
        nodeTaints: ['nvidia.com/gpu=h100:NoSchedule']
      }
      // Embeddings/reranking pool — smaller GPUs, no NVMe required
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
        vnetSubnetResourceId: vnet.outputs.subnetResourceIds[0]
        nodeLabels: {
          'directai.io/gpu-pool': 'embeddings'
          'directai.io/pool': 'embeddings'
        }
        nodeTaints: ['directai.io/workload=embeddings:NoSchedule']
      }
    ]
  : []

module aks 'br/public:avm/res/container-service/managed-cluster:0.5.3' = {
  name: 'aks'
  params: {
    name: aksName
    location: location
    kubernetesVersion: kubernetesVersion
    skuTier: environment == 'prod' ? 'Standard' : 'Free'

    // Identity — split for least privilege
    // Control plane identity: cluster management operations
    managedIdentities: {
      userAssignedResourcesIds: [identityControlPlane.outputs.resourceId]
    }
    // Kubelet identity: node-level operations (image pull, blob mount, secret read)
    identityProfile: {
      kubeletidentity: {
        resourceId: identityKubelet.outputs.resourceId
      }
    }

    // AAD integration — Azure RBAC for K8s authz
    aadProfile: {
      aadProfileEnableAzureRBAC: true
      aadProfileManaged: true
    }
    disableLocalAccounts: true

    // Networking — Azure CNI Overlay (pod IPs decoupled from VNet)
    networkPlugin: 'azure'
    networkPluginMode: 'overlay'
    networkDataplane: 'azure'
    networkPolicy: 'azure'
    dnsServiceIP: '10.10.200.10'
    serviceCidr: '10.10.200.0/24'

    // System node pool
    primaryAgentPoolProfiles: [
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
        availabilityZones: environment == 'prod' ? [1, 2, 3] : [1]
        vnetSubnetResourceId: vnet.outputs.subnetResourceIds[0]
        nodeTaints: ['CriticalAddonsOnly=true:NoSchedule']
      }
    ]

    // GPU node pools (conditional)
    agentPools: gpuAgentPools

    // Add-ons — KEDA, KV secrets, Blob CSI, OIDC, Workload Identity
    kedaAddon: true
    enableKeyvaultSecretsProvider: true
    enableSecretRotation: true
    enableOidcIssuerProfile: true
    enableWorkloadIdentity: true
    enableStorageProfileBlobCSIDriver: true
    enableStorageProfileDiskCSIDriver: true

    // Monitoring
    omsAgentEnabled: true
    monitoringWorkspaceResourceId: logAnalytics.outputs.resourceId
    enableAzureMonitorProfileMetrics: true

    // Auto-upgrade
    autoUpgradeProfileUpgradeChannel: 'stable'
    autoNodeOsUpgradeProfileUpgradeChannel: 'SecurityPatch'

    // Maintenance windows
    maintenanceConfigurations: [
      {
        name: 'aksManagedAutoUpgradeSchedule'
        maintenanceWindow: {
          durationHours: 4
          schedule: { weekly: { dayOfWeek: 'Sunday', intervalWeeks: 1 } }
          startDate: '2025-01-01'
          startTime: '04:00'
          utcOffset: '+00:00'
        }
      }
      {
        name: 'aksManagedNodeOSUpgradeSchedule'
        maintenanceWindow: {
          durationHours: 4
          schedule: { weekly: { dayOfWeek: 'Sunday', intervalWeeks: 1 } }
          startDate: '2025-01-01'
          startTime: '04:00'
          utcOffset: '+00:00'
        }
      }
    ]

    // Diagnostics
    diagnosticSettings: [
      {
        workspaceResourceId: logAnalytics.outputs.resourceId
        logCategoriesAndGroups: [
          { category: 'kube-apiserver' }
          { category: 'kube-controller-manager' }
          { category: 'kube-scheduler' }
          { category: 'cluster-autoscaler' }
          { category: 'kube-audit-admin' }
          { category: 'guard' }
        ]
        metricCategories: [{ category: 'AllMetrics' }]
      }
    ]

    tags: defaultTags
  }
}

// ---------------------------------------------------------------------------
// 8. Federated Identity Credential — Workload Identity for K8s pods
//    Links the kubelet managed identity to the AKS OIDC issuer.
//    Pods in the "directai" namespace using the "directai" ServiceAccount
//    (annotated with azure.workload.identity/client-id) can authenticate
//    as this identity to access Blob Storage, Key Vault, etc.
// ---------------------------------------------------------------------------

resource existingKubeletIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: identityKubeletName
}

resource kubeletFederatedCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: existingKubeletIdentity
  name: 'fic-aks-directai'
  properties: {
    issuer: aks.outputs.oidcIssuerUrl
    subject: 'system:serviceaccount:directai:directai'
    audiences: ['api://AzureADTokenExchange']
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('AKS cluster name.')
output aksName string = aks.outputs.name

@description('AKS cluster resource ID.')
output aksResourceId string = aks.outputs.resourceId

@description('AKS OIDC issuer URL for workload identity federation.')
output aksOidcIssuerUrl string = aks.outputs.oidcIssuerUrl

@description('AKS control plane FQDN.')
output aksControlPlaneFqdn string = aks.outputs.controlPlaneFQDN

@description('Storage account name for model weights and engines.')
output storageAccountName string = storage.outputs.name

@description('ACR login server for inference images. Per-customer ACR when deployed, otherwise platform ACR.')
output acrLoginServer string = deployPerCustomerAcr ? acr!.outputs.loginServer : platformAcrLoginServer

@description('Key Vault URI.')
output keyVaultUri string = keyVault.outputs.uri

@description('Log Analytics workspace resource ID.')
output logAnalyticsWorkspaceId string = logAnalytics.outputs.resourceId

@description('Control plane identity principal ID.')
output controlPlaneIdentityPrincipalId string = identityControlPlane.outputs.principalId

@description('Control plane identity client ID.')
output controlPlaneIdentityClientId string = identityControlPlane.outputs.clientId

@description('Kubelet identity principal ID.')
output kubeletIdentityPrincipalId string = identityKubelet.outputs.principalId

@description('Kubelet identity client ID.')
output kubeletIdentityClientId string = identityKubelet.outputs.clientId

@description('Application Insights connection string.')
output appInsightsConnectionString string = appInsights.outputs.connectionString

@description('Application Insights resource ID.')
output appInsightsResourceId string = appInsights.outputs.resourceId
