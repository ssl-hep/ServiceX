{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "servicex.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "servicex.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "servicex.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
The vector aggregator's Service name. Every producer that talks to the
aggregator - the app, the DID finders, each transformer pod's own vector - goes
through this, so the name is spelled once.
*/}}
{{- define "servicex.vector.aggregatorHost" -}}
{{ .Release.Name }}-vector-aggregator
{{- end -}}

{{/*
Env vars pointing a python logger at the vector aggregator, which owns the only
connection to the Postgres log_messages table. Used by the app and by all four
DID finders. They are long-running deployments rather than per-request pods, so
they write straight to the aggregator's TCP socket source and need no vector
container of their own, and no postgres credentials.

Renders empty when vector is disabled. Render with `trim | nindent` under an
`env:` list that has other entries.
*/}}
{{- define "servicex.vector.env" -}}
{{- if .Values.logging.vector.enabled }}
- name: VECTOR_HOST
  value: "{{ include "servicex.vector.aggregatorHost" . }}"
- name: VECTOR_PORT
  value: "{{ .Values.logging.vector.port }}"
{{- end }}
{{- end -}}

{{/*
Log shipping env vars, shared by all four DID finder deployments: the legacy
logstash path to the external Elastic cluster, plus the vector aggregator.

Render with `nindent 10` under a container's `env:`. INSTANCE_NAME is
deliberately not here: the finders place it in different spots in their lists.
*/}}
{{- define "servicex.didFinder.loggingEnv" -}}
{{- if .Values.logging.logstash.enabled }}
- name: LOGSTASH_HOST
  value: "{{ .Values.logging.logstash.host }}"
- name: LOGSTASH_PORT
  value: "{{ .Values.logging.logstash.port }}"
{{- end }}
{{- include "servicex.vector.env" . }}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "servicex.labels" -}}
app.kubernetes.io/name: {{ include "servicex.name" . }}
helm.sh/chart: {{ include "servicex.chart" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Names of the resources created by the bundled monitoring subcharts.

Prometheus, Grafana and Tempo come from the upstream community charts, so
their resource names are decided by *their* fullname helpers, not ours. These
mirror that logic so the datasource URLs, the RBAC subjects and the OTLP
endpoint keep pointing at the right objects even when the release name already
contains the chart name (which makes the upstream helpers collapse the prefix).
*/}}

{{- define "servicex.prometheus.fullname" -}}
{{- if .Values.prometheus.fullnameOverride -}}
{{- .Values.prometheus.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default "prometheus" .Values.prometheus.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/* The Prometheus server Deployment/Service/ServiceAccount, e.g. myrelease-prometheus-server */}}
{{- define "servicex.prometheus.server" -}}
{{- if .Values.prometheus.server.fullnameOverride -}}
{{- .Values.prometheus.server.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default "prometheus" .Values.prometheus.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- printf "%s-%s" .Release.Name .Values.prometheus.server.name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s-%s" .Release.Name $name .Values.prometheus.server.name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/* In-cluster URL of the bundled Prometheus, without a trailing slash */}}
{{- define "servicex.prometheus.url" -}}
{{- printf "http://%s:%v" (include "servicex.prometheus.server" .) .Values.prometheus.server.service.servicePort -}}
{{- end -}}

{{- define "servicex.grafana.fullname" -}}
{{- if .Values.grafana.fullnameOverride -}}
{{- .Values.grafana.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default "grafana" .Values.grafana.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "servicex.tempo.fullname" -}}
{{- if .Values.tempo.fullnameOverride -}}
{{- .Values.tempo.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default "tempo" .Values.tempo.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/* True when Tempo's metrics-generator is on, which is what fills the span
     metrics and service graph the tracing dashboard draws. */}}
{{- define "servicex.tempo.serviceGraphsEnabled" -}}
{{- if and .Values.monitoring.tracing.enabled .Values.tempo.tempo.metricsGenerator.enabled -}}
true
{{- end -}}
{{- end -}}
