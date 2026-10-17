param location string
param name string
param tags object

@secure()
param storageConnectionString string

@secure()
param appInsightsConnectionString string

param keyVaultName string
param openAiEndpoint string
param openAiDeploymentName string
param openAiApiVersion string
param tableEndpoint string
param contentShareName string

resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: '${name}-plan'
  location: location
  tags: tags
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

var keyVaultReferencePrefix = '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName='

resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: name
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    clientAffinityEnabled: false
    publicNetworkAccess: 'Enabled'
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: storageConnectionString
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: storageConnectionString
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: contentShareName
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'AzureWebJobsFeatureFlags'
          value: 'EnableWorkerIndexing'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        {
          name: 'LLM_BACKEND'
          value: 'azure'
        }
        {
          name: 'STORAGE_BACKEND'
          value: 'table'
        }
        {
          name: 'USE_MANAGED_IDENTITY'
          value: 'true'
        }
        {
          name: 'SEED_SAMPLE_DATA'
          value: 'true'
        }
        {
          name: 'KEY_VAULT_URL'
          value: 'https://${keyVaultName}${environment().suffixes.keyvaultDns}/'
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: openAiEndpoint
        }
        {
          name: 'AZURE_OPENAI_DEPLOYMENT'
          value: openAiDeploymentName
        }
        {
          name: 'AZURE_OPENAI_API_VERSION'
          value: openAiApiVersion
        }
        {
          name: 'STORAGE_ACCOUNT_URL'
          value: tableEndpoint
        }
        {
          name: 'AZURE_OPENAI_API_KEY'
          value: '${keyVaultReferencePrefix}azure-openai-api-key)'
        }
        {
          name: 'STORAGE_CONNECTION_STRING'
          value: '${keyVaultReferencePrefix}storage-connection-string)'
        }
      ]
    }
  }
}

output id string = functionApp.id
output name string = functionApp.name
output principalId string = functionApp.identity.principalId
output defaultHostName string = functionApp.properties.defaultHostName
