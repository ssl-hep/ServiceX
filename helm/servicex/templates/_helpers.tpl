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
Log shipping env vars, shared by all four DID finder deployments.

  logstash - the legacy path to the external Elastic cluster.
  vector   - the release's vector aggregator, which owns the only connection to
             the Postgres log_messages table. A DID finder is a long-running
             deployment rather than a per-request pod, so like the app it writes
             straight to the aggregator's TCP socket source; it needs no vector
             container of its own.

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
{{- if .Values.logging.vector.enabled }}
- name: VECTOR_HOST
  value: "{{ .Release.Name }}-vector-aggregator"
- name: VECTOR_PORT
  value: "{{ .Values.logging.vector.port }}"
{{- end }}
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
