import { screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/render'
import { ProjectsPage } from './ProjectsPage'

const mockFetch = vi.fn()

vi.stubGlobal('fetch', mockFetch)

function jsonResponse(payload: unknown, ok = true) {
  return new Response(JSON.stringify(payload), {
    status: ok ? 200 : 500,
    headers: { 'Content-Type': 'application/json' },
  })
}

function mockProjects(projects: unknown[], ok = true) {
  mockFetch.mockImplementation((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/projects')) return Promise.resolve(jsonResponse(projects, ok))
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
      <ProjectsPage />
    </MemoryRouter>,
  )
}

describe('ProjectsPage', () => {
  it('renders the page header and upload panel', async () => {
    mockProjects([])

    renderPage()

    expect(await screen.findByRole('heading', { name: /projects/i })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Upload a repository' })).toBeInTheDocument()
  })

  it('lists indexed projects with language tags', async () => {
    mockProjects([
      project,
      { ...project, id: 'proj-2', name: 'other', languages: ['C', 'C++'] },
    ])

    renderPage()

    expect(await screen.findByText('demo')).toBeInTheDocument()
    expect(await screen.findByText('other')).toBeInTheDocument()
    expect(await screen.findByText('Python')).toBeInTheDocument()
    expect(await screen.findByText('C')).toBeInTheDocument()
    expect(await screen.findByText('C++')).toBeInTheDocument()
  })

  it('shows an empty state when no projects exist', async () => {
    mockProjects([])

    renderPage()

    expect(
      await screen.findByText('No projects yet — upload a repository above.'),
    ).toBeInTheDocument()
  })

  it('shows an error alert when the backend fails', async () => {
    mockProjects([], false)

    renderPage()

    expect(await screen.findByText('Failed to load projects')).toBeInTheDocument()
  })

  it('links each project row to its detail page', async () => {
    mockProjects([project])

    renderPage()

    await screen.findByText('demo')

    const openButtons = await screen.findAllByRole('link', { name: 'Open' })
    expect(openButtons[0]).toHaveAttribute('href', '/projects/proj-1')
  })
})
