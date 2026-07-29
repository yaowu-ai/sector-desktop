import { Tag } from 'antd'
import type { ReactNode } from 'react'

export type StatusTone = 'ok' | 'error' | 'running' | 'warning' | 'idle'

const colorByStatus: Record<StatusTone, string> = {
  ok: 'green',
  error: 'red',
  running: 'blue',
  warning: 'gold',
  idle: 'default',
}

interface StatusTagProps {
  status: StatusTone
  label: ReactNode
}

export function StatusTag({ status, label }: StatusTagProps) {
  return <Tag color={colorByStatus[status]}>{label}</Tag>
}
