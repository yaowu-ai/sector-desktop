import { useEffect, useState } from 'react';
import { getCurrentRunStatus, PROCESS_STARTED_EVENT } from '../services/api';
import type { ProcessStatus } from '../services/types';

export function usePublishingRun() {
  const [status, setStatus] = useState<ProcessStatus | null>(null);
  useEffect(() => {
    let active = true;
    const refresh = () => { void getCurrentRunStatus().then(value => { if (active) setStatus(value); }).catch(() => { /* The output panel owns detailed connection errors. */ }); };
    refresh();
    const timer = window.setInterval(refresh, 1500);
    window.addEventListener(PROCESS_STARTED_EVENT, refresh);
    return () => { active = false; window.clearInterval(timer); window.removeEventListener(PROCESS_STARTED_EVENT, refresh); };
  }, []);
  return { status, busy: !status || ['starting', 'running', 'pause_pending', 'intervention_required', 'stopping'].includes(status.status) };
}
