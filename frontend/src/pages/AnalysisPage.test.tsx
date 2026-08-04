import { screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/render'
import { AnalysisPage } from './AnalysisPage'

const mockFetch = vi.fn()

vi.stubGlobal('fetch', mockFetch)

function jsonResponse(payload: unknown, ok = true) {
  return new Response(JSON.stringify(payload), {
    status: ok ? 200 : 500,
    headers: { 'Content-Type': 'application/json' },
  })
}

function mockRoutes(analysis: unknown[], ok = true) {
  mockFetch.mockImplementation((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/analysis')) return Promise.resolve(jsonResponse(analysis, ok))
    if (url.includes('/projects')) return Promise.resolve(jsonResponse([]))
    return Promise.resolve(jsonResponse({ detail: `no mock for ${url}` }, false))
  })
}

const run = {
  id: 'an-1',
  project_id: 'proj-1',
  status: 'ready',
  created_at: '2026-07-24T12:00:00Z',
  updated_at: '2026-07-24T12:01:00Z',
  error: null,
}

afterEach(() => {
  vi.clearAllMocks()
})

function renderPage(initialEntry = '/analysis') {
  return renderWithProviders(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AnalysisPage />
    </MemoryRouter>,
  )
}

describe('AnalysisPage', () => {
  it('renders the page header and lists runs', async () => {
    mockRoutes([run])

    renderPage()

    expect(await screen.findByRole('heading', { name: /analysis/i })).toBeInTheDocument()
    expect(await screen.findByText(/an-1/)).toBeInTheDocument()
  })

  it('shows an empty state when no runs exist', async () => {
    mockRoutes([])

    renderPage()

    expect(
      await screen.findByText('No analysis runs yet — open a project and start analysis there.'),
    ).toBeInTheDocument()
  })

  it('shows an error alert when the backend fails', async () => {
    mockRoutes([], false)

    renderPage()

    expect(await screen.findByText('Failed to load analysis runs')).toBeInTheDocument()
  })

  it('renders the start button only when a project filter is present', async () => {
    mockRoutes([run])

    renderPage('/analysis?project=proj-1')

    expect(await screen.findByRole('button', { name: 'Start analysis' })).toBeInTheDocument()
  })
})
