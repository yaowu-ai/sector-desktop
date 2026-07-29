import { Button, Card, Descriptions, Space, Typography } from 'antd'
import { Settings2, ShieldAlert } from 'lucide-react'

import {
  PLATFORM_CAPABILITIES,
  getCapabilityStatusLabel,
  getPlatformDefinition,
} from '../platforms/registry'
import type { CapabilityStatus, Platform, PlatformCapability } from '../platforms/types'
import { StatusTag, type StatusTone } from './StatusTag'

interface UnsupportedCapabilityStateProps {
  platform: Platform
  capability: PlatformCapability
  status: CapabilityStatus
  reason: string
  nextAction?: string
}

export function UnsupportedCapabilityState({
  platform,
  capability,
  status,
  reason,
  nextAction = '进入平台设置查看接入状态和能力矩阵。',
}: UnsupportedCapabilityStateProps) {
  const platformDefinition = getPlatformDefinition(platform)
  const capabilityDefinition = PLATFORM_CAPABILITIES.find((item) => item.key === capability)

  return (
    <Card className="unsupported-capability-state">
      <Space direction="vertical" size={18} className="full-width">
        <Space align="start" size={12}>
          <ShieldAlert size={26} color="#ca8a04" />
          <Space direction="vertical" size={4}>
            <Typography.Title level={3}>
              {platformDefinition.localeName} / {capabilityDefinition?.label ?? capability}
            </Typography.Title>
            <Typography.Text type="secondary">当前平台暂不支持此功能。</Typography.Text>
          </Space>
        </Space>

        <Descriptions size="small" column={1} bordered>
          <Descriptions.Item label="平台">{platformDefinition.localeName}</Descriptions.Item>
          <Descriptions.Item label="功能">{capabilityDefinition?.label ?? capability}</Descriptions.Item>
          <Descriptions.Item label="接入状态">
            <StatusTag status={capabilityTone(status)} label={getCapabilityStatusLabel(status)} />
          </Descriptions.Item>
          <Descriptions.Item label="不支持原因">{reason}</Descriptions.Item>
          <Descriptions.Item label="下一步">{nextAction}</Descriptions.Item>
        </Descriptions>

        <div>
          <Button icon={<Settings2 size={16} />} onClick={() => goRoute('platforms')}>
            平台设置
          </Button>
        </div>
      </Space>
    </Card>
  )
}

function capabilityTone(status: CapabilityStatus): StatusTone {
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

function goRoute(routeKey: string) {
  window.location.hash = routeKey
}
