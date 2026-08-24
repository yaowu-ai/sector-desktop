import { Button, Select, Space, Typography } from 'antd'
import { Settings2 } from 'lucide-react'

import { usePlatformContext } from '../app/PlatformContext'
import { PLATFORMS } from '../platforms/registry'
import type { Platform } from '../platforms/types'

interface PlatformSelectorProps {
  onOpenSettings: () => void
  canOpenSettings?: boolean
}

export function PlatformSelector({ onOpenSettings, canOpenSettings = true }: PlatformSelectorProps) {
  const { currentPlatform, setCurrentPlatform } = usePlatformContext()

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
        }))}
      />
      {canOpenSettings ? (
        <Button icon={<Settings2 size={16} />} onClick={onOpenSettings}>
          更多平台
        </Button>
      ) : null}
    </Space>
  )
}
