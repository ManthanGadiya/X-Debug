import { screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/render'
import { RuntimePage } from './RuntimePage'

const mockFetch = vi.fn()

vi.stubGlobal('fetch', mockFetch)

function jsonResponse(payload: unknown, ok = true) {
  return new Response(JSON.stringify(payload), {
    status: ok ? 200 : 500,
    headers: { 'Content-Type': 'application/json' },
  })
}

function mockRoutes(runtime: unknown[], ok = true) {
  mockFetch.mockImplementation((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/runtime')) return Promise.resolve(jsonResponse(runtime, ok))
    if (url.includes('/projects')) return Promise.resolve(jsonResponse([]))
    return Promise.resolve(jsonResponse({ detail: `no mock for ${url}` }, false))
  })
}

const run = {
  id: 'rt-1',
  project_id: 'proj-1',
  status: 'ready',
  created_at: '2026-07-24T12:00:00Z',
  updated_at: '2026-07-24T12:01:00Z',
  error: null,
}

afterEach(() => {
  vi.clearAllMocks()
})

function renderPage(initialEntry = '/runtime') {
  return renderWithProviders(
    <MemoryRouter initialEntries={[initialEntry]}>
      <RuntimePage />
    </MemoryRouter>,
  )
}

describe('RuntimePage', () => {
  it('renders the page header and lists runs', async () => {
    mockRoutes([run])

    renderPage()

    expect(await screen.findByRole('heading', { name: /runtime/i })).toBeInTheDocument()
    expect(await screen.findByText(/rt-1/)).toBeInTheDocument()
  })

  it('shows an empty state when no runs exist', async () => {
    mockRoutes([])

    renderPage()

    expect(
      await screen.findByText('No runtime runs yet — open a project and run its code there.'),
    ).toBeInTheDocument()
  })

  it('shows an error alert when the backend fails', async () => {
    mockRoutes([], false)

    renderPage()

    expect(await screen.findByText('Failed to load runtime runs')).toBeInTheDocument()
  })

  it('renders the start button only when a project filter is present', async () => {
    mockRoutes([run])

    renderPage('/runtime?project=proj-1')

    expect(await screen.findByRole('button', { name: 'Run code' })).toBeInTheDocument()
  })
})
