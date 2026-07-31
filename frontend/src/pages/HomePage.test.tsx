import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/render'
import { HomePage } from './HomePage'

const mockFetch = vi.fn()

vi.stubGlobal('fetch', mockFetch)

afterEach(() => {
  vi.clearAllMocks()
})

function renderPage() {
  return renderWithProviders(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  )
}

describe('HomePage', () => {
  it('renders the page title and description', () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'ok',
        app: 'XDebug API',
        version: '0.1.0',
        environment: 'test',
      }),
    })

    renderPage()

    expect(screen.getByRole('heading', { name: /dashboard/i })).toBeInTheDocument()
  })

  it('displays backend health information when available', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'ok',
        app: 'XDebug API',
        version: '0.1.0',
        environment: 'test',
      }),
    })

    renderPage()

    expect(await screen.findByText('XDebug API')).toBeInTheDocument()
    expect(screen.getByText('ok')).toBeInTheDocument()
    expect(screen.getByText('0.1.0')).toBeInTheDocument()
  })

  it('shows an error when the backend is unreachable', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
    })

    renderPage()

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Backend unreachable')).toBeInTheDocument()
  })

  it('re-checks health when the refresh button is clicked', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'ok',
        app: 'XDebug API',
        version: '0.1.0',
        environment: 'test',
      }),
    })

    renderPage()

    const refresh = screen.getByRole('button', { name: /refresh/i })
    await userEvent.click(refresh)

    expect(mockFetch).toHaveBeenCalledTimes(2)
  })
})
