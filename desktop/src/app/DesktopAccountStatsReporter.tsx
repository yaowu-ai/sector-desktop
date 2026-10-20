import { useEffect, useRef } from 'react'

import { queryAccountCoverage } from '../services/api'
import { reportDesktopAccountStats } from '../services/desktopApi'
import { useDesktopAuth } from './DesktopAuthContext'

const REPORT_INTERVAL_MS = 60 * 60 * 1000
const RETRY_INTERVAL_MS = 60 * 1000

/** Runs regardless of the active page. Only reads local SQLite; never starts TikTok collection. */
export function DesktopAccountStatsReporter() {
  const auth = useDesktopAuth()
  const current = useRef(auth)
  current.current = auth
  const userId = auth.session?.userId
  const ready = auth.device?.status === 'active' && auth.license?.status === 'active'
  useEffect(() => {
    if (!userId || !ready) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    const report = async () => {
      let delay = REPORT_INTERVAL_MS
      try {
        const metrics = await queryAccountCoverage('tiktok')
        const latest = current.current
        if (cancelled || latest.session?.userId !== userId || latest.license?.status !== 'active') return
        await reportDesktopAccountStats({ session: latest.session, apiBaseUrl: latest.apiBaseUrl,
          metrics, observedAt: new Date().toISOString() })
      } catch { delay = RETRY_INTERVAL_MS }
      if (!cancelled) timer = setTimeout(report, delay)
    }
    void report()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [userId, ready, auth.apiBaseUrl])
  return null
}
