/** Run one refresh at a time; coalesce waiting requests to the newest scope. */
export function createRefreshQueue() {
  let running = false
  let pending: {
    task: () => Promise<void>
    waiters: Array<{ resolve: () => void; reject: (error: unknown) => void }>
  } | undefined

  async function drain() {
    running = true
    while (pending) {
      const current = pending
      pending = undefined
      try {
        await current.task()
        current.waiters.forEach(waiter => waiter.resolve())
      } catch (error) {
        current.waiters.forEach(waiter => waiter.reject(error))
      }
    }
    running = false
  }

  return (task: () => Promise<void>) => new Promise<void>((resolve, reject) => {
    if (pending) {
      pending.task = task
      pending.waiters.push({ resolve, reject })
    } else {
      pending = { task, waiters: [{ resolve, reject }] }
    }
    if (!running) void drain()
  })
}
