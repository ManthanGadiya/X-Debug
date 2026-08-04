import { screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/render'
import { TestsPage } from './TestsPage'

const mockFetch = vi.fn()

vi.stubGlobal('fetch', mockFetch)

function jsonResponse(payload: unknown, ok = true) {
  return new Response(JSON.stringify(payload), {
    status: ok ? 200 : 500,
    headers: { 'Content-Type': 'application/json' },
  })
}

function mockRoutes(tests: unknown[], ok = true) {
  mockFetch.mockImplementation((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/tests')) return Promise.resolve(jsonResponse(tests, ok))
    if (url.includes('/projects')) return Promise.resolve(jsonResponse([]))
    return Promise.resolve(jsonResponse({ detail: `no mock for ${url}` }, false))
  })
}

const run = {
  id: 'ts-1',
  project_id: 'proj-1',
  status: 'ready',
  created_at: '2026-07-24T12:00:00Z',
  updated_at: '2026-07-24T12:01:00Z',
  error: null,
}

afterEach(() => {
  vi.clearAllMocks()
})

function renderPage(initialEntry = '/tests') {
  return renderWithProviders(
    <MemoryRouter initialEntries={[initialEntry]}>
      <TestsPage />
    </MemoryRouter>,
  )
}

describe('TestsPage', () => {
  it('renders the page header and lists runs', async () => {
    mockRoutes([run])

    renderPage()

    expect(await screen.findByRole('heading', { name: /tests/i })).toBeInTheDocument()
    expect(await screen.findByText(/ts-1/)).toBeInTheDocument()
  })

  it('shows an empty state when no runs exist', async () => {
    mockRoutes([])

    renderPage()

    expect(
      await screen.findByText('No test runs yet — open a project and run its tests there.'),
    ).toBeInTheDocument()
  })

  it('shows an error alert when the backend fails', async () => {
    mockRoutes([], false)

    renderPage()

    expect(await screen.findByText('Failed to load test runs')).toBeInTheDocument()
  })

  it('renders the run button only when a project filter is present', async () => {
    mockRoutes([run])

    renderPage('/tests?project=proj-1')

    expect(await screen.findByRole('button', { name: 'Run tests' })).toBeInTheDocument()
  })
})
