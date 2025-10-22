// Core infrastructure resources for DirectAI Music Platform
// Includes Container Apps, PostgreSQL, Storage, Service Bus, Key Vault, Monitoring

@minLength(1)
@maxLength(64)
param environmentName string

@minLength(1)
param location string = resourceGroup().location

@secure()
param databaseAdminUsername string

@secure()
param databaseAdminPassword string

// Generate unique token for resource naming
var resourceToken = uniqueString(subscription().id, resourceGroup().id, location, environmentName)
var tags = {
  environment: environmentName
  project: 'directai-music-platform'
}

// ===== Managed Identity =====
resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'azmi${resourceToken}'
  location: location
  tags: tags
}

// ===== Container Registry =====
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'azcr${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

// AcrPull role assignment for managed identity (REQUIRED by azd rules)
resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, managedIdentity.id, 'acrPull')
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d') // AcrPull
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ===== Log Analytics Workspace =====
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'azla${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ===== Application Insights =====
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'azai${resourceToken}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ===== Storage Account =====
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'azst${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false // Disable key access (use Managed Identity)
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

// Blob container for audio files
resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: '${storageAccount.name}/default/audio-files'
  properties: {
    publicAccess: 'None'
  }
}

// Storage Blob Data Contributor role for managed identity
resource storageBlobContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, managedIdentity.id, 'storageBlobContributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ===== Service Bus =====
resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: 'azsb${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    minimumTlsVersion: '1.2'
  }
}

// Analysis jobs queue
resource analysisQueue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = {
  name: 'analysis-jobs'
  parent: serviceBusNamespace
  properties: {
    maxSizeInMegabytes: 5120
    defaultMessageTimeToLive: 'P14D'
    deadLetteringOnMessageExpiration: true
    lockDuration: 'PT5M'
  }
}

// Generation jobs queue
resource generationQueue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = {
  name: 'generation-jobs'
  parent: serviceBusNamespace
  properties: {
    maxSizeInMegabytes: 5120
    defaultMessageTimeToLive: 'P14D'
    deadLetteringOnMessageExpiration: true
    lockDuration: 'PT5M'
  }
}

// Training jobs queue
resource trainingQueue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = {
  name: 'training-jobs'
  parent: serviceBusNamespace
  properties: {
    maxSizeInMegabytes: 5120
    defaultMessageTimeToLive: 'P14D'
    deadLetteringOnMessageExpiration: true
    lockDuration: 'PT5M'
  }
}

// Service Bus Data Receiver role for managed identity
resource serviceBusReceiverRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(serviceBusNamespace.id, managedIdentity.id, 'serviceBusReceiver')
  scope: serviceBusNamespace
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0') // Azure Service Bus Data Receiver
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Service Bus Data Sender role for managed identity
resource serviceBusSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(serviceBusNamespace.id, managedIdentity.id, 'serviceBusSender')
  scope: serviceBusNamespace
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39') // Azure Service Bus Data Sender
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ===== PostgreSQL Flexible Server =====
resource postgreSqlServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: 'azpg${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'Standard_B2s'
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: databaseAdminUsername
    administratorLoginPassword: databaseAdminPassword
    version: '16'
    storage: {
      storageSizeGB: 32
      autoGrow: 'Enabled'
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

// PostgreSQL database
resource postgreSqlDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  name: 'musicplatform'
  parent: postgreSqlServer
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// Allow Azure services firewall rule
resource postgreSqlFirewallRule 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  name: 'AllowAzureServices'
  parent: postgreSqlServer
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// ===== Key Vault =====
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'azkv${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
  }
}

// Key Vault Secrets User role for managed identity
resource keyVaultSecretsUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, managedIdentity.id, 'keyVaultSecretsUser')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Store database connection string in Key Vault
resource databaseConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'DatabaseConnectionString'
  parent: keyVault
  properties: {
    value: 'Host=${postgreSqlServer.properties.fullyQualifiedDomainName};Database=musicplatform;Username=${databaseAdminUsername};Password=${databaseAdminPassword};SSL Mode=Require'
  }
}

// Store storage connection string in Key Vault (using managed identity, so this is just the account name)
resource storageConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'StorageAccountName'
  parent: keyVault
  properties: {
    value: storageAccount.name
  }
}

// Store Service Bus namespace in Key Vault
resource serviceBusNamespaceSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'ServiceBusNamespace'
  parent: keyVault
  properties: {
    value: '${serviceBusNamespace.name}.servicebus.windows.net'
  }
}

