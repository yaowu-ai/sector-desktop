import { Alert, Modal, Space, Spin, Typography } from 'antd'
import { useEffect, useState } from 'react'

import { captureBrowserPreview } from '../services/api'
import type { BrowserPreview } from '../services/types'

interface BrowserPreviewModalProps {
  open: boolean
  preview?: BrowserPreview
  onClose: () => void
}

type ConnectionState = 'idle' | 'connecting' | 'live' | 'error'

export function BrowserPreviewModal({ open, preview, onClose }: BrowserPreviewModalProps) {
  const [frame, setFrame] = useState<string>()
  const [state, setState] = useState<ConnectionState>('idle')
  const [error, setError] = useState<string>()

  useEffect(() => {
    setFrame(undefined)
    setError(undefined)

    if (!open || !preview?.cdpEndpoint) {
      setState('idle')
      return undefined
    }

    let cancelled = false
    let inFlight = false

    const capture = async () => {
      if (cancelled || inFlight) {
        return
      }
      inFlight = true
      setState((current) => (current === 'live' ? current : 'connecting'))
      try {
        const result = await captureBrowserPreview({ cdpEndpoint: preview.cdpEndpoint })
        if (!cancelled) {
          setFrame(result.dataUrl)
          setState('live')
          setError(undefined)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err))
          setState('error')
        }
      } finally {
        inFlight = false
      }
    }

    void capture()
    const id = window.setInterval(() => void capture(), 1000)

    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [open, preview?.cdpEndpoint])

  const title = preview ? `浏览器预览 - ${preview.accountId}` : '浏览器预览'
  const waitingText = preview ? '正在连接 Bit浏览器画面...' : '等待浏览器启动...'

  return (
    <Modal
      title={title}
      open={open}
      onCancel={onClose}
      footer={null}
      width={980}
      destroyOnClose
      className="browser-preview-modal"
    >
      <div className="browser-preview-shell">
        {frame ? (
          <img className="browser-preview-frame" src={frame} alt="Bit浏览器实时预览" />
        ) : (
          <div className="browser-preview-empty">
            <Space direction="vertical" align="center">
              <Spin />
              <Typography.Text type="secondary">{waitingText}</Typography.Text>
            </Space>
          </div>
        )}
      </div>
      {state === 'error' && error ? (
        <Alert type="warning" showIcon message="浏览器预览连接失败" description={error} style={{ marginTop: 12 }} />
      ) : null}
    </Modal>
  )
}
