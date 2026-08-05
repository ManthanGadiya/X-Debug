import { screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/render'
import { ProjectDetailPage } from './ProjectDetailPage'

const mockFetch = vi.fn()

vi.stubGlobal('fetch', mockFetch)

function jsonResponse(payload: unknown, ok = true) {
  return new Response(JSON.stringify(payload), {
    status: ok ? 200 : 500,
    headers: { 'Content-Type': 'application/json' },
  })
}

const detail = {
  id: 'proj-1',
  name: 'demo',
  source: 'local',
  root_path: '/workspace/demo',
  file_count: 12,
  source_file_count: 10,
  total_size_bytes: 4096,
  languages: ['Python'],
  created_at: '2026-07-24T12:00:00Z',
  files: [
    { path: 'main.py', language: 'Python', size_bytes: 512, lines: 42 },
    { path: 'util.py', language: 'Python', size_bytes: 256, lines: 17 },
  ],
}

function mockRoutes(overrides: Record<string, unknown> = {}) {
  mockFetch.mockImplementation((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/projects/proj-1')) return Promise.resolve(jsonResponse(detail))
    if (url.includes('/analysis')) {
      return Promise.resolve(jsonResponse(overrides.analysis ?? []))
    }
    if (url.includes('/runtime')) {
      return Promise.resolve(jsonResponse(overrides.runtime ?? []))
    }
    if (url.includes('/tests')) return Promise.resolve(jsonResponse(overrides.tests ?? []))
    return Promise.resolve(jsonResponse({ detail: `no mock for ${url}` }, false))
  })
}

afterEach(() => {
  vi.clearAllMocks()
})

function renderPage() {
  return renderWithProviders(
    <MemoryRouter initialEntries={['/projects/proj-1']}>
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProjectDetailPage', () => {
  it('renders the project name, stats, and source files', async () => {
    mockRoutes()

    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'demo' }, { timeout: 3000 }),
    ).toBeInTheDocument()
    expect(await screen.findByText('10')).toBeInTheDocument()
    expect(await screen.findByText('main.py')).toBeInTheDocument()
    expect(await screen.findByText('util.py')).toBeInTheDocument()
    expect(await screen.findAllByText('Python')).toHaveLength(2)
  })

  it('renders action links to analysis, runtime, tests, and reports', async () => {
    mockRoutes()

    renderPage()

    await screen.findByRole('heading', { name: 'demo' })

    expect(screen.getByRole('link', { name: 'Analyze' })).toHaveAttribute(
      'href',
      '/analysis?project=proj-1',
    )
    expect(screen.getByRole('link', { name: 'Run' })).toHaveAttribute(
      'href',
      '/runtime?project=proj-1',
    )
    expect(screen.getByRole('link', { name: 'Test' })).toHaveAttribute(
      'href',
      '/tests?project=proj-1',
    )
    expect(screen.getByRole('link', { name: 'Report' })).toHaveAttribute(
      'href',
      '/reports?project=proj-1',
    )
  })

  it('lists analysis, runtime, and test runs for the project', async () => {
    mockRoutes({
      analysis: [
        {
          id: 'an-1',
          project_id: 'proj-1',
          status: 'ready',
          created_at: '2026-07-24T12:00:00Z',
          updated_at: '2026-07-24T12:01:00Z',
          error: null,
        },
      ],
      runtime: [
        {
          id: 'rt-1',
          project_id: 'proj-1',
          status: 'ready',
          created_at: '2026-07-24T12:00:00Z',
          updated_at: '2026-07-24T12:01:00Z',
          error: null,
        },
      ],
      tests: [
        {
          id: 'ts-1',
          project_id: 'proj-1',
          status: 'ready',
          created_at: '2026-07-24T12:00:00Z',
          updated_at: '2026-07-24T12:01:00Z',
          error: null,
        },
      ],
    })

    renderPage()

    expect(await screen.findByText(/an-1/)).toBeInTheDocument()
    expect(await screen.findByText(/rt-1/)).toBeInTheDocument()
    expect(await screen.findByText(/ts-1/)).toBeInTheDocument()
  })

  it('shows empty labels when the project has no runs', async () => {
    mockRoutes()

    renderPage()

    expect(
      await screen.findByText('No analysis runs yet — start one from the Analysis page.'),
    ).toBeInTheDocument()
    expect(
      await screen.findByText('No runtime runs yet — start one from the Runtime page.'),
    ).toBeInTheDocument()
    expect(
      await screen.findByText('No test runs yet — start one from the Tests page.'),
    ).toBeInTheDocument()
  })

  it('shows an error alert when the project fails to load', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/projects/proj-1')) {
        return Promise.resolve(jsonResponse({ detail: 'boom' }, false))
      }
      return Promise.resolve(jsonResponse([]))
    })

    renderPage()

    expect(await screen.findByText('Failed to load project')).toBeInTheDocument()
  })
})
