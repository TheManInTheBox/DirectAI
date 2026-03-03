// ============================================================================
// DirectAI Observability Workbook
// Azure Monitor Workbook with per-model latency, throughput, error rate,
// TTFT, inflight requests, GPU utilization, and node pool health.
// ============================================================================

@description('Azure region.')
param location string

@description('Log Analytics workspace resource ID.')
param logAnalyticsWorkspaceId string

@description('Application Insights resource ID.')
param appInsightsResourceId string

@description('Resource tags.')
param tags object = {}

// Workbook content — serialised JSON template.
// Uses Kusto queries against Log Analytics and App Insights.
var workbookContent = {
  version: 'Notebook/1.0'
  items: [
    // ── Section: Overview ──────────────────────────────────────────────
    {
      type: 1
      content: {
        json: '# DirectAI Inference Platform — Observability Dashboard\n\nReal-time metrics for all inference endpoints. Select a time range and model to drill down.'
      }
      name: 'header'
    }
    {
      type: 9
      content: {
        version: 'KqlParameterItem/1.0'
        parameters: [
          {
            id: 'timeRange'
            version: 'KqlParameterItem/1.0'
            name: 'TimeRange'
            type: 4
            isRequired: true
            value: { durationMs: 3600000 }
            typeSettings: {
              selectableValues: [
                { durationMs: 300000, displayName: 'Last 5 minutes' }
                { durationMs: 900000, displayName: 'Last 15 minutes' }
                { durationMs: 3600000, displayName: 'Last 1 hour' }
                { durationMs: 14400000, displayName: 'Last 4 hours' }
                { durationMs: 86400000, displayName: 'Last 24 hours' }
                { durationMs: 604800000, displayName: 'Last 7 days' }
              ]
            }
            label: 'Time Range'
          }
        ]
      }
      name: 'parameters'
    }
    // ── Section: Request Rate & Error Rate ─────────────────────────────
    {
      type: 1
      content: {
        json: '## Request Rate & Error Rate'
      }
      name: 'section-requests'
    }
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
InsightsMetrics
| where Namespace == "prometheus" and Name == "directai_requests_total"
| extend model = tostring(Tags.model), status = tostring(Tags.status)
| where isnotempty(model)
| summarize Value = sum(Val) by model, status, bin(TimeGenerated, 1m)
| order by TimeGenerated asc
'''
        size: 0
        timeContextFromParameter: 'TimeRange'
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [logAnalyticsWorkspaceId]
        visualization: 'timechart'
        chartSettings: {
          seriesLabelSettings: [
            { seriesName: 'ok', color: 'green' }
            { seriesName: 'error', color: 'red' }
          ]
        }
      }
      name: 'request-rate-chart'
    }
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
InsightsMetrics
| where Namespace == "prometheus" and Name == "directai_requests_total"
| extend model = tostring(Tags.model), status = tostring(Tags.status)
| where isnotempty(model)
| summarize Total = sum(Val) by model, status
| evaluate pivot(status, sum(Total))
| extend ErrorRate = iff(isnotnull(error) and (error + ok) > 0, round(100.0 * error / (error + ok), 2), 0.0)
| project Model = model, OK = ok, Errors = error, ['Error Rate %'] = ErrorRate
| order by Errors desc
'''
        size: 0
        timeContextFromParameter: 'TimeRange'
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [logAnalyticsWorkspaceId]
        visualization: 'table'
        gridSettings: {
          formatters: [
            {
              columnMatch: 'Error Rate %'
              formatter: 18
              formatOptions: {
                thresholdsOptions: 'icons'
                thresholdsGrid: [
                  { operator: '>=', thresholdValue: '5', representation: 'warning', text: '{0}%' }
                  { operator: '>=', thresholdValue: '1', representation: 'info', text: '{0}%' }
                  { operator: 'Default', representation: 'success', text: '{0}%' }
                ]
              }
            }
          ]
        }
      }
      name: 'error-rate-table'
    }
    // ── Section: Latency ───────────────────────────────────────────────
    {
      type: 1
      content: {
        json: '## Latency Percentiles (P50 / P95 / P99)'
      }
      name: 'section-latency'
    }
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
InsightsMetrics
| where Namespace == "prometheus" and Name == "directai_request_duration_seconds"
| extend model = tostring(Tags.model)
| where isnotempty(model)
| summarize P50 = round(percentile(Val, 50), 3),
            P95 = round(percentile(Val, 95), 3),
            P99 = round(percentile(Val, 99), 3),
            Avg = round(avg(Val), 3),
            Count = count()
  by model, bin(TimeGenerated, 1m)
