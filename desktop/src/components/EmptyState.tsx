import { Empty, Typography } from 'antd'

interface EmptyStateProps {
  title: string
  description?: string
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <div>
            <Typography.Text strong>{title}</Typography.Text>
            {description ? (
              <Typography.Paragraph type="secondary">{description}</Typography.Paragraph>
            ) : null}
          </div>
        }
      />
    </div>
  )
}
