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
Log shipping env vars, shared by the DID finder deployments: the legacy
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
Temporal worker env for a DID finder: where Temporal and the app's internal endpoint
are, and how many lookups to run at once. Called as
`include "servicex.didFinder.temporalEnv" (list . <maxConcurrentLookups>)`.

Render with `nindent 10` under a container's `env:`.
*/}}
{{- define "servicex.didFinder.temporalEnv" -}}
{{- $root := index . 0 -}}
- name: TEMPORAL_ADDRESS
  value: {{ include "servicex.temporal.address" $root | quote }}
- name: TEMPORAL_NAMESPACE
  value: {{ $root.Values.orchestrator.temporal.namespace | quote }}
- name: SERVICEX_INTERNAL_ENDPOINT
  value: "http://{{ $root.Release.Name }}-servicex-app:8000/servicex/internal/transformation/"
- name: DID_FINDER_MAX_CONCURRENT
  value: {{ index . 1 | quote }}
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
Temporal frontend host:port that ServiceX components connect to: the explicit
orchestrator.temporal.address, else the frontend Service of the temporal
subchart. The subchart names it <release>-temporal-frontend unless the release
name already contains "temporal".
*/}}
{{- define "servicex.temporal.address" -}}
{{- if .Values.orchestrator.temporal.address -}}
{{ .Values.orchestrator.temporal.address }}
{{- else if contains "temporal" .Release.Name -}}
{{ .Release.Name }}-frontend:7233
{{- else -}}
{{ .Release.Name }}-temporal-frontend:7233
{{- end -}}
{{- end -}}

{{/*
The Secret and key holding the orchestrator's Postgres password: the site's
`secrets` Secret when set (key orchestrator-db-password), otherwise the
<release>-orchestrator-db Secret this chart renders from
orchestrator.database.password.
*/}}
{{- define "servicex.orchestrator.dbSecretName" -}}
{{- if .Values.secrets -}}
{{ .Values.secrets }}
{{- else -}}
{{ .Release.Name }}-orchestrator-db
{{- end -}}
{{- end -}}

{{/*
The orchestrator role's name and password, for the orchestrator (which connects
as it) and for the app (whose boot.sh creates it after migrating). Render with
`trim | nindent` under a container's `env:`.
*/}}
{{- define "servicex.orchestrator.dbEnv" -}}
- name: ORCHESTRATOR_DB_USER
  value: {{ .Values.orchestrator.database.user | quote }}
- name: ORCHESTRATOR_DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "servicex.orchestrator.dbSecretName" . }}
      key: orchestrator-db-password
{{- end -}}
