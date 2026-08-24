import { Select, Space, Typography } from 'antd'

import { useOptionalPageScopeContext, type PlatformFilterValue } from '../app/pageScope'
import { PLATFORMS } from '../platforms/registry'

interface PlatformScopeFilterProps {
  value?: PlatformFilterValue
  onChange?: (value: PlatformFilterValue) => void
  includeAll?: boolean
  label?: string
  disabled?: boolean
}

export function PlatformScopeFilter({
  value,
  onChange,
  includeAll = true,
  label = '平台',
  disabled,
}: PlatformScopeFilterProps) {
  const scopeContext = useOptionalPageScopeContext()
  const currentValue = value ?? scopeContext?.platformFilter ?? 'all'
  const handleChange = onChange ?? scopeContext?.setPlatformFilter

  return (
    <Space size={8} className="platform-scope-filter">
      <Typography.Text type="secondary">{label}</Typography.Text>
      <Select<PlatformFilterValue>
        value={currentValue}
        disabled={disabled}
        className="platform-scope-filter-select"
        onChange={(nextValue) => handleChange?.(nextValue)}
        options={[
          ...(includeAll ? [{ value: 'all' as const, label: '全部平台' }] : []),
          ...PLATFORMS.map((platform) => ({
            value: platform.id,
            label: platform.localeName,
          })),
        ]}
      />
    </Space>
  )
}
