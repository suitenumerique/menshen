{{/*
Expand the name of the chart.
*/}}
{{- define "menshen.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "menshen.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "menshen.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
menshen.labels
*/}}
{{- define "menshen.labels" -}}
helm.sh/chart: {{ include "menshen.chart" . }}
{{ include "menshen.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "menshen.selectorLabels" -}}
app.kubernetes.io/name: {{ include "menshen.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
transform dictionary of environment variables
Usage : {{ include "menshen.env.transformDict" .Values.envVars }}

Example:
envVars:
  # Using simple strings as env vars
  ENV_VAR_NAME: "envVar value"
  # Using a value from a configMap
  ENV_VAR_FROM_CM:
    configMapKeyRef:
      name: cm-name
      key: "key_in_cm"
  # Using a value from a secret
  ENV_VAR_FROM_SECRET:
    secretKeyRef:
      name: secret-name
      key: "key_in_secret"
*/}}
{{- define "menshen.env.transformDict" -}}
{{- range $key, $value := . }}
- name: {{ $key | quote }}
{{- if $value | kindIs "map" }}
  valueFrom: {{ $value | toYaml | nindent 4 }}
{{- else }}
  value: {{ $value | quote }}
{{- end }}
{{- end }}
{{- end }}


{{/*
menshen env vars
*/}}
{{- define "menshen.common.env" -}}
{{- $topLevelScope := index . 0 -}}
{{- $workerScope := index . 1 -}}
{{- include "menshen.env.transformDict" $workerScope.envVars -}}
{{- end }}

{{/*
menshen backend django env vars - combines common backend.envVars with backend.django.envVars
*/}}
{{- define "menshen.backend.django.env" -}}
{{- $topLevelScope := index . 0 -}}
{{- $workerScope := index . 1 -}}
{{- include "menshen.env.transformDict" $workerScope.envVars -}}
{{- include "menshen.env.transformDict" (($workerScope.django | default dict).envVars | default dict) -}}
{{- include "menshen.backend.metrics.env" $topLevelScope -}}
{{- end }}

{{/*
Environment enabling the prometheus metrics of the backend. A pod is only ever
scraped over plain http, TLS ending at the ingress, so the path is also taken
out of the redirect to https. Each variable is skipped when the deployment sets
it by hand, in either env map. The bearer token (PROMETHEUS_API_KEY) is not set
here: it is a secret, given through `backend.envVars`.

Requires top level scope
*/}}
{{- define "menshen.backend.metrics.env" -}}
{{- if .Values.backend.metrics.enabled -}}
{{- $named := merge (dict) ((.Values.backend.django | default dict).envVars | default dict) (.Values.backend.envVars | default dict) -}}
{{- range $variable := list "PROMETHEUS_METRICS_ENABLED" "PROMETHEUS_METRICS_SSL_REDIRECT_EXEMPT" -}}
{{- if not (hasKey $named $variable) }}
- name: {{ $variable | quote }}
  value: "True"
{{- end }}
{{- end }}
{{- end }}
{{- end }}

{{/*
The Secret a monitor reads the bearer token of a scrape from: the one named in
`backend.metrics.apiKeySecret`, or else the one PROMETHEUS_API_KEY is taken
from in the env of the backend. A token that comes from nowhere the Prometheus
Operator can read is refused at render time, rather than left to fail at scrape
time with a 401.

Requires top level scope
*/}}
{{- define "menshen.metrics.apiKeySecret" -}}
{{- $ref := .Values.backend.metrics.apiKeySecret | default dict -}}
{{- if not $ref.name -}}
{{- $envVars := merge (dict) ((.Values.backend.django | default dict).envVars | default dict) (.Values.backend.envVars | default dict) -}}
{{- $fromEnv := index $envVars "PROMETHEUS_API_KEY" -}}
{{- $ref = (kindIs "map" $fromEnv) | ternary $fromEnv dict -}}
{{- $ref = $ref.secretKeyRef | default dict -}}
{{- end -}}
{{- if not (and $ref.name $ref.key) -}}
{{- fail "a monitor scrapes the backend with the bearer token of PROMETHEUS_API_KEY, which has to come from a Secret. Give it as a secretKeyRef in backend.envVars, or name the Secret in backend.metrics.apiKeySecret" -}}
{{- end -}}
name: {{ $ref.name | quote }}
key: {{ $ref.key | quote }}
{{- end }}

{{/*
The scrape endpoint of a ServiceMonitor or a PodMonitor.

Requires a dict with the top level scope (root) and the monitor values (monitor)
*/}}
{{- define "menshen.metrics.endpoint" -}}
- port: http
  path: "/metrics"
  scheme: http
  {{- with .monitor.interval }}
  interval: {{ . }}
  {{- end }}
  {{- with .monitor.scrapeTimeout }}
  scrapeTimeout: {{ . }}
  {{- end }}
  honorLabels: {{ .monitor.honorLabels }}
  authorization:
    type: Bearer
    credentials:
      {{- include "menshen.metrics.apiKeySecret" .root | nindent 6 }}
  {{- with .monitor.relabelings }}
  relabelings:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  {{- with .monitor.metricRelabelings }}
  metricRelabelings:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end }}