| order by TimeGenerated asc
'''
        size: 0
        timeContextFromParameter: 'TimeRange'
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [logAnalyticsWorkspaceId]
        visualization: 'timechart'
      }
      name: 'latency-percentiles-chart'
    }
    // ── Section: TTFT (Time to First Token) ────────────────────────────
    {
      type: 1
      content: {
        json: '## Time to First Token (LLM)'
      }
      name: 'section-ttft'
    }
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
InsightsMetrics
| where Namespace == "prometheus" and Name == "directai_llm_time_to_first_token_seconds"
| summarize P50 = round(percentile(Val, 50), 3),
            P95 = round(percentile(Val, 95), 3),
            P99 = round(percentile(Val, 99), 3)
  by bin(TimeGenerated, 1m)
| order by TimeGenerated asc
'''
        size: 0
        timeContextFromParameter: 'TimeRange'
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [logAnalyticsWorkspaceId]
        visualization: 'timechart'
      }
      name: 'ttft-chart'
    }
    // ── Section: Inflight Requests ─────────────────────────────────────
    {
      type: 1
      content: {
        json: '## Inflight Requests (KEDA Scaling Trigger)'
      }
      name: 'section-inflight'
    }
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
InsightsMetrics
| where Namespace == "prometheus" and Name == "directai_backend_inflight_requests"
| extend model = tostring(Tags.model)
| where isnotempty(model)
| summarize Inflight = max(Val) by model, bin(TimeGenerated, 30s)
| order by TimeGenerated asc
'''
        size: 0
        timeContextFromParameter: 'TimeRange'
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [logAnalyticsWorkspaceId]
        visualization: 'timechart'
      }
      name: 'inflight-requests-chart'
    }
    // ── Section: Token Throughput ──────────────────────────────────────
    {
      type: 1
      content: {
        json: '## Token Throughput (LLM)'
      }
      name: 'section-tokens'
    }
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
InsightsMetrics
| where Namespace == "prometheus" and Name in ("directai_llm_tokens_generated_total", "directai_llm_prompt_tokens_total")
| summarize Tokens = sum(Val) by Name, bin(TimeGenerated, 1m)
| extend Metric = case(
    Name == "directai_llm_tokens_generated_total", "Generated",
    Name == "directai_llm_prompt_tokens_total", "Prompt",
    Name)
| project TimeGenerated, Metric, Tokens
| order by TimeGenerated asc
'''
        size: 0
        timeContextFromParameter: 'TimeRange'
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [logAnalyticsWorkspaceId]
        visualization: 'timechart'
      }
      name: 'token-throughput-chart'
    }
    // ── Section: GPU Utilization ───────────────────────────────────────
    {
      type: 1
      content: {
        json: '## GPU Utilization (DCGM Exporter)'
      }
      name: 'section-gpu'
    }
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
InsightsMetrics
| where Namespace == "prometheus" and Name in (
    "DCGM_FI_DEV_GPU_UTIL",
    "DCGM_FI_DEV_FB_USED",
    "DCGM_FI_DEV_FB_FREE"
  )
