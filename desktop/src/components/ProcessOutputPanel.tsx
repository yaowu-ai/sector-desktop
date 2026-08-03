import { Alert, Button, Card, Descriptions, Drawer, Space, Typography, message } from 'antd'
import { PauseCircle, Square, Terminal } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  continueAuthIntervention,
  getCurrentRunStatus,
  getStderrChunk,
  getStdoutChunk,
  skipAuthIntervention,
  stopCurrentRun,
} from '../services/api'
import { runStatusLabel } from '../services/runStatus'
import type { ProcessStatus } from '../services/types'
import { confirmDanger } from './ConfirmDanger'
import { LogViewer } from './LogViewer'
import { StatusTag } from './StatusTag'

interface ProcessOutputPanelProps {
  title?: string
}

export function ProcessOutputPanel({ title = '运行输出' }: ProcessOutputPanelProps) {
  const [status, setStatus] = useState<ProcessStatus | null>(null)
  const [stdoutOffset, setStdoutOffset] = useState(0)
  const [stderrOffset, setStderrOffset] = useState(0)
  const [stdout, setStdout] = useState('')
  const [stderr, setStderr] = useState('')
  const [stopping, setStopping] = useState(false)
  const [outputOpen, setOutputOpen] = useState(false)
  const observedRegistrationRunRef = useRef<string | null>(null)
  const notifiedRegistrationRunRef = useRef<string | null>(null)

  const refresh = useCallback(async () => {
    const nextStatus = await getCurrentRunStatus()
    setStatus((current) => {
      if (current?.processId !== nextStatus.processId) {
        setStdoutOffset(0)
        setStderrOffset(0)
        if (nextStatus.processId) {
          setStdout('')
          setStderr('')
        }
      }
      return nextStatus
    })

    const [stdoutChunk, stderrChunk] = await Promise.all([
      getStdoutChunk(stdoutOffset),
      getStderrChunk(stderrOffset),
    ])
    setStdoutOffset(stdoutChunk.nextOffset)
    setStderrOffset(stderrChunk.nextOffset)
    if (stdoutChunk.content) {
      setStdout((current) => `${current}${stdoutChunk.content}`.slice(-12000))
    }
    if (stderrChunk.content) {
      setStderr((current) => `${current}${stderrChunk.content}`.slice(-12000))
    }
  }, [stderrOffset, stdoutOffset])

  useEffect(() => {
    void refresh().catch(handleError)
    const id = window.setInterval(() => {
      void refresh().catch(handleError)
    }, 1500)
    return () => window.clearInterval(id)
  }, [refresh])

  useEffect(() => {
    if (status?.taskType !== 'tiktok_register') {
      return
    }
    const runKey = status.startedAt ?? status.endedAt ?? String(status.processId ?? 'unknown')
    if (['starting', 'running', 'pause_pending', 'intervention_required'].includes(status.status)) {
      observedRegistrationRunRef.current = runKey
      return
    }
    if (
      !['completed', 'failed', 'partial_failed', 'stopped'].includes(status.status) ||
      observedRegistrationRunRef.current !== runKey ||
      notifiedRegistrationRunRef.current === runKey
    ) {
      return
    }

    const outcome = parseRegistrationBatchOutcome(stdout)
    if (status.status === 'completed' && !outcome) {
      return
    }

    notifiedRegistrationRunRef.current = runKey
    if (status.status === 'stopped') {
      message.warning('注册任务已停止')
      return
    }
    if (status.status === 'failed' || status.status === 'partial_failed') {
      message.error(`注册失败：${status.error ?? '任务未完整完成'}`)
      return
    }
    if (outcome?.failed) {
      message.error(`注册失败：${outcome.ok}/${outcome.total} 完成，${outcome.failed} 个失败`)
      return
    }
    message.success(`注册完成：${outcome?.ok ?? status.completedAccounts.length}/${outcome?.total ?? status.completedAccounts.length} 个账号`)
  }, [status, stdout])

  const stopAfterCurrent = async () => {
    setStopping(true)
    try {
      const result = await stopCurrentRun(false)
      message.success(result.message)
      await refresh()
    } catch (error) {
      handleError(error)
    } finally {
      setStopping(false)
    }
  }

  const forceStop = () => {
    confirmDanger({
      title: '强制停止当前任务',
      content: '将直接终止当前 Python 进程，日志和数据库记录可能不完整。',
      onOk: () => {
        void (async () => {
          setStopping(true)
          try {
            const result = await stopCurrentRun(true)
            message.success(result.message)
            await refresh()
          } catch (error) {
            handleError(error)
          } finally {
            setStopping(false)
          }
        })()
      },
    })
  }

  const continueIntervention = async () => {
    setStopping(true)
    try {
      const result = await continueAuthIntervention()
      message.success(result.message)
      await refresh()
    } catch (error) {
      handleError(error)
    } finally {
      setStopping(false)
    }
  }

  const skipIntervention = async () => {
    setStopping(true)
    try {
      const result = await skipAuthIntervention()
      message.success(result.message)
      await refresh()
    } catch (error) {
      handleError(error)
    } finally {
      setStopping(false)
    }
  }

  const running = Boolean(status && ['starting', 'running', 'pause_pending', 'intervention_required'].includes(status.status))
  const filteredStdout = useMemo(() => filterPersistedSessionLogLines(stdout), [stdout])
  const latestStderrLine = useMemo(() => latestNonEmptyLine(stderr), [stderr])
  const visibleOutputCount = Number(Boolean(filteredStdout)) + Number(Boolean(stderr))
  const outputButtonLabel = stderr ? '查看 stderr' : visibleOutputCount ? `查看输出 (${visibleOutputCount})` : '查看输出'

  return (
    <>
      <Card
        title={title}
        size="small"
        extra={
          <Space wrap>
            <StatusTag status={statusTone(status)} label={runStatusLabel(status?.status)} />
            <Button icon={<Terminal size={16} />} onClick={() => setOutputOpen(true)}>
              {outputButtonLabel}
            </Button>
            <Button
              icon={<PauseCircle size={16} />}
              disabled={!running}
              loading={stopping}
              onClick={() => void stopAfterCurrent()}
            >
              暂停后续
            </Button>
            <Button danger icon={<Square size={16} />} disabled={!running} loading={stopping} onClick={forceStop}>
              强制停止
            </Button>
          </Space>
        }
      >
        <Space wrap size={[16, 8]}>
          <Typography.Text type="secondary">PID：{status?.processId ?? '-'}</Typography.Text>
          <Typography.Text type="secondary">账号：{status?.accountId ?? '-'}</Typography.Text>
          <Typography.Text type="secondary">队列：{status?.queuedAccounts.length ?? 0}</Typography.Text>
          <Typography.Text type="secondary">已完成：{status?.completedAccounts.length ?? 0}</Typography.Text>
          {status?.error ? <Typography.Text type="danger">{status.error}</Typography.Text> : null}
        </Space>
        {stderr ? (
          <Alert
            type="error"
            showIcon
            style={{ marginTop: 12 }}
            message="stderr 有输出"
            description={latestStderrLine || '标准错误流已有输出，请查看详情。'}
            action={
              <Button danger size="small" onClick={() => setOutputOpen(true)}>
                查看 stderr
              </Button>
            }
          />
        ) : null}
        {status?.authIntervention ? (
          <Alert
            type="warning"
            showIcon
            style={{ marginTop: 12 }}
            message={`Manual auth required: ${status.authIntervention.state}`}
            description={
              <Space direction="vertical" size={8} className="full-width">
                <Typography.Text>
                  {status.authIntervention.accountId}: {status.authIntervention.detail || status.authIntervention.reason}
                </Typography.Text>
                {status.authIntervention.url ? (
                  <Typography.Text type="secondary">{status.authIntervention.url}</Typography.Text>
                ) : null}
                <Space wrap>
                  <Button type="primary" loading={stopping} onClick={() => void continueIntervention()}>
                    我已完成，继续检测
                  </Button>
                  <Button loading={stopping} onClick={() => void skipIntervention()}>
                    跳过当前账号
                  </Button>
                  <Button danger loading={stopping} onClick={forceStop}>
                    停止任务
                  </Button>
                </Space>
              </Space>
            }
          />
        ) : null}
      </Card>
      <Drawer
        title={title}
        open={outputOpen}
        width="min(960px, 92vw)"
        destroyOnClose={false}
        onClose={() => setOutputOpen(false)}
      >
        {status ? (
          <Descriptions size="small" column={2} bordered style={{ marginBottom: 12 }}>
            <Descriptions.Item label="PID">{status.processId ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="账号">{status.accountId ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="队列">{status.queuedAccounts.length}</Descriptions.Item>
            <Descriptions.Item label="已完成">{status.completedAccounts.length}</Descriptions.Item>
            <Descriptions.Item label="命令" span={2}>
              {status.command.length ? <Typography.Text code>{formatDisplayCommand(status.command)}</Typography.Text> : '-'}
            </Descriptions.Item>
            {status.error ? (
              <Descriptions.Item label="错误" span={2}>
                <Typography.Text type="danger">{status.error}</Typography.Text>
              </Descriptions.Item>
            ) : null}
          </Descriptions>
        ) : null}
        <LogViewer stdout={filteredStdout} stderr={stderr} running={running} preferStderr={Boolean(stderr)} />
      </Drawer>
    </>
  )
}

const PERSISTED_SESSION_LOG_LINE_RE = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| [a-z][a-z0-9_-]* \| /i

function formatDisplayCommand(command: string[]) {
  return command.map((part, index) => sanitizeCommandPart(part, command[index - 1], index)).join(' ')
}

function sanitizeCommandPart(part: string, previousPart: string | undefined, index: number) {
  if (index === 0 || /account-matrix-runtime\.exe$/i.test(part)) {
    return 'account-matrix-runtime.exe'
  }
  if (previousPart === '--config') {
    return '<配置文件>'
  }
  if (previousPart === '--data-dir') {
    return '<数据目录>'
  }
  if (isLocalPath(part)) {
    return '<本地路径>'
  }
  return part
}

function isLocalPath(value: string) {
  const normalized = value.replace(/^\/\/\?\//, '').replace(/^\\\\\?\\/, '')
  return (
    /^[a-zA-Z]:[\\/]/.test(normalized) ||
    normalized.includes('/AppData/') ||
    normalized.includes('\\AppData\\') ||
    normalized.startsWith('/Users/') ||
    normalized.startsWith('/home/')
  )
}

function filterPersistedSessionLogLines(value: string) {
  if (!value) {
    return value
  }
  return value
    .split(/\r?\n/)
    .filter((line) => !PERSISTED_SESSION_LOG_LINE_RE.test(line))
    .join('\n')
    .trimEnd()
}

function latestNonEmptyLine(value: string) {
  const lines = value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
  return lines[lines.length - 1]
}

function parseRegistrationBatchOutcome(value: string) {
  const match = value.match(
    /BATCH END \| (?:\[ERR\] )?Account Matrix 注册: (\d+)\/(\d+) 完成(?:, (\d+) 失败)?/,
  )
  if (!match) {
    return null
  }
  return {
    ok: Number(match[1]),
    total: Number(match[2]),
    failed: Number(match[3] ?? 0),
  }
}

function statusTone(status: ProcessStatus | null) {
  if (!status || status.status === 'idle' || status.status === 'completed') {
    return 'idle'
  }
  if (status.status === 'running' || status.status === 'starting') {
    return 'running'
  }
  if (status.status === 'failed' || status.status === 'partial_failed') {
    return 'error'
  }
  return 'warning'
}

function handleError(error: unknown) {
  message.error(error instanceof Error ? error.message : String(error))
}
