import { Button, Select, Space, Tag, Tooltip, Typography } from 'antd'
import { Settings2 } from 'lucide-react'

import { usePlatformContext } from '../app/PlatformContext'
import { PLATFORMS } from '../platforms/registry'
import type { Platform, PlatformStatus } from '../platforms/types'
import { StatusTag, type StatusTone } from './StatusTag'

interface PlatformSelectorProps {
  onOpenSettings: () => void
  canOpenSettings?: boolean
}

export function PlatformSelector({ onOpenSettings, canOpenSettings = true }: PlatformSelectorProps) {
  const { currentPlatform, currentPlatformDefinition, setCurrentPlatform } = usePlatformContext()

  return (
    <Space size={8} wrap={false} className="platform-selector">
      <Typography.Text type="secondary" className="platform-selector-label">
        平台
      </Typography.Text>
      <Select<Platform>
        className="platform-selector-select"
        value={currentPlatform}
        onChange={setCurrentPlatform}
        optionLabelProp="label"
        options={PLATFORMS.map((platform) => ({
          value: platform.id,
          label: platform.localeName,
          option: platform,
        }))}
        optionRender={(option) => {
          const platform = option.data.option
          return (
            <Space className="platform-selector-option">
              <Typography.Text>{platform.localeName}</Typography.Text>
              <PlatformStatusTag status={platform.status} enabled={platform.enabled} />
            </Space>
          )
        }}
      />
      <Tooltip title={currentPlatformDefinition.summary}>
        <span>
          <StatusTag
            status={platformTone(currentPlatformDefinition.status, currentPlatformDefinition.enabled)}
            label={platformStatusLabel(currentPlatformDefinition.status, currentPlatformDefinition.enabled)}
          />
        </span>
      </Tooltip>
      {canOpenSettings ? (
        <Button icon={<Settings2 size={16} />} onClick={onOpenSettings}>
          更多平台
        </Button>
      ) : null}
    </Space>
  )
}

function PlatformStatusTag({ status, enabled }: { status: PlatformStatus; enabled: boolean }) {
  return (
    <Tag color={statusColor(status, enabled)} className="platform-selector-status-tag">
      {platformStatusLabel(status, enabled)}
    </Tag>
  )
}

function platformTone(status: PlatformStatus, enabled: boolean): StatusTone {
  if (!enabled) {
    return 'warning'
  }
  if (status === 'supported') {
    return 'ok'
  }
  if (status === 'in_development') {
    return 'running'
  }
  if (status === 'reserved') {
    return 'warning'
  }
  return 'idle'
}

function statusColor(status: PlatformStatus, enabled: boolean) {
  if (!enabled) {
    return 'gold'
  }
  if (status === 'supported') {
    return 'green'
  }
  if (status === 'in_development') {
    return 'blue'
  }
  if (status === 'reserved') {
    return 'gold'
  }
  return 'default'
}

function platformStatusLabel(status: PlatformStatus, enabled: boolean) {
  if (!enabled) {
    return '未启用'
  }
  if (status === 'supported') {
    return '已支持'
  }
  if (status === 'reserved') {
    return '预留'
  }
  if (status === 'in_development') {
    return '开发中'
  }
  return '未支持'
}
