import { Empty, Space, Tabs, Tooltip, message } from 'antd'
import clsx from 'clsx'
import { Copy, Download } from 'lucide-react'
import { useEffect, useState } from 'react'

import { exportLogFile } from '../services/api'

interface LogViewerProps {
  stdout?: string
  stderr?: string
  running?: boolean
  preferStderr?: boolean
}

interface LogBlockProps {
  value?: string
  tone?: 'error'
  filename: string
  emptyDescription?: string
  className?: string
  contentClassName?: string
}

export function LogBlock({
  value,
  tone,
  filename,
  emptyDescription = '暂无输出',
  className,
  contentClassName,
}: LogBlockProps) {
  if (!value) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyDescription} />
  }

  return (
    <div className={clsx('log-block', className)}>
      <LogActions value={value} filename={filename} />
      <pre className={clsx('log-viewer', tone === 'error' && 'log-viewer-error', contentClassName)}>
        {value}
      </pre>
    </div>
  )
}

export function LogViewer({ stdout, stderr, running, preferStderr }: LogViewerProps) {
  const [activeKey, setActiveKey] = useState(preferStderr && stderr ? 'stderr' : 'stdout')

  useEffect(() => {
    if (preferStderr && stderr) {
      setActiveKey('stderr')
    }
  }, [preferStderr, stderr])

  return (
    <Tabs
      activeKey={activeKey}
      className={running ? 'is-running' : undefined}
      onChange={setActiveKey}
      items={[
        {
          key: 'stdout',
          label: (
            <Tooltip title="stdout：标准输出，程序正常输出的信息。">
              <span>stdout</span>
            </Tooltip>
          ),
          children: <LogBlock value={stdout} filename="stdout.log" />,
        },
        {
          key: 'stderr',
          label: (
            <Tooltip title="stderr：标准错误，程序错误、警告或诊断信息。">
              <span>stderr</span>
            </Tooltip>
          ),
          children: <LogBlock value={stderr} tone="error" filename="stderr.log" />,
        },
      ]}
    />
  )
}

function LogActions({ value, filename }: { value: string; filename: string }) {
  const copyLog = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value)
      } else {
        copyTextFallback(value)
      }
      message.success('日志已复制')
    } catch (error) {
      try {
        copyTextFallback(value)
        message.success('日志已复制')
      } catch (fallbackError) {
        message.error(fallbackError instanceof Error ? fallbackError.message : String(fallbackError))
      }
    }
  }

  const downloadLog = async () => {
    try {
      const result = await exportLogFile(filename, value)
      if (result.cancelled) {
        return
      }
      message.success(result.path ? `日志已保存：${result.path}` : '日志已保存')
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <Space className="log-actions" size={6}>
      <Tooltip title="复制日志">
        <button
          aria-label="复制日志"
          className="log-action-icon"
          type="button"
          onClick={() => void copyLog()}
        >
          <Copy size={16} />
        </button>
      </Tooltip>
      <Tooltip title="下载日志">
        <button
          aria-label="下载日志"
          className="log-action-icon"
          type="button"
          onClick={() => void downloadLog()}
        >
          <Download size={16} />
        </button>
      </Tooltip>
    </Space>
  )
}

function copyTextFallback(value: string) {
  const textarea = document.createElement('textarea')
  textarea.value = value
  textarea.setAttribute('readonly', 'true')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  textarea.remove()
  if (!copied) {
    throw new Error('复制日志失败')
  }
}
