import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Row,
  Space,
  Typography,
  message,
} from "antd";
import { CheckCircle2, DownloadCloud, Info, RefreshCw } from "lucide-react";

import { useDesktopAuth } from "../app/DesktopAuthContext";
import { PageHeader } from "../components/PageHeader";
import desktopIcon from "../../src-tauri/icons/icon.png";

const APP_VERSION = "0.1.0";
const DOWNLOAD_URL = "待配置";

export function AboutPage() {
  const auth = useDesktopAuth();

  const checkUpdate = () => {
    message.info("自动更新服务待接入，当前请使用项目提供的安装包更新。");
  };

  return (
    <div>
      <PageHeader
        title="关于软件"
        description="查看当前版本、下载和更新状态。"
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card>
            <Space size={16} align="start">
              <div className="about-logo">
                <img
                  src={desktopIcon}
                  alt="星域桌面端图标"
                  style={{
                    width: "100%",
                    height: "100%",
                    objectFit: "contain",
                  }}
                />
              </div>
              <div>
                <Typography.Title level={3} className="profile-title">
                  星域
                </Typography.Title>
                <Typography.Text type="secondary">
                  自动化运营工具
                </Typography.Text>
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
              <Descriptions.Item
                label={<InfoLabel icon={<Info size={15} />} text="当前版本" />}
              >
                {APP_VERSION}
              </Descriptions.Item>
              <Descriptions.Item
                label={
                  <InfoLabel
                    icon={<CheckCircle2 size={15} />}
                    text="更新状态"
                  />
                }
              >
                自动更新待接入
              </Descriptions.Item>
              <Descriptions.Item
                label={
                  <InfoLabel
                    icon={<DownloadCloud size={15} />}
                    text="下载地址"
                  />
                }
              >
                {DOWNLOAD_URL}
              </Descriptions.Item>
            </Descriptions>
            <Space className="about-actions" wrap>
              <Button
                type="primary"
                icon={<RefreshCw size={16} />}
                onClick={checkUpdate}
              >
                检查更新
              </Button>
              <Button icon={<DownloadCloud size={16} />} disabled>
                下载安装包（待配置）
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
      </Row>
    </div>
  );
}

function InfoLabel({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <Space size={6}>
      {icon}
      <span>{text}</span>
    </Space>
  );
}
