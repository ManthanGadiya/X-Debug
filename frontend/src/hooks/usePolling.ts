import { useCallback, useEffect, useRef, useState } from 'react'

interface PollingOptions<T> {
  /** Milliseconds between polls. Defaults to 3000. */
  interval?: number
  /** Stop polling once this predicate returns true (e.g. terminal status). */
  done?: (data: T) => boolean
}

interface PollingResult<T> {
  data: T | null
  error: string | null
  loading: boolean
  refresh: () => Promise<void>
}

/**
 * Poll a fetch function until a terminal condition is reached.
 *
 * The first fetch fires immediately; subsequent fetches wait `interval` ms.
 * `refresh` re-runs the loader immediately (used by retry buttons and after
 * a user triggers a background job). State is not updated after unmount.
 */
export function usePolling<T>(
  loader: () => Promise<T>,
  options: PollingOptions<T> = {},
): PollingResult<T> {
  const { interval = 3000, done } = options
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const cancelledRef = useRef(false)
  const timerRef = useRef<number | undefined>(undefined)

  const run = useCallback(async () => {
    try {
      const result = await loader()
      if (cancelledRef.current) return
      setData(result)
      setError(null)
      setLoading(false)
      return result
    } catch (cause: unknown) {
      if (cancelledRef.current) return
      setError(cause instanceof Error ? cause.message : 'Unknown error')
      setLoading(false)
      return null
    }
  }, [loader])

  useEffect(() => {
    cancelledRef.current = false

    const tick = async () => {
      const result = await run()
      if (cancelledRef.current) return
      if (result != null && done && done(result)) return
      timerRef.current = window.setTimeout(tick, interval)
    }

    void tick()
    return () => {
      cancelledRef.current = true
      if (timerRef.current !== undefined) {
        window.clearTimeout(timerRef.current)
      }
    }
  }, [run, interval, done])

  const refresh = useCallback(async () => {
    if (timerRef.current !== undefined) {
      window.clearTimeout(timerRef.current)
    }
    await run()
  }, [run])

  return { data, error, loading, refresh }
}
