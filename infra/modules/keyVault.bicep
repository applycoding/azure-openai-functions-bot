param name string
param location string
param tags object

@secure()
param openAiApiKey string

@secure()
param storageConnectionString string

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
    tenantId: tenant().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource openAiApiKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'azure-openai-api-key'
  properties: {
    value: openAiApiKey
  }
}

resource storageConnectionSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'storage-connection-string'
  properties: {
    value: storageConnectionString
  }
}

output id string = vault.id
output name string = vault.name
output uri string = vault.properties.vaultUri
