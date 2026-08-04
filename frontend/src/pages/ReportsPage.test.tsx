import { fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/render'
import { ReportsPage } from './ReportsPage'

const mockFetch = vi.fn()

vi.stubGlobal('fetch', mockFetch)

function jsonResponse(payload: unknown, ok = true) {
  return new Response(JSON.stringify(payload), {
    status: ok ? 200 : 500,
    headers: { 'Content-Type': 'application/json' },
  })
}

const project = {
  id: 'proj-1',
  name: 'demo',
  source: 'local',
  root_path: '/workspace/demo',
  file_count: 3,
  source_file_count: 3,
  total_size_bytes: 1024,
  languages: ['Python'],
  created_at: '2026-07-24T12:00:00Z',
}

const localization = {
  project_id: 'proj-1',
  status: 'ready',
  created_at: '2026-07-24T12:00:00Z',
  updated_at: '2026-07-24T12:01:00Z',
  error: null,
  resolved: true,
  confidence: 0.85,
  summary: 'The failure originates in the payment handler.',
  root_cause: {
    node_id: 'n1',
    label: 'main.py:pay',
    kind: 'function',
    score: 0.9,
    evidence: [{ source: 'trace', description: 'Raised exception here', score: 0.9 }],
    reason: 'Exception raised on this line',
  },
  candidates: [
    {
      node_id: 'n1',
      label: 'main.py:pay',
      kind: 'function',
      score: 0.9,
      evidence: [{ source: 'trace', description: 'Raised exception here', score: 0.9 }],
      reason: 'Exception raised on this line',
    },
  ],
  propagation_path: ['n1'],
  evidence_summary: [{ source: 'trace', description: 'Raised exception here', score: 0.9 }],
  missing_sources: [],
  suggested_fix: null,
}

const explanation = {
  project_id: 'proj-1',
  status: 'ready',
  created_at: '2026-07-24T12:00:00Z',
  updated_at: '2026-07-24T12:01:00Z',
  error: null,
  resolved: true,
  error_summary: 'ValueError raised in pay()',
  root_cause: 'main.py:42',
  why: 'The discount lookup returns None for unknown codes.',
  where: [{ file: 'main.py', function: 'pay', cls: '', line: 42 }],
  evidence: [{ source: 'trace', description: 'Lookup returned None', score: 0.8 }],
  suggested_fix: null,
  confidence: 0.75,
  propagation_path: [],
  missing_sources: [],
}

function mockRoutes(overrides: Record<string, unknown> = {}) {
  mockFetch.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.includes('/projects')) return Promise.resolve(jsonResponse([project]))
    if (url.includes('/localization/proj-1')) {
      if ((init?.method ?? 'GET') === 'POST') {
        return Promise.resolve(jsonResponse(overrides.localization ?? localization))
      }
      return Promise.resolve(jsonResponse(overrides.localization ?? localization))
    }
    if (url.includes('/explanation/proj-1')) {
      return Promise.resolve(jsonResponse(overrides.explanation ?? explanation))
    }
    return Promise.resolve(jsonResponse({ detail: `no mock for ${url}` }, false))
  })
}

afterEach(() => {
  vi.clearAllMocks()
})

function renderPage() {
  return renderWithProviders(
    <MemoryRouter>
      <ReportsPage />
    </MemoryRouter>,
  )
}

async function selectProject() {
  const user = userEvent.setup()
  await user.click(screen.getByRole('combobox'))
  // Mantine v9 renders the Select dropdown with display:none in jsdom, so the
  // option never becomes "visible"; query it as hidden and click it directly.
  const option = await screen.findByRole('option', { name: 'demo', hidden: true })
  fireEvent.click(option)
  return user
}

describe('ReportsPage', () => {
  it('prompts to select a project before showing reports', async () => {
    mockRoutes()

    renderPage()

    expect(
      await screen.findByText('Choose a project above to generate its debug report.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Localize' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Explain' })).toBeDisabled()
  })

  it('loads localization and explanation once a project is selected', async () => {
    mockRoutes()

    renderPage()

    await selectProject()

    expect(await screen.findByText('Root-cause localization')).toBeInTheDocument()
    expect(await screen.findByText('85%')).toBeInTheDocument()
    expect(
      await screen.findByText('The failure originates in the payment handler.'),
    ).toBeInTheDocument()
    expect(
      await screen.findByText('The discount lookup returns None for unknown codes.'),
    ).toBeInTheDocument()
  })

  it('runs localization and refreshes the report', async () => {
    mockRoutes()

    renderPage()

    const user = await selectProject()

    const localize = await screen.findByRole('button', { name: 'Localize' })
    await user.click(localize)

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/localization/proj-1'),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(await screen.findByText('85%')).toBeInTheDocument()
  })

  it('runs explanation and refreshes the report', async () => {
    mockRoutes()

    renderPage()

    const user = await selectProject()

    const explain = await screen.findByRole('button', { name: 'Explain' })
    await user.click(explain)

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/explanation/proj-1'),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(
      await screen.findByText('The discount lookup returns None for unknown codes.'),
    ).toBeInTheDocument()
  })

  it('shows an error alert when loading localization fails', async () => {
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/projects')) return Promise.resolve(jsonResponse([project]))
      if (url.includes('/localization/proj-1')) {
        return Promise.resolve(jsonResponse({ detail: 'boom' }, false))
      }
      if (url.includes('/explanation/proj-1')) {
        return Promise.resolve(jsonResponse(explanation))
      }
      return Promise.resolve(jsonResponse({ detail: `no mock for ${url}` }, false))
    })

    renderPage()

    await selectProject()

    expect(await screen.findByText('Failed to load localization')).toBeInTheDocument()
  })
})
