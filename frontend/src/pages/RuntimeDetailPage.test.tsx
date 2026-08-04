import { screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/render'
import { RuntimeDetailPage } from './RuntimeDetailPage'

const mockFetch = vi.fn()

vi.stubGlobal('fetch', mockFetch)

function jsonResponse(payload: unknown, ok = true) {
  return new Response(JSON.stringify(payload), {
    status: ok ? 200 : 500,
    headers: { 'Content-Type': 'application/json' },
  })
}

const detail = {
  id: 'rt-1',
  project_id: 'proj-1',
  status: 'ready',
  succeeded: false,
  languages: ['python'],
  created_at: '2026-07-24T12:00:00Z',
  updated_at: '2026-07-24T12:01:00Z',
  error: null,
}

const trace = {
  language: 'python',
  event_count: 4,
  duration_seconds: 0.25,
  stdout: 'hello\n',
  stderr: '',
  exception: null,
}

const replay = {
  language: 'python',
  first_index: 0,
  total_events: 4,
  max_stack_depth: 3,
  count_by_type: { call: 2, return: 2 },
}

const step = {
  index: 0,
  total: 4,
  previous_index: null,
  next_index: 1,
  event: {
    type: 'call',
    function: 'main',
    filename: 'main.py',
    lineno: 1,
    depth: 0,
    variables: { x: 1 },
    exception: null,
  },
}

function mockRoutes(overrides: Record<string, unknown> = {}) {
  mockFetch.mockImplementation((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/runtime/rt-1')) {
      if (url.includes('/trace/python')) {
        return Promise.resolve(jsonResponse(overrides.trace ?? trace))
      }
      if (url.includes('/replay/python')) {
        if (url.includes('/step')) {
          return Promise.resolve(jsonResponse(overrides.step ?? step))
        }
        return Promise.resolve(jsonResponse(overrides.replay ?? replay))
      }
      return Promise.resolve(jsonResponse(overrides.detail ?? detail))
    }
    return Promise.resolve(jsonResponse({ detail: `no mock for ${url}` }, false))
  })
}

afterEach(() => {
  vi.clearAllMocks()
})

function renderPage() {
  return renderWithProviders(
    <MemoryRouter initialEntries={['/runtime/rt-1']}>
      <Routes>
        <Route path="/runtime/:runId" element={<RuntimeDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RuntimeDetailPage', () => {
  it('renders the run header and result stat', async () => {
    mockRoutes()

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Runtime rt-1' })).toBeInTheDocument()
    expect(await screen.findByText('Result')).toBeInTheDocument()
    expect(await screen.findByText('FAILED')).toBeInTheDocument()
  })

  it('renders the execution trace and replay summary', async () => {
    mockRoutes()

    renderPage()

    expect(await screen.findByText('Execution trace')).toBeInTheDocument()
    expect(await screen.findByText('hello')).toBeInTheDocument()
    expect(await screen.findByText('4 events · max stack depth 3 · call×2 · return×2')).toBeInTheDocument()
  })

  it('starts a replay and shows the first step', async () => {
    mockRoutes()

    renderPage()

    const start = await screen.findByRole('button', { name: 'Start replay' })
    start.click()

    expect(await screen.findByText('#1 / 4')).toBeInTheDocument()
    expect(await screen.findByText('main.py:1 · main (depth 0)')).toBeInTheDocument()
    expect(await screen.findByText('call')).toBeInTheDocument()
  })

  it('shows a runtime error alert when the run failed with an error', async () => {
    mockRoutes({ detail: { ...detail, error: 'Killed by signal' } })

    renderPage()

    expect(await screen.findByText('Runtime error')).toBeInTheDocument()
    expect(await screen.findByText('Killed by signal')).toBeInTheDocument()
  })

  it('shows an error alert when the runtime run fails to load', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/runtime/rt-1') && !url.includes('/trace') && !url.includes('/replay')) {
        return Promise.resolve(jsonResponse({ detail: 'boom' }, false))
      }
      return Promise.resolve(jsonResponse({}))
    })

    renderPage()

    expect(await screen.findByText('Failed to load runtime run')).toBeInTheDocument()
  })
})
