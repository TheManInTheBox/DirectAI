// ============================================================================
// ACR Role Assignment Module
//
// Assigns AcrPull role to a principal on a given Container Registry.
// Used for cross-resource role assignments where the ACR is deployed
// via an AVM module and can't have scoped role assignments added
// directly in the same template.
// ============================================================================

@description('Name of the existing Container Registry.')
param acrName string

@description('Principal ID to assign AcrPull role.')
param principalId string

@description('Principal type for the role assignment.')
@allowed(['ServicePrincipal', 'Group', 'User'])
param principalType string = 'ServicePrincipal'

var acrPullRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: acrName
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, principalId, acrPullRoleId)
  scope: acr
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: acrPullRoleId
  }
}
