import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  Row,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { Loader2, MessageSquareText, Send } from "lucide-react";
import { useState } from "react";

import wecomQr from "../assets/contact/wecom-qr.png";
import { useDesktopAuth } from "../app/DesktopAuthContext";
import { PageHeader } from "../components/PageHeader";
import { submitDesktopFeedback } from "../services/desktopApi";

export function ContactSupportPage() {
  const auth = useDesktopAuth();
  const [form] = Form.useForm<{ category: string; content: string }>();
  const [submitting, setSubmitting] = useState(false);
  const [lastSubmittedAt, setLastSubmittedAt] = useState<string | null>(null);

  const submitFeedback = async (values: {
    category: string;
    content: string;
  }) => {
    if (!auth.session) return;
    const content = [
      `问题类型：${values.category || "未填写"}`,
      `问题描述：${values.content}`,
    ].join("\n");
    setSubmitting(true);
    try {
      await submitDesktopFeedback(
        auth.session,
        { content, imageUrls: [] },
        auth.apiBaseUrl,
      );
      form.resetFields();
      setLastSubmittedAt(new Date().toISOString());
      message.success("反馈已提交");
    } catch (error) {
      message.error(formatSupportError(error));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="联系客服"
        description="提交问题反馈，便于定位授权、登录或运行异常。"
      />

      <Row gutter={[16, 16]} className="contact-support-grid">
        <Col xs={24} lg={9}>
          <Card title="联系信息">
            <Space direction="vertical" size={16} className="full-width">
              <Descriptions column={1} bordered size="small">
                <Descriptions.Item
                  label={
                    <InfoLabel
                      icon={<MessageSquareText size={15} />}
                      text="企业微信"
                    />
                  }
                >
                  扫码添加下方二维码
                </Descriptions.Item>
              </Descriptions>
              <div className="contact-wecom-qr">
                <img
                  className="contact-wecom-qr-image"
                  src={wecomQr}
                  alt="企业微信二维码"
                />
              </div>
            </Space>
          </Card>
        </Col>

        <Col xs={24} lg={15}>
          <Card title="问题反馈">
            <Form form={form} layout="vertical" onFinish={submitFeedback}>
              <Form.Item
                label="问题类型"
                name="category"
                rules={[{ max: 80, message: "问题类型不能超过80个字符" }]}
              >
                <Input placeholder="例如：登录授权、任务运行、浏览器环境、数据统计" />
              </Form.Item>
              <Form.Item
                label="问题描述"
                name="content"
                rules={[
                  { required: true, message: "请填写问题描述" },
                  { max: 4500, message: "问题描述不能超过4500个字符" },
                ]}
              >
                <Input.TextArea
                  rows={6}
                  placeholder="请描述出现问题的页面、操作步骤、错误提示和发生时间。"
                />
              </Form.Item>
              <Space>
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={submitting ? <Loader2 size={16} /> : <Send size={16} />}
                  loading={submitting}
                >
                  提交反馈
                </Button>
                <Typography.Text type="secondary">
                  {lastSubmittedAt
                    ? `上次提交：${formatDateTime(lastSubmittedAt)}`
                    : ""}
                </Typography.Text>
              </Space>
            </Form>
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

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value || "-";
  return date.toLocaleString();
}

function formatSupportError(error: unknown) {
  const messageText = error instanceof Error ? error.message : String(error);
  const normalized = messageText.trim();
  const translations: Record<string, string> = {
    "Failed to fetch": "暂时无法提交反馈，请稍后重试",
    "Invalid desktop session": "登录状态已失效，请重新登录后再提交反馈",
    Unauthorized: "登录状态已失效，请重新登录后再提交反馈",
  };
  if (translations[normalized]) return translations[normalized];
  if (/failed to fetch/i.test(normalized))
    return translations["Failed to fetch"];
  if (/unauthorized/i.test(normalized)) return translations.Unauthorized;
  return normalized || "反馈提交失败，请稍后重试";
}
