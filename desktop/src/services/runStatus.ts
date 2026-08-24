import type { RunStatus } from './types'


const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  idle: '\u7a7a\u95f2',
  starting: '\u542f\u52a8\u4e2d',
  running: '\u8fd0\u884c\u4e2d',
  pause_pending: '\u6b63\u5728\u6682\u505c',
  intervention_required: '\u9700\u8981\u4eba\u5de5\u5904\u7406',
  completed: '\u5df2\u5b8c\u6210',
  partial_failed: '\u90e8\u5206\u5931\u8d25',
  failed: '\u5931\u8d25',
  stopped: '\u5df2\u505c\u6b62',
}


export function runStatusLabel(status: RunStatus | null | undefined) {
  return status ? RUN_STATUS_LABELS[status] : RUN_STATUS_LABELS.idle
}
