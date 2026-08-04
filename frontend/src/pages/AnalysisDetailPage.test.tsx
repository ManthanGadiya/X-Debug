import { screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/render'
import { AnalysisDetailPage } from './AnalysisDetailPage'

const mockFetch = vi.fn()

vi.stubGlobal('fetch', mockFetch)

function jsonResponse(payload: unknown, ok = true) {
  return new Response(JSON.stringify(payload), {
    status: ok ? 200 : 500,
    headers: { 'Content-Type': 'application/json' },
  })
}

function mockRoutes(overrides: Record<string, unknown> = {}) {
  mockFetch.mockImplementation((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/analysis/an-1')) {
      if (url.includes('/graphs/')) {
        return Promise.resolve(
          jsonResponse(
            overrides.graph ?? {
              name: 'dependency',
              node_count: 2,
              edge_count: 1,
              nodes: [
                { id: 'n1', kind: 'module', label: 'main.py' },
                { id: 'n2', kind: 'module', label: 'util.py' },
              ],
              edges: [{ source: 'n1', target: 'n2', kind: 'import' }],
            },
          ),
        )
      }
      return Promise.resolve(
        jsonResponse(
          overrides.analysis ?? {
            id: 'an-1',
            project_id: 'proj-1',
            status: 'ready',
            created_at: '2026-07-24T12:00:00Z',
            updated_at: '2026-07-24T12:01:00Z',
            error: null,
            parsed_file_count: 2,
            failed_file_count: 0,
            dependency_edge_count: 1,
            call_edge_count: 0,
            cfg_node_count: 3,
            dataflow_edge_count: 0,
          },
        ),
      )
    }
    return Promise.resolve(jsonResponse({ detail: `no mock for ${url}` }, false))
  })
}

afterEach(() => {
  vi.clearAllMocks()
})

function renderPage() {
  return renderWithProviders(
    <MemoryRouter initialEntries={['/analysis/an-1']}>
      <Routes>
        <Route path="/analysis/:analysisId" element={<AnalysisDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AnalysisDetailPage', () => {
  it('renders the run header and stat cards', async () => {
    mockRoutes()

    renderPage()

    expect(await screen.findByRole('heading', { name: /Analysis an-1/i })).toBeInTheDocument()
    expect(await screen.findByText('Files parsed')).toBeInTheDocument()
    expect(await screen.findByText('2')).toBeInTheDocument()
  })

  it('renders the dependency graph by default', async () => {
    mockRoutes()

    renderPage()

    expect(await screen.findByText('Graphs')).toBeInTheDocument()
    expect(await screen.findByText(/2 nodes, 1 edges/)).toBeInTheDocument()
    // GraphViewer truncates node labels to 6 chars (truncate(label, 6)),
    // so 'main.py' renders as 'main.…'.
    expect(await screen.findByText(/main\./)).toBeInTheDocument()
    expect(await screen.findByText(/util\./)).toBeInTheDocument()
  })

  it('switches graph kind via the segmented control', async () => {
    mockRoutes()

    renderPage()

    await screen.findByText('Graphs')

    const callGraph = screen.getByRole('radio', { name: 'Call graph' })
    callGraph.click()

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/graphs/call'),
      expect.anything(),
    )
  })

  it('shows an error alert when the analysis fails to load', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/analysis/an-1') && !url.includes('/graphs/')) {
        return Promise.resolve(jsonResponse({ detail: 'boom' }, false))
      }
      return Promise.resolve(jsonResponse({}))
    })

    renderPage()

    expect(await screen.findByText('Failed to load analysis')).toBeInTheDocument()
  })
})