{{/*
Common labels

Requires array with top level scope and component name
*/}}
{{- define "menshen.common.labels" -}}
{{- $topLevelScope := index . 0 -}}
{{- $component := index . 1 -}}
{{- include "menshen.labels" $topLevelScope }}
app.kubernetes.io/component: {{ $component }}
{{- end }}

{{/*
Common selector labels

Requires array with top level scope and component name
*/}}
{{- define "menshen.common.selectorLabels" -}}
{{- $topLevelScope := index . 0 -}}
{{- $component := index . 1 -}}
{{- include "menshen.selectorLabels" $topLevelScope }}
app.kubernetes.io/component: {{ $component }}
{{- end }}

{{- define "menshen.probes.abstract" -}}
{{- if .exec -}}
exec:
{{- toYaml .exec | nindent 2 }}
{{- else if .tcpSocket -}}
tcpSocket:
{{- toYaml .tcpSocket | nindent 2 }}
{{- else -}}
httpGet:
  path: {{ .path }}
  port: {{ .targetPort }}
{{- end }}
initialDelaySeconds: {{ .initialDelaySeconds | eq nil | ternary 0 .initialDelaySeconds }}
timeoutSeconds: {{ .timeoutSeconds | eq nil | ternary 1 .timeoutSeconds }}
{{- end }}

{{/*
Full name for the backend

Requires top level scope
*/}}
{{- define "menshen.backend.fullname" -}}
{{ include "menshen.fullname" . }}-backend
{{- end }}


{{/*
Usage : {{ include "menshen.secret.dockerconfigjson.name" (dict "fullname" (include "menshen.fullname" .) "imageCredentials" .Values.path.to.the.image1) }}
*/}}
{{- define "menshen.secret.dockerconfigjson.name" }}
{{- if (default (dict) .imageCredentials).name }}{{ .imageCredentials.name }}{{ else }}{{ .fullname | trunc 63 | trimSuffix "-" }}-dockerconfig{{ end -}}
{{- end }}

{{/*
Usage : {{ include "menshen.secret.dockerconfigjson" (dict "fullname" (include "menshen.fullname" .) "imageCredentials" .Values.path.to.the.image1) }}
*/}}
{{- define "menshen.secret.dockerconfigjson" }}
{{- if .imageCredentials -}}
apiVersion: v1
kind: Secret
metadata:
  name: {{ template "menshen.secret.dockerconfigjson.name" (dict "fullname" .fullname "imageCredentials" .imageCredentials) }}
  annotations:
    "helm.sh/hook": pre-install,pre-upgrade
    "helm.sh/hook-weight": "-5"
    "helm.sh/hook-delete-policy": before-hook-creation
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: {{ template "menshen.secret.dockerconfigjson.data" .imageCredentials }}
{{- end -}}
{{- end }}
