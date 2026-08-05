import { useCallback, useEffect, useRef, useState } from 'react'

interface PollingOptions<T> {
  /** Milliseconds between polls. Defaults to 3000. */
  interval?: number
  /** Stop polling once this predicate returns true (e.g. terminal status). */
  done?: (data: T) => boolean
  /**
   * Values captured by `loader` that should restart polling when they change
   * (e.g. the selected language or project id). Each change triggers an
   * immediate fetch using the latest `loader`.
   */
  deps?: readonly unknown[]
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
 * The latest `loader`/`done` closures are read on every poll, so polling never
 * restarts (and never hammers the server) merely because a caller re-created
 * an inline function on a re-render. Pass the values `loader` captures via
 * `deps` to restart polling when they change. `refresh` re-runs the loader
 * immediately (used by retry buttons and after a user triggers a background
 * job). State is not updated after unmount.
 */
export function usePolling<T>(
  loader: () => Promise<T>,
  options: PollingOptions<T> = {},
): PollingResult<T> {
  const { interval = 3000, deps = [] } = options

  const loaderRef = useRef(loader)
  const doneRef = useRef(options.done)
  useEffect(() => {
    loaderRef.current = loader
  })
  useEffect(() => {
    doneRef.current = options.done
  })

  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const cancelledRef = useRef(false)
  const timerRef = useRef<number | undefined>(undefined)

  // Restart polling when a captured input changes. Comparing element-wise
  // keeps polling stable across renders that merely recreate the `deps`
  // array with the same values.
  const [prevDeps, setPrevDeps] = useState(deps)
  const [restartToken, setRestartToken] = useState(0)
  if (prevDeps.length !== deps.length || deps.some((value, index) => !Object.is(value, prevDeps[index]))) {
    setPrevDeps(deps)
    setRestartToken((token) => token + 1)
  }

  const run = useCallback(async () => {
    try {
      const result = await loaderRef.current()
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
  }, [])

  useEffect(() => {
    cancelledRef.current = false

    const tick = async () => {
      const result = await run()
      if (cancelledRef.current) return
      const done = doneRef.current
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
  }, [run, interval, restartToken])

  const refresh = useCallback(async () => {
    if (timerRef.current !== undefined) {
      window.clearTimeout(timerRef.current)
    }
    await run()
  }, [run])

  return { data, error, loading, refresh }
}
