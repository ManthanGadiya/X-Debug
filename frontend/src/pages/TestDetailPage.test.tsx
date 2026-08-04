import { screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/render'
import { TestDetailPage } from './TestDetailPage'

const mockFetch = vi.fn()

vi.stubGlobal('fetch', mockFetch)

function jsonResponse(payload: unknown, ok = true) {
  return new Response(JSON.stringify(payload), {
    status: ok ? 200 : 500,
    headers: { 'Content-Type': 'application/json' },
  })
}

const detail = {
  id: 'ts-1',
  project_id: 'proj-1',
  status: 'ready',
  succeeded: false,
  tests_run: 3,
  passed: 2,
  failed: 1,
  skipped: 0,
  languages: ['python'],
  created_at: '2026-07-24T12:00:00Z',
  updated_at: '2026-07-24T12:01:00Z',
  error: null,
}

const suite = {
  language: 'python',
  tests_run: 3,
  duration_seconds: 0.42,
  passed: 2,
  failed: 1,
  skipped: 0,
  error: null,
  cases: [
    { name: 'test_add', outcome: 'passed', duration_seconds: 0.1, message: null },
    {
      name: 'test_sub',
      outcome: 'failed',
      duration_seconds: 0.2,
      message: 'assert 4 == 5',
    },
    { name: 'test_mul', outcome: 'skipped', duration_seconds: 0.0, message: null },
  ],
}

function mockRoutes(overrides: Record<string, unknown> = {}) {
  mockFetch.mockImplementation((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/tests/ts-1')) {
      if (url.includes('/results/python')) {
        return Promise.resolve(jsonResponse(overrides.suite ?? suite))
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
    <MemoryRouter initialEntries={['/tests/ts-1']}>
      <Routes>
        <Route path="/tests/:runId" element={<TestDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('TestDetailPage', () => {
  it('renders the run header and stat cards', async () => {
    mockRoutes()

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Test run ts-1' })).toBeInTheDocument()
    expect(await screen.findByText('Result')).toBeInTheDocument()
    expect(await screen.findByText('FAILED')).toBeInTheDocument()
    expect(await screen.findByText('2')).toBeInTheDocument()
  })

  it('renders the suite table with per-case outcomes', async () => {
    mockRoutes()

    renderPage()

    expect(await screen.findByText('python suite')).toBeInTheDocument()
    expect(await screen.findByText('test_add')).toBeInTheDocument()
    expect(await screen.findByText('test_sub')).toBeInTheDocument()
    expect(await screen.findByText('test_mul')).toBeInTheDocument()
    expect(await screen.findByText('passed')).toBeInTheDocument()
    expect(await screen.findByText('failed')).toBeInTheDocument()
  })

  it('shows failure messages in the failures viewer', async () => {
    mockRoutes()

    renderPage()

    expect(await screen.findByText('Failures')).toBeInTheDocument()
    expect(await screen.findByText(/assert 4 == 5/)).toBeInTheDocument()
  })

  it('shows a test run error alert when the run failed with an error', async () => {
    mockRoutes({ detail: { ...detail, error: 'Timeout' } })

    renderPage()

    expect(await screen.findByText('Test run error')).toBeInTheDocument()
    expect(await screen.findByText('Timeout')).toBeInTheDocument()
  })

  it('shows an error alert when the test run fails to load', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/tests/ts-1') && !url.includes('/results')) {
        return Promise.resolve(jsonResponse({ detail: 'boom' }, false))
      }
      return Promise.resolve(jsonResponse({}))
    })

    renderPage()

    expect(await screen.findByText('Failed to load test run')).toBeInTheDocument()
  })
})
