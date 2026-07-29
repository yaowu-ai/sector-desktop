import { useCallback, useEffect, useRef, useState } from 'react'

import { getCurrentRunStatus } from '../services/api'
import type { BrowserPreview, ProcessStartResult, ProcessStatus, RunStatus } from '../services/types'

const TERMINAL_STATUS: RunStatus[] = ['completed', 'partial_failed', 'failed', 'stopped', 'idle']

interface UseBrowserPreviewOptions {
  pollMs?: number
  closeOnTerminal?: boolean
  onTerminal?: (status: ProcessStatus) => void | Promise<void>
  onError?: (error: unknown) => void
}

export function useBrowserPreview({
  pollMs = 1500,
  closeOnTerminal = true,
  onTerminal,
  onError,
}: UseBrowserPreviewOptions = {}) {
  const [previewOpen, setPreviewOpen] = useState(false)
  const [preview, setPreview] = useState<BrowserPreview>()
  const [watching, setWatching] = useState(false)
  const expectedProcessIdRef = useRef<number>()
  const expectedTaskTypeRef = useRef<string>()
  const previewResolvedRef = useRef(false)
  const onTerminalRef = useRef(onTerminal)
  const onErrorRef = useRef(onError)

  useEffect(() => {
    onTerminalRef.current = onTerminal
  }, [onTerminal])

  useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  const closePreview = useCallback(() => {
    setPreviewOpen(false)
  }, [])

  const openBrowserPreview = useCallback((nextPreview: BrowserPreview) => {
    expectedProcessIdRef.current = undefined
    expectedTaskTypeRef.current = undefined
    previewResolvedRef.current = true
    setWatching(false)
    setPreview(nextPreview)
    setPreviewOpen(true)
  }, [])

  const watchProcessPreview = useCallback((result: ProcessStartResult) => {
    expectedProcessIdRef.current = result.processId
    expectedTaskTypeRef.current = result.taskType
    previewResolvedRef.current = false
    setPreview(undefined)
    setPreviewOpen(true)
    setWatching(true)
  }, [])

  useEffect(() => {
    if (!watching) {
      return undefined
    }

    const matchesExpectedRun = (status: ProcessStatus) => {
      const expectedProcessId = expectedProcessIdRef.current
      if (expectedProcessId && status.processId !== expectedProcessId) {
        return false
      }

      const expectedTaskType = expectedTaskTypeRef.current
      if (!expectedProcessId && expectedTaskType && status.taskType && status.taskType !== expectedTaskType) {
        return false
      }

      return true
    }

    const poll = async () => {
      try {
        const status = await getCurrentRunStatus()
        if (!matchesExpectedRun(status)) {
          return
        }

        if (status.browserPreview && !previewResolvedRef.current) {
          previewResolvedRef.current = true
          setPreview(status.browserPreview)
          setPreviewOpen(true)
        }

        if (TERMINAL_STATUS.includes(status.status)) {
          setWatching(false)
          if (closeOnTerminal) {
            setPreviewOpen(false)
            setPreview(undefined)
          }
          await onTerminalRef.current?.(status)
        }
      } catch (error) {
        onErrorRef.current?.(error)
      }
    }

    void poll()
    const timer = window.setInterval(() => {
      void poll()
    }, pollMs)

    return () => window.clearInterval(timer)
  }, [closeOnTerminal, pollMs, watching])

  return {
    preview,
    previewOpen,
    closePreview,
    openBrowserPreview,
    watchProcessPreview,
  }
}
