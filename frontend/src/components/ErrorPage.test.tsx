import { screen } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../test/render'
import { ErrorPage } from './ErrorPage'

function ThrowingPage(): never {
  throw new Error('boom')
}

describe('ErrorPage', () => {
  it('renders the route fallback when a matched route throws', async () => {
    const router = createMemoryRouter(
      [
        {
          errorElement: <ErrorPage />,
          children: [{ path: '/', element: <ThrowingPage /> }],
        },
      ],
      { initialEntries: ['/'] },
    )

    renderWithProviders(<RouterProvider router={router} />)

    expect(await screen.findByText('boom')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to dashboard/i })).toBeInTheDocument()
  })
})
