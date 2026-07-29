import { Space, Typography } from 'antd'
import type { ReactNode } from 'react'

import { usePlatformContext } from '../app/PlatformContext'
import { useOptionalPageScopeContext } from '../app/pageScope'

interface PageHeaderProps {
  title: string
  description?: string
  extra?: ReactNode
}

export function PageHeader({ title, description, extra }: PageHeaderProps) {
  const scopeContext = useOptionalPageScopeContext()
  const { currentPlatformDefinition } = usePlatformContext()
  const displayTitle = formatScopedTitle(title, scopeContext?.scope, currentPlatformDefinition.localeName)

  return (
    <div className="page-header">
      <div>
        <Typography.Title level={2}>{displayTitle}</Typography.Title>
        {description ? <Typography.Text type="secondary">{description}</Typography.Text> : null}
      </div>
      {extra ? <Space>{extra}</Space> : null}
    </div>
  )
}

function formatScopedTitle(title: string, scope: string | undefined, platformLabel: string) {
  if (scope === 'current_platform') {
    return `${platformLabel} / ${title}`
  }
  if (scope === 'all_platforms') {
    return `全部平台 / ${title}`
  }
  return title
}
