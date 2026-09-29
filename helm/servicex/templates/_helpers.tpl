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
