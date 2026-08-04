// Typed API client for the XDebug backend.
//
// All endpoints live under `/api/v1` (overridable with `VITE_API_BASE_URL`).
// Types mirror the Pydantic response models in `backend/app/schemas`.

export type Language = 'Python' | 'C' | 'C++'

export type RunStatus = 'queued' | 'running' | 'ready' | 'failed'

export type GraphKind = 'dependency' | 'call' | 'cfg' | 'dataflow'

export interface HealthResponse {
  status: string
  app: string
  version: string
  environment: string
}

export interface SourceFile {
  path: string
  language: Language
  size_bytes: number
  lines: number
}

export interface ProjectSummary {
  id: string
  name: string
  source: string
  root_path: string
  file_count: number
  source_file_count: number
  total_size_bytes: number
  languages: Language[]
  created_at: string
}

export interface ProjectDetail extends ProjectSummary {
  files: SourceFile[]
}

export interface AnalysisSummary {
  id: string
  project_id: string
  status: RunStatus
  created_at: string
  updated_at: string
  error: string | null
}

export interface AnalysisDetail extends AnalysisSummary {
  parsed_file_count: number
  failed_file_count: number
  dependency_edge_count: number
  call_edge_count: number
  cfg_node_count: number
  dataflow_edge_count: number
}

export interface GraphNode {
  id: string
  kind: string
  label: string
}

export interface GraphEdge {
  source: string
  target: string
  kind: string
}