// ===== Container Apps Environment =====
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'azce${resourceToken}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ===== Container Apps =====
// API Container App
resource apiContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'api-${resourceToken}'
  location: location
  tags: union(tags, {
    'azd-service-name': 'api'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'http'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']
          allowedHeaders: ['*']
        }
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: managedIdentity.id
        }
      ]
      secrets: [
        {
          name: 'database-connection-string'
          keyVaultUrl: databaseConnectionStringSecret.properties.secretUri
          identity: managedIdentity.id
        }
        {
          name: 'appinsights-connection-string'
          value: applicationInsights.properties.ConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: [
            {
              name: 'ASPNETCORE_ENVIRONMENT'
              value: 'Production'
            }
            {
              name: 'ConnectionStrings__DefaultConnection'
              secretRef: 'database-connection-string'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'appinsights-connection-string'
            }
            {
              name: 'AZURE_STORAGE_ACCOUNT_NAME'
              value: storageAccount.name
            }
            {
              name: 'BLOB_CONTAINER_NAME'
              value: 'audio-files'
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
              value: '${serviceBusNamespace.name}.servicebus.windows.net'
            }
            {
              name: 'ANALYSIS_QUEUE_NAME'
              value: 'analysis-jobs'
            }
            {
              name: 'GENERATION_QUEUE_NAME'
              value: 'generation-jobs'
            }
            {
              name: 'TRAINING_QUEUE_NAME'
              value: 'training-jobs'
            }
            {
              name: 'TRAINING_WORKER_URL'
              value: 'http://training-${resourceToken}'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
        rules: [
          {
            name: 'http-scale-rule'
            http: {
              metadata: {
                concurrentRequests: '100'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [
    acrPullRoleAssignment
  ]
}

// Analysis Worker Container App
resource analysisWorkerContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'analysis-${resourceToken}'
  location: location
  tags: union(tags, {
    'azd-service-name': 'analysis-worker'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: false
        targetPort: 8004
        transport: 'http'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: managedIdentity.id
        }
      ]
      secrets: [
        {
          name: 'database-connection-string'
          keyVaultUrl: databaseConnectionStringSecret.properties.secretUri
          identity: managedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'analysis-worker'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: [
            {
              name: 'AZURE_STORAGE_ACCOUNT_NAME'
              value: storageAccount.name
            }
            {
              name: 'BLOB_CONTAINER_NAME'
              value: 'audio-files'
            }
            {
              name: 'DATABASE_URL'
              secretRef: 'database-connection-string'
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
              value: '${serviceBusNamespace.name}.servicebus.windows.net'
            }
            {
              name: 'ANALYSIS_QUEUE_NAME'
              value: 'analysis-jobs'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 5
        rules: [
          {
            name: 'servicebus-scale-rule'
            custom: {
              type: 'azure-servicebus'
              metadata: {
                queueName: 'analysis-jobs'
                messageCount: '10'
                namespace: serviceBusNamespace.name
              }
              auth: [
                {
                  secretRef: 'servicebus-connection-string'
                  triggerParameter: 'connection'
                }
              ]
            }
          }
        ]
      }
    }
  }
  dependsOn: [
    acrPullRoleAssignment
  ]
}

// Generation Worker Container App
resource generationWorkerContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'generation-${resourceToken}'
  location: location
  tags: union(tags, {
    'azd-service-name': 'generation-worker'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: false
        targetPort: 8080
        transport: 'http'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: managedIdentity.id
        }
      ]
      secrets: [
        {
          name: 'database-connection-string'
          keyVaultUrl: databaseConnectionStringSecret.properties.secretUri
          identity: managedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'generation-worker'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: [
            {
              name: 'AZURE_STORAGE_ACCOUNT_NAME'
              value: storageAccount.name
            }
            {
              name: 'BLOB_CONTAINER_NAME'
              value: 'audio-files'
            }
            {
              name: 'DATABASE_URL'
              secretRef: 'database-connection-string'
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
              value: '${serviceBusNamespace.name}.servicebus.windows.net'
            }
            {
              name: 'GENERATION_QUEUE_NAME'
              value: 'generation-jobs'
            }
            {
              name: 'USE_GPU'
              value: 'false'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
        rules: [
          {
            name: 'servicebus-scale-rule'
            custom: {
              type: 'azure-servicebus'
              metadata: {
                queueName: 'generation-jobs'
                messageCount: '5'
                namespace: serviceBusNamespace.name
              }
              auth: [
                {
                  secretRef: 'servicebus-connection-string'
                  triggerParameter: 'connection'
                }
              ]
            }
          }
        ]
      }
    }
  }
  dependsOn: [
    acrPullRoleAssignment
  ]
}

// Training Worker Container App
resource trainingWorkerContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'training-${resourceToken}'
  location: location
  tags: union(tags, {
    'azd-service-name': 'training-worker'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: false
        targetPort: 8003
        transport: 'http'
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: managedIdentity.id
        }
      ]
      secrets: [
        {
          name: 'database-connection-string'
          keyVaultUrl: databaseConnectionStringSecret.properties.secretUri
          identity: managedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'training-worker'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: [
            {
              name: 'AZURE_STORAGE_ACCOUNT_NAME'
              value: storageAccount.name
            }
            {
              name: 'BLOB_CONTAINER_NAME'
              value: 'audio-files'
            }
            {
              name: 'DATABASE_URL'
              secretRef: 'database-connection-string'
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
              value: '${serviceBusNamespace.name}.servicebus.windows.net'
            }
            {
              name: 'TRAINING_QUEUE_NAME'
              value: 'training-jobs'
            }
            {
              name: 'USE_GPU'
              value: 'false'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
        rules: [
          {
            name: 'servicebus-scale-rule'
            custom: {
              type: 'azure-servicebus'
              metadata: {
                queueName: 'training-jobs'
                messageCount: '2'
                namespace: serviceBusNamespace.name
              }
              auth: [
                {
                  secretRef: 'servicebus-connection-string'
                  triggerParameter: 'connection'
                }
              ]
            }
          }
        ]
      }
    }
  }
  dependsOn: [
    acrPullRoleAssignment
  ]
}

// ===== Outputs =====
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.properties.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.name
output API_ENDPOINT string = 'https://${apiContainerApp.properties.configuration.ingress.fqdn}'
output DATABASE_HOST string = postgreSqlServer.properties.fullyQualifiedDomainName
output STORAGE_ACCOUNT_NAME string = storageAccount.name
output SERVICE_BUS_NAMESPACE string = '${serviceBusNamespace.name}.servicebus.windows.net'
output KEY_VAULT_NAME string = keyVault.name
output MANAGED_IDENTITY_CLIENT_ID string = managedIdentity.properties.clientId
output APPLICATION_INSIGHTS_CONNECTION_STRING string = applicationInsights.properties.ConnectionString
