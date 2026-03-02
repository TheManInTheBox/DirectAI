{{/*
Common labels applied to all resources.
*/}}
{{- define "directai.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/*
Selector labels for the API server.
*/}}
{{- define "directai.apiServerSelectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: api-server
{{- end }}

{{/*
Selector labels for a backend inference pod.
Usage: include "directai.backendSelectorLabels" (dict "name" $name "root" $)
*/}}
{{- define "directai.backendSelectorLabels" -}}
app.kubernetes.io/name: {{ .root.Chart.Name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: backend
directai.io/model: {{ .name }}
{{- end }}

{{/*
Service account name.
*/}}
{{- define "directai.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default "directai" .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