export interface GraphData {
  name: string
  node_count: number
  edge_count: number
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface RuntimeExceptionSchema {
  type: string
  message: string
}

export interface RuntimeSummary {
  id: string
  project_id: string
  status: RunStatus
  created_at: string
  updated_at: string
  error: string | null
}

export interface RuntimeDetail extends RuntimeSummary {
  languages: string[]
  succeeded: boolean
}

export interface TraceEvent {
  type: string
  function: string
  filename: string
  lineno: number
  timestamp: number
  depth: number
  variables: Record<string, unknown>
  exception: string | null
}

export interface RuntimeResultSchema {
  language: string
  exit_code: number | null
  stdout: string
  stderr: string
  duration_seconds: number
  exception: RuntimeExceptionSchema | null
  event_count: number
  function_order: string[]
  error: string | null
}

export interface RuntimeTraceDetail extends RuntimeResultSchema {
  events: TraceEvent[]
}

export interface ReplayStep {
  index: number
  event: TraceEvent
  position: number
  total: number
  stack_depth: number
  previous_index: number | null
  next_index: number | null
}

export interface ReplaySummary {
  language: string
  total_events: number
  count_by_type: Record<string, number>
  function_order: string[]
  exception: RuntimeExceptionSchema | null
  max_stack_depth: number
  first_index: number | null
  last_index: number | null
}

export interface ReplayStepList {
  language: string
  total: number
  offset: number
  limit: number
  items: ReplayStep[]
}

export interface TestSummary {
  id: string
  project_id: string
  status: RunStatus
  created_at: string
  updated_at: string
  error: string | null
}

export interface TestDetail extends TestSummary {
  languages: string[]
  tests_run: number
  passed: number
  failed: number
  skipped: number
  succeeded: boolean
}

export interface TestCase {
  name: string
  outcome: string
  duration_seconds: number
  message: string | null
}

export interface TestSuiteDetail {
  language: string
  tests_run: number
  passed: number
  failed: number
  skipped: number
  duration_seconds: number
  error: string | null
  cases: TestCase[]
}

export interface KnowledgeStats {
  node_count: number
  edge_count: number
  node_kinds: Record<string, number>
  edge_kinds: Record<string, number>
}

export interface KnowledgeDetail {
  project_id: string
  status: string
  created_at: string
  updated_at: string
  error: string | null
  sources: string[]
  missing_sources: string[]
  stats: KnowledgeStats
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface EvidenceSchema {
  source: string
  description: string
  score: number
}

export interface LocalizationCandidate {
  node_id: string
  label: string
  kind: string
  score: number
  evidence: EvidenceSchema[]
  reason: string
}

export interface LocalizationDetail {
  project_id: string
  status: string
  created_at: string
  updated_at: string
  error: string | null
  resolved: boolean
  confidence: number
  summary: string
  root_cause: LocalizationCandidate | null
  candidates: LocalizationCandidate[]
  propagation_path: string[]
  evidence_summary: EvidenceSchema[]
  missing_sources: string[]
  suggested_fix: string | null
}

export interface EvidenceReference {
  source: string
  description: string
  score: number
  artifact: string
}

export interface WhereReference {
  file: string
  function: string
  cls: string
  line: number | null
}

export interface ExplanationDetail {
  project_id: string
  status: string
  created_at: string
  updated_at: string
  error: string | null
  resolved: boolean
  error_summary: string
  root_cause: string | null
  why: string
  where: WhereReference[]
  evidence: EvidenceReference[]
  suggested_fix: string | null
  confidence: number
  propagation_path: string[]
  missing_sources: string[]
  insufficient_evidence: boolean
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `Request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST'
  body?: unknown
  formData?: FormData
  query?: Record<string, string | number | boolean | undefined>
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  if (!query) return `${API_BASE}${path}`
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) {
      params.set(key, String(value))
    }
  }
  const suffix = params.toString()
  return `${API_BASE}${path}${suffix ? `?${suffix}` : ''}`
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, formData, query } = options
  const response = await fetch(buildUrl(path, query), {
    method,
    headers: formData ? undefined : body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
  })

  if (!response.ok) {
    let detail: unknown
    try {
      const payload = (await response.json()) as { detail?: unknown }
      detail = payload.detail
    } catch {
      detail = undefined
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export const api = {
  health: () => request<HealthResponse>('/health'),

  listProjects: () => request<ProjectSummary[]>('/projects'),
  getProject: (projectId: string) => request<ProjectDetail>(`/projects/${projectId}`),
  uploadProject: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return request<ProjectDetail>('/projects/upload', { method: 'POST', formData })
  },
  ingestGithub: (url: string) =>
    request<ProjectDetail>('/projects/github', { method: 'POST', body: { url } }),

  listAnalysis: () => request<AnalysisSummary[]>('/analysis'),
  startAnalysis: (projectId: string) =>
    request<AnalysisSummary>('/analysis/start', { method: 'POST', body: { project_id: projectId } }),
  getAnalysis: (analysisId: string) => request<AnalysisDetail>(`/analysis/${analysisId}`),
  getGraph: (analysisId: string, kind: GraphKind) =>
    request<GraphData>(`/analysis/${analysisId}/graphs/${kind}`),

  listRuntime: () => request<RuntimeSummary[]>('/runtime'),
  startRuntime: (projectId: string) =>
    request<RuntimeSummary>('/runtime/run', { method: 'POST', body: { project_id: projectId } }),
  getRuntime: (runId: string) => request<RuntimeDetail>(`/runtime/${runId}`),
  getTrace: (runId: string, language: Language) =>
    request<RuntimeTraceDetail>(`/runtime/${runId}/trace/${language}`),
  getReplay: (runId: string, language: Language) =>
    request<ReplaySummary>(`/runtime/${runId}/replay/${language}`),
  getReplayStep: (runId: string, language: Language, index: number) =>
    request<ReplayStep>(`/runtime/${runId}/replay/${language}/step`, {
      query: { index },
    }),
  getReplaySteps: (
    runId: string,
    language: Language,
    query: { event_type?: string; function?: string; offset?: number; limit?: number } = {},
  ) => request<ReplayStepList>(`/runtime/${runId}/replay/${language}/steps`, { query }),

  listTests: () => request<TestSummary[]>('/tests'),
  startTests: (projectId: string) =>
    request<TestSummary>('/tests/run', { method: 'POST', body: { project_id: projectId } }),
  getTestRun: (runId: string) => request<TestDetail>(`/tests/${runId}`),
  getTestResults: (runId: string, language: Language) =>
    request<TestSuiteDetail>(`/tests/${runId}/results/${language}`),

  buildKnowledge: (projectId: string) =>
    request<KnowledgeDetail>('/knowledge/build', { method: 'POST', body: { project_id: projectId } }),
  getKnowledge: (projectId: string) => request<KnowledgeDetail>(`/knowledge/${projectId}`),

  runLocalization: (projectId: string, language = 'python') =>
    request<LocalizationDetail>(`/localization/${projectId}`, {
      method: 'POST',
      body: { language },
    }),
  getLocalization: (projectId: string) =>
    request<LocalizationDetail>(`/localization/${projectId}`),

  runExplanation: (projectId: string) =>
    request<ExplanationDetail>(`/explanation/${projectId}`, { method: 'POST' }),
  getExplanation: (projectId: string) =>
    request<ExplanationDetail>(`/explanation/${projectId}`),
}
