// ============================================================================
// DNS A Record — Customer Subdomain
//
// Creates an A record in the platform DNS zone for a customer stamp.
// Deployed to the PLATFORM resource group (operations subscription) as a
// cross-subscription module invocation from deploy-stamp.yml.
//
// Example: acme.agilecloud.ai → 48.192.177.54
// ============================================================================

targetScope = 'resourceGroup'

@description('Name of the existing DNS zone (e.g., agilecloud.ai).')
param dnsZoneName string

@description('Subdomain record name (e.g., "internal" creates internal.agilecloud.ai).')
param recordName string

@description('IPv4 address of the customer stamp ingress load balancer.')
param ipAddress string

@description('TTL in seconds for the A record.')
param ttl int = 300

// Reference the existing DNS zone in this resource group
resource dnsZone 'Microsoft.Network/dnsZones@2023-07-01-preview' existing = {
  name: dnsZoneName
}

resource aRecord 'Microsoft.Network/dnsZones/A@2023-07-01-preview' = {
  parent: dnsZone
  name: recordName
  properties: {
    TTL: ttl
    ARecords: [
      { ipv4Address: ipAddress }
    ]
  }
}

output fqdn string = '${recordName}.${dnsZoneName}'
output recordId string = aRecord.id
