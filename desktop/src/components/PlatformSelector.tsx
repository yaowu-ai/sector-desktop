import { Button, Select, Space, Typography } from 'antd'
import { Settings2 } from 'lucide-react'
import { useEffect, useMemo } from 'react'

import { usePlatformContext } from '../app/PlatformContext'
import { filterPlatformsByRole, type DesktopUserRole } from '../app/routePermissions'
import { PLATFORMS } from '../platforms/registry'
import type { Platform } from '../platforms/types'

interface PlatformSelectorProps {
  onOpenSettings: () => void
  userRole: DesktopUserRole
  canOpenSettings?: boolean
}

export function PlatformSelector({ onOpenSettings, userRole, canOpenSettings = true }: PlatformSelectorProps) {
  const { currentPlatform, setCurrentPlatform } = usePlatformContext()
  const visiblePlatforms = useMemo(() => filterPlatformsByRole(PLATFORMS, userRole), [userRole])
  const selectedPlatform = visiblePlatforms.some((platform) => platform.id === currentPlatform)
    ? currentPlatform
    : visiblePlatforms[0]?.id ?? currentPlatform

  useEffect(() => {
    if (selectedPlatform !== currentPlatform) {
      setCurrentPlatform(selectedPlatform)
    }
  }, [currentPlatform, selectedPlatform, setCurrentPlatform])

  return (
    <Space size={8} wrap={false} className="platform-selector">
      <Typography.Text type="secondary" className="platform-selector-label">
        平台
      </Typography.Text>
      <Select<Platform>
        className="platform-selector-select"
        value={selectedPlatform}
        onChange={setCurrentPlatform}
        optionLabelProp="label"
        options={visiblePlatforms.map((platform) => ({
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
