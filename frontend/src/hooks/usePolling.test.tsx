import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { usePolling } from './usePolling'

function Harness({
  loader,
  interval = 1000,
  done,
  deps,
}: {
  loader: () => Promise<string | null>
  interval?: number
  done?: (data: string | null) => boolean
  deps?: readonly unknown[]
}) {
  const { data, error, loading, refresh } = usePolling(loader, { interval, done, deps })
  return (
    <div>
      <span data-testid="data">{data ?? 'null'}</span>
      <span data-testid="error">{error ?? 'null'}</span>
      <span data-testid="loading">{String(loading)}</span>
      <button onClick={() => void refresh()}>refresh</button>
    </div>
  )
}

afterEach(() => {
  vi.useRealTimers()
})

describe('usePolling', () => {
  it('fetches immediately on mount', async () => {
    vi.useFakeTimers()
    let calls = 0
    render(
      <Harness
        loader={() => {
          calls += 1
          return Promise.resolve('value')
        }}
      />,
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(screen.getByTestId('data')).toHaveTextContent('value')
    expect(calls).toBe(1)
  })

  it('does not refetch when the loader closure is recreated on a re-render', async () => {
    vi.useFakeTimers()
    let calls = 0
    const { rerender } = render(
      <Harness
        loader={() => {
          calls += 1
          return Promise.resolve('value')
        }}
      />,
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(calls).toBe(1)

    rerender(
      <Harness
        loader={() => {
          calls += 1
          return Promise.resolve('value')
        }}
      />,
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(calls).toBe(1)
  })

  it('polls again after the configured interval', async () => {
    vi.useFakeTimers()
    let calls = 0
    render(
      <Harness
        interval={500}
        loader={() => {
          calls += 1
          return Promise.resolve('value')
        }}
      />,
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(calls).toBe(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(500)
    })
    expect(calls).toBe(2)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(500)
    })
    expect(calls).toBe(3)
  })

  it('stops polling once the done predicate is satisfied', async () => {
    vi.useFakeTimers()
    let calls = 0
    render(
      <Harness
        interval={500}
        loader={() => {
          calls += 1
          return Promise.resolve('ready')
        }}
        done={(data) => data === 'ready'}
      />,
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(calls).toBe(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000)
    })
    expect(calls).toBe(1)
  })

  it('restarts polling immediately when deps change', async () => {
    vi.useFakeTimers()
    let calls = 0
    const { rerender } = render(
      <Harness
        interval={5000}
        deps={['a']}
        loader={() => {
          calls += 1
          return Promise.resolve('value')
        }}
      />,
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(calls).toBe(1)

    rerender(
      <Harness
        interval={5000}
        deps={['b']}
        loader={() => {
          calls += 1
          return Promise.resolve('value')
        }}
      />,
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(calls).toBe(2)
  })

  it('does not restart when a re-created deps array has identical elements', async () => {
    vi.useFakeTimers()
    let calls = 0
    const { rerender } = render(
      <Harness
        interval={500}
        deps={['x']}
        loader={() => {
          calls += 1
          return Promise.resolve('value')
        }}
      />,
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(calls).toBe(1)

    rerender(
      <Harness
        interval={500}
        deps={['x']}
        loader={() => {
          calls += 1
          return Promise.resolve('value')
        }}
      />,
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(calls).toBe(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(500)
    })
    expect(calls).toBe(2)
  })

  it('refresh fetches immediately even after polling has stopped', async () => {
    vi.useFakeTimers()
    let calls = 0
    render(
      <Harness
        interval={500}
        loader={() => {
          calls += 1
          return Promise.resolve('ready')
        }}
        done={(data) => data === 'ready'}
      />,
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(calls).toBe(1)

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'refresh' }))
    })
    expect(calls).toBe(2)
  })
})
