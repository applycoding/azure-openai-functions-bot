// Portfolio demo infrastructure. CI compiles this file. This repo does not deploy it.
targetScope = 'resourceGroup'

@description('Region for the Function App, storage, Key Vault, and Application Insights.')
param location string = resourceGroup().location

@description('Region for Azure OpenAI. The resource group region is not always an OpenAI region.')
param openAiLocation string = 'eastus'

@maxLength(8)
@description('Optional lowercase prefix, up to 8 characters. A unique suffix is always added.')
param namePrefix string = ''

@description('Azure OpenAI deployment name. The Function App sends chat requests to this deployment.')
param openAiDeploymentName string = 'gpt-4o-mini'

@description('Azure OpenAI model name. Confirm the model is available in openAiLocation before deploying.')
param openAiModelName string = 'gpt-4o-mini'

@description('Azure OpenAI model version. Confirm the version is available in openAiLocation before deploying.')
param openAiModelVersion string = '2024-07-18'

@description('Deployment SKU. gpt-4o-mini commonly uses GlobalStandard.')
param openAiSkuName string = 'GlobalStandard'

@description('Deployment capacity units requested for the model. Confirm subscription quota before deploying.')
param openAiCapacity int = 10

@description('Chat Completions API version used by the openai SDK AzureOpenAI client.')
param openAiApiVersion string = '2024-10-21'

param tags object = {
  project: 'azure-openai-functions-bot'
  purpose: 'portfolio-demo'
}

var prefix = take('${toLower(namePrefix)}${uniqueString(resourceGroup().id)}', 13)
var storageAccountName = take('${prefix}st', 24)
var keyVaultName = take('${prefix}kv', 24)
var openAiAccountName = take('${prefix}oai', 24)
var functionAppName = take('${prefix}-func', 60)
var appInsightsName = take('${prefix}-ai', 60)
var workspaceName = take('${prefix}-logs', 60)
var contentShareName = take('${prefix}-content', 63)

// Built-in role definition ids.
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
var storageTableDataContributorRoleId = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    name: storageAccountName
    location: location
    tags: tags
  }
}

module openai 'modules/openai.bicep' = {
  name: 'openai'
  params: {
    name: openAiAccountName
    location: openAiLocation
    deploymentName: openAiDeploymentName
    modelName: openAiModelName
    modelVersion: openAiModelVersion
    skuName: openAiSkuName
    capacity: openAiCapacity
    tags: tags
  }
}

module keyVault 'modules/keyVault.bicep' = {
  name: 'keyVault'
  params: {
    name: keyVaultName
    location: location
    tags: tags
    openAiApiKey: openai.outputs.primaryKey
    storageConnectionString: storage.outputs.connectionString
  }
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    workspaceName: workspaceName
    appInsightsName: appInsightsName
    tags: tags
  }
}

module functionApp 'modules/functionApp.bicep' = {
  name: 'functionApp'
  params: {
    location: location
    name: functionAppName
    tags: tags
    storageConnectionString: storage.outputs.connectionString
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    keyVaultName: keyVaultName
    openAiEndpoint: openai.outputs.endpoint
    openAiDeploymentName: openai.outputs.deploymentName
    openAiApiVersion: openAiApiVersion
    tableEndpoint: storage.outputs.tableEndpoint
    contentShareName: contentShareName
  }
  dependsOn: [
    keyVault
  ]
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openAiAccountName
}

resource tableDataRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountName, functionAppName, storageTableDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageTableDataContributorRoleId)
    principalId: functionApp.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

resource keyVaultSecretsRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVaultName, functionAppName, keyVaultSecretsUserRoleId)
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: functionApp.outputs.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    keyVault
  ]
}

resource openAiUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAiAccountName, functionAppName, cognitiveServicesOpenAIUserRoleId)
  scope: openAiAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
    principalId: functionApp.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

output functionAppName string = functionApp.outputs.name
output functionHostName string = functionApp.outputs.defaultHostName
output keyVaultUri string = keyVault.outputs.uri
output openAiEndpoint string = openai.outputs.endpoint
output openAiDeploymentName string = openai.outputs.deploymentName
output storageAccountName string = storage.outputs.name
