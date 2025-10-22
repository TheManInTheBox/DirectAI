// Main infrastructure deployment for DirectAI Music Platform
// B2C SaaS multi-tenant architecture with Container Apps

targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment (e.g., dev, staging, prod)')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Name of the resource group')
param resourceGroupName string = 'rg-${environmentName}'

@description('PostgreSQL administrator login username')
@secure()
param databaseAdminUsername string

@description('PostgreSQL administrator password')
@secure()
param databaseAdminPassword string

// Resource group
resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: {
    'azd-env-name': environmentName
    environment: environmentName
    project: 'directai-music-platform'
  }
}

// Deploy core infrastructure
module resources 'resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    environmentName: environmentName
    location: location
    databaseAdminUsername: databaseAdminUsername
    databaseAdminPassword: databaseAdminPassword
  }
}

// Outputs required by azd
output RESOURCE_GROUP_ID string = rg.id
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.AZURE_CONTAINER_REGISTRY_ENDPOINT
output AZURE_CONTAINER_REGISTRY_NAME string = resources.outputs.AZURE_CONTAINER_REGISTRY_NAME
output API_ENDPOINT string = resources.outputs.API_ENDPOINT
output DATABASE_HOST string = resources.outputs.DATABASE_HOST
output STORAGE_ACCOUNT_NAME string = resources.outputs.STORAGE_ACCOUNT_NAME
output SERVICE_BUS_NAMESPACE string = resources.outputs.SERVICE_BUS_NAMESPACE
output KEY_VAULT_NAME string = resources.outputs.KEY_VAULT_NAME