| extend gpu = tostring(Tags.gpu), node = tostring(Tags.instance)
| summarize Value = avg(Val) by Name, gpu, node, bin(TimeGenerated, 1m)
| extend Metric = case(
    Name == "DCGM_FI_DEV_GPU_UTIL", "GPU Util %",
    Name == "DCGM_FI_DEV_FB_USED", "FB Used MB",
    Name == "DCGM_FI_DEV_FB_FREE", "FB Free MB",
    Name)
| project TimeGenerated, Metric, gpu, node, Value
| order by TimeGenerated asc
'''
        size: 0
        timeContextFromParameter: 'TimeRange'
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [logAnalyticsWorkspaceId]
        visualization: 'timechart'
      }
      name: 'gpu-utilization-chart'
    }
    // ── Section: Node Pool Health ──────────────────────────────────────
    {
      type: 1
      content: {
        json: '## Node Pool Health'
      }
      name: 'section-nodepool'
    }
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
KubeNodeInventory
| where TimeGenerated > ago(5m)
| extend pool = tostring(Labels.agentpool)
| summarize NodeCount = dcount(Computer),
            ReadyNodes = dcountif(Computer, Status == "Ready"),
            NotReady = dcountif(Computer, Status != "Ready")
  by pool
| project Pool = pool, ['Total Nodes'] = NodeCount, Ready = ReadyNodes, ['Not Ready'] = NotReady
| order by Pool asc
'''
        size: 0
        timeContextFromParameter: 'TimeRange'
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [logAnalyticsWorkspaceId]
        visualization: 'table'
      }
      name: 'nodepool-health-table'
    }
    // ── Section: Embedding Engine ──────────────────────────────────────
    {
      type: 1
      content: {
        json: '## Embedding Engine — Batch Size & Throughput'
      }
      name: 'section-embeddings'
    }
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
InsightsMetrics
| where Namespace == "prometheus" and Name in (
    "directai_embed_batch_size",
    "directai_embed_requests_total",
    "directai_embed_request_duration_seconds"
  )
| summarize Value = avg(Val) by Name, bin(TimeGenerated, 1m)
| extend Metric = case(
    Name == "directai_embed_batch_size", "Avg Batch Size",
    Name == "directai_embed_requests_total", "Request Count",
    Name == "directai_embed_request_duration_seconds", "Avg Latency (s)",
    Name)
| project TimeGenerated, Metric, Value
| order by TimeGenerated asc
'''
        size: 0
        timeContextFromParameter: 'TimeRange'
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [logAnalyticsWorkspaceId]
        visualization: 'timechart'
      }
      name: 'embeddings-chart'
    }
    // ── Section: Cluster Autoscaler ────────────────────────────────────
    {
      type: 1
      content: {
        json: '## Cluster Autoscaler Events'
      }
      name: 'section-autoscaler'
    }
    {
      type: 3
      content: {
        version: 'KqlItem/1.0'
        query: '''
AzureDiagnostics
| where Category == "cluster-autoscaler"
| where TimeGenerated > ago(1h)
| project TimeGenerated, log_s
| order by TimeGenerated desc
| take 50
'''
        size: 0
        timeContextFromParameter: 'TimeRange'
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        crossComponentResources: [logAnalyticsWorkspaceId]
        visualization: 'table'
      }
      name: 'autoscaler-events-table'
    }
  ]
  styleSettings: {}
  '$schema': 'https://github.com/Microsoft/Application-Insights-Workbooks/blob/master/schema/workbook.json'
}

// ── Azure Monitor Workbook ────────────────────────────────────────────────

resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: guid('directai-observability-workbook', resourceGroup().id)
  location: location
  kind: 'shared'
  properties: {
    displayName: 'DirectAI Inference Platform'
    category: 'workbook'
    sourceId: appInsightsResourceId
    serializedData: string(workbookContent)
  }
  tags: union(tags, {
    'hidden-title': 'DirectAI Inference Platform'
  })
}

// ── Outputs ───────────────────────────────────────────────────────────────

@description('Workbook resource ID.')
output workbookResourceId string = workbook.id

@description('Workbook name.')
output workbookName string = workbook.name
