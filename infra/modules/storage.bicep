param name string
param location string
param tags object

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Enabled'
  }
}

resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  name: 'default'
  parent: storage
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

resource tableServices 'Microsoft.Storage/storageAccounts/tableServices@2023-05-01' = {
  name: 'default'
  parent: storage
}

resource ordersTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = {
  name: 'orders'
  parent: tableServices
}

resource ticketsTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = {
  name: 'tickets'
  parent: tableServices
}

resource messagesTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = {
  name: 'messages'
  parent: tableServices
}

var connectionString = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'

output id string = storage.id
output name string = storage.name
output tableEndpoint string = storage.properties.primaryEndpoints.table

@secure()
output connectionString string = connectionString
