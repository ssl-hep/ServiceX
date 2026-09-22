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

Renders empty when vector is disabled. Since `nindent` on an empty string still
emits an indented blank line, a caller with nothing else in the block wraps it
in `with`; a caller that always has other env vars can just pipe through
`trim | nindent`.
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
