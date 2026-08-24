import { Modal } from 'antd'

interface ConfirmDangerOptions {
  title: string
  content: string
  onOk: () => void
}

export function confirmDanger({ title, content, onOk }: ConfirmDangerOptions) {
  Modal.confirm({
    title,
    content,
    okText: '确认',
    cancelText: '取消',
    okButtonProps: { danger: true },
    onOk,
  })
}
