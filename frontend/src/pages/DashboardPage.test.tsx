import { screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { renderWithProviders } from '../test/render'
import { DashboardPage } from './DashboardPage'

const mockFetch = vi.fn()

vi.stubGlobal('fetch', mockFetch)

function jsonResponse(payload: unknown, ok = true) {
  return new Response(JSON.stringify(payload), {
    status: ok ? 200 : 500,
    headers: { 'Content-Type': 'application/json' },
  })
}

function mockRoutes(routes: Record<string, () => Promise<Response>>) {
  mockFetch.mockImplementation((input: RequestInfo | URL) => {
    const url = String(input)
    for (const [path, handler] of Object.entries(routes)) {
      if (url.includes(path)) return handler()
    }
    return Promise.resolve(jsonResponse({ detail: `no mock for ${url}` }, false))
  })
}

const project = {
  id: 'proj-1',
  name: 'demo',
  source: 'local',
  root_path: '/workspace/demo',
  file_count: 12,
  source_file_count: 10,
  total_size_bytes: 4096,
  languages: ['Python'],
  created_at: '2026-07-24T12:00:00Z',
}

afterEach(() => {
  vi.clearAllMocks()
})

function renderPage() {
  return renderWithProviders(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  )
}

describe('DashboardPage', () => {
  it('renders the dashboard title and project count', async () => {
    mockRoutes({
      '/health': async () => jsonResponse({ status: 'ok', app: 'XDebug API', version: '0.1.0', environment: 'test' }),
      '/projects': async () => jsonResponse([project]),
      '/analysis': async () => jsonResponse([]),
      '/runtime': async () => jsonResponse([]),
      '/tests': async () => jsonResponse([]),
    })

    renderPage()

    expect(await screen.findByRole('heading', { name: /dashboard/i })).toBeInTheDocument()
    expect(await screen.findByText('demo')).toBeInTheDocument()
  })

  it('shows an offline warning when the backend is unreachable', async () => {
    mockRoutes({
      '/health': async () => jsonResponse({ detail: 'boom' }, false),
      '/projects': async () => jsonResponse([]),
      '/analysis': async () => jsonResponse([]),
      '/runtime': async () => jsonResponse([]),
      '/tests': async () => jsonResponse([]),
    })

    renderPage()

    expect(await screen.findByText('Backend unreachable')).toBeInTheDocument()
  })

  it('shows the upload panel', async () => {
    mockRoutes({
      '/health': async () => jsonResponse({ status: 'ok', app: 'XDebug API', version: '0.1.0', environment: 'test' }),
      '/projects': async () => jsonResponse([]),
      '/analysis': async () => jsonResponse([]),
      '/runtime': async () => jsonResponse([]),
      '/tests': async () => jsonResponse([]),
    })

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Upload a repository' })).toBeInTheDocument()
  })

  it('does not call projects endpoint twice when listProjects is invoked once', async () => {
    mockRoutes({
      '/health': async () => jsonResponse({ status: 'ok', app: 'XDebug API', version: '0.1.0', environment: 'test' }),
      '/projects': async () => jsonResponse([]),
      '/analysis': async () => jsonResponse([]),
      '/runtime': async () => jsonResponse([]),
      '/tests': async () => jsonResponse([]),
    })

    mockFetch.mockClear()

    await api.listProjects()

    expect(mockFetch).toHaveBeenCalledTimes(1)
  })
})
