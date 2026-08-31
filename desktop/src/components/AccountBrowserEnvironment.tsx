import { Space, Tag, Typography } from 'antd'

import type { Account, BrowserProviderId } from '../services/types'

const PROVIDER_LABELS: Record<BrowserProviderId, string> = {
  bitbrowser: 'Bit浏览器',
  builtin_chromium: '内置浏览器',
}

const PROVIDER_COLORS: Record<BrowserProviderId, string> = {
  bitbrowser: 'green',
  builtin_chromium: 'gold',
}

interface AccountBrowserEnvironmentProps {
  accounts: Account[]
  emptyText?: string
}

export function AccountBrowserEnvironment({
  accounts,
  emptyText = '暂无执行账号',
}: AccountBrowserEnvironmentProps) {
  if (accounts.length === 0) {
    return <Typography.Text type="secondary">{emptyText}</Typography.Text>
  }

  return (
    <Space direction="vertical" size={6}>
      {accounts.map((account) => {
        const provider = resolveBrowserProvider(account)
        return (
          <Space key={account.id} wrap size={6}>
            <Typography.Text strong>{account.id}</Typography.Text>
            <Tag color={PROVIDER_COLORS[provider]}>{PROVIDER_LABELS[provider]}</Tag>
            <Typography.Text type="secondary">{browserEnvironmentDetail(account, provider)}</Typography.Text>
          </Space>
        )
      })}
    </Space>
  )
}

function resolveBrowserProvider(account: Account): BrowserProviderId {
  return account.browserProvider ?? account.browser?.provider ?? 'bitbrowser'
}

function browserEnvironmentDetail(account: Account, provider: BrowserProviderId) {
  if (provider === 'bitbrowser') {
    return `profile_id: ${account.bitbrowserProfileId ?? account.browser?.profileId ?? '未绑定'}`
  }
  return `用户数据目录：${account.browser?.userDataDir ?? '账号独立目录'}`
}
