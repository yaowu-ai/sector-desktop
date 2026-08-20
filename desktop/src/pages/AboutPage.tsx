import { Alert, Button, Card, Col, Descriptions, Row, Space, Typography, message } from 'antd'
import { CheckCircle2, Copy, DownloadCloud, Info, RefreshCw, ShieldCheck, Sparkles } from 'lucide-react'

import { useDesktopAuth } from '../app/DesktopAuthContext'
import { PageHeader } from '../components/PageHeader'

const APP_VERSION = '0.1.0'
const DOWNLOAD_URL = '待配置'

export function AboutPage() {
  const auth = useDesktopAuth()

  const checkUpdate = () => {
    message.info('自动更新服务待接入，当前请使用项目提供的安装包更新。')
  }

  const copyRuntimeInfo = async () => {
    const text = [
      '星域桌面端',
      `版本：${APP_VERSION}`,
      `账号：${auth.session?.phone || auth.session?.username || '-'}`,
      `用户ID：${auth.session?.userId || '-'}`,
      `订阅：${auth.subscription?.status || '-'}`,
      `License：${auth.license?.status || '-'}`,
      `设备：${auth.device?.deviceFingerprint || '-'}`,
    ].join('\n')

    try {
      await navigator.clipboard.writeText(text)
      message.success('软件信息已复制')
    } catch {
      message.warning('当前环境不支持自动复制')
    }
  }

  return (
    <div>
      <PageHeader title="关于软件" description="查看当前版本、运行信息、下载和更新状态。" />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card>
            <Space size={16} align="start">
              <div className="about-logo">
                <Sparkles size={34} />
              </div>
              <div>
                <Typography.Title level={3} className="profile-title">
                  星域桌面端
                </Typography.Title>
                <Typography.Text type="secondary">自动化运营工具</Typography.Text>
                <div className="profile-role-row">
                  <Typography.Text strong>版本 {APP_VERSION}</Typography.Text>
                </div>
              </div>
            </Space>
          </Card>
        </Col>

        <Col xs={24} lg={16}>
          <Card title="版本与更新">
            <Descriptions column={{ xs: 1, md: 2 }} bordered size="small">
              <Descriptions.Item label={<InfoLabel icon={<Info size={15} />} text="当前版本" />}>{APP_VERSION}</Descriptions.Item>
              <Descriptions.Item label={<InfoLabel icon={<CheckCircle2 size={15} />} text="更新状态" />}>
                自动更新待接入
              </Descriptions.Item>
              <Descriptions.Item label={<InfoLabel icon={<DownloadCloud size={15} />} text="下载地址" />}>
                {DOWNLOAD_URL}
              </Descriptions.Item>
              <Descriptions.Item label={<InfoLabel icon={<ShieldCheck size={15} />} text="授权状态" />}>
                {auth.license?.status || '-'}
              </Descriptions.Item>
            </Descriptions>
            <Space className="about-actions" wrap>
              <Button type="primary" icon={<RefreshCw size={16} />} onClick={checkUpdate}>
                检查更新
              </Button>
              <Button icon={<DownloadCloud size={16} />} disabled>
                下载安装包（待配置）
              </Button>
              <Button icon={<Copy size={16} />} onClick={copyRuntimeInfo}>
                复制软件信息
              </Button>
            </Space>
            <Alert
              className="contact-hint"
              type="info"
              showIcon
              message="下载与自动更新配置待接入"
              description="后续可以由服务端下发最新版本号、安装包地址、更新说明和强制更新策略。"
            />
          </Card>
        </Col>

        <Col xs={24}>
          <Card title="本机运行信息">
            <Descriptions column={{ xs: 1, md: 3 }} bordered size="small">
              <Descriptions.Item label="产品账号">{auth.session?.phone || auth.session?.username || '-'}</Descriptions.Item>
              <Descriptions.Item label="用户角色">{auth.session?.userRole === 1 ? '技术人员' : '普通用户'}</Descriptions.Item>
              <Descriptions.Item label="订阅状态">{auth.subscription?.status || '-'}</Descriptions.Item>
              <Descriptions.Item label="License 状态">{auth.license?.status || '-'}</Descriptions.Item>
              <Descriptions.Item label="设备状态">{auth.device?.status || '-'}</Descriptions.Item>
              <Descriptions.Item label="设备名称">{auth.device?.deviceName || '-'}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

function InfoLabel({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <Space size={6}>
      {icon}
      <span>{text}</span>
    </Space>
  )
}
