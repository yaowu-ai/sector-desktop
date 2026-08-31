import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from "antd";
import { DatabaseBackup, RefreshCw, Save, Send, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "../components/PageHeader";
import { confirmDanger } from "../components/ConfirmDanger";
import {
  applyConfigMigration,
  clearSessionLog,
  getBuiltinChromiumStatus,
  getBrowserProviderMatrix,
  getInitializationStatus,
  getSqliteStatus,
  loadConfig,
  loadSystemSettings,
  previewConfigMigration,
  saveNotifySettings,
  saveSystemSettings,
  testNotification,
} from "../services/api";
import type {
  AppInitializationStatus,
  BuiltinChromiumStatus,
  BrowserProviderCapability,
  MigrationPreview,
  NotifySettings,
  SqliteStatus,
  SystemSettingsPayload,
  SystemSettingsSnapshot,
} from "../services/types";

const DEFAULT_NOTIFY: NotifySettings = {
  enabled: false,
  type: "serverchan",
  serverchan: { sendkey: "" },
  bark: { url: "" },
  webhook: { url: "" },
};

export function SettingsPage() {
  const [systemForm] = Form.useForm<SystemSettingsPayload>();
  const [notifyForm] = Form.useForm<NotifySettings>();
  const notifyType = Form.useWatch("type", notifyForm) ?? "serverchan";
  const [settings, setSettings] = useState<SystemSettingsSnapshot | null>(null);
  const runtimeMode =
    Form.useWatch("runtimeMode", systemForm) ??
    settings?.runtimeMode ??
    "source";
  const defaultBrowserProvider =
    Form.useWatch("defaultBrowserProvider", systemForm) ??
    settings?.defaultBrowserProvider ??
    "bitbrowser";
  const dataDir = Form.useWatch("dataDir", systemForm) ?? settings?.dataDir;
  const configPath =
    Form.useWatch("configPath", systemForm) ?? settings?.configPath;
  const commentsPath =
    Form.useWatch("commentsPath", systemForm) ?? settings?.commentsPath;
  const brandCommentsPath =
    Form.useWatch("brandCommentsPath", systemForm) ??
    settings?.brandCommentsPath;
  const [initializationStatus, setInitializationStatus] =
    useState<AppInitializationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [migrationPreview, setMigrationPreview] =
    useState<MigrationPreview | null>(null);
  const [providerMatrix, setProviderMatrix] = useState<
    BrowserProviderCapability[]
  >([]);
  const [builtinChromiumStatus, setBuiltinChromiumStatus] =
    useState<BuiltinChromiumStatus | null>(null);
  const [sqliteStatus, setSqliteStatus] = useState<SqliteStatus | null>(null);
  const [previewingMigration, setPreviewingMigration] = useState(false);
  const [applyingMigration, setApplyingMigration] = useState(false);
  const [detectingChromium, setDetectingChromium] = useState(false);
  const [advancedPathKeys, setAdvancedPathKeys] = useState<string[]>([]);
  const [diagnosticPathKeys, setDiagnosticPathKeys] = useState<string[]>([]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const systemSettings = await loadSystemSettings();
      setSettings(systemSettings);
      systemForm.setFieldsValue(systemSettings);
      setInitializationStatus(await getInitializationStatus());
      setProviderMatrix(await getBrowserProviderMatrix());
      setBuiltinChromiumStatus(await getBuiltinChromiumStatus());
      setSqliteStatus(await getSqliteStatus());

      try {
        const config = await loadConfig();
        notifyForm.setFieldsValue(normalizeNotify(config.notify));
      } catch (error) {
        notifyForm.setFieldsValue(DEFAULT_NOTIFY);
        message.warning(`未能读取账号配置：${formatError(error)}`);
      }

      try {
        setMigrationPreview(await previewConfigMigration());
      } catch {
        setMigrationPreview(null);
      }
    } catch (error) {
      message.error(formatError(error));
    } finally {
      setLoading(false);
    }
  }, [notifyForm, systemForm]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const save = async () => {
    setSaving(true);
    try {
      const systemValues = await systemForm.validateFields();
      const allSystemValues = systemForm.getFieldsValue(
        true,
      ) as SystemSettingsPayload;
      const notifyEnabled = Boolean(notifyForm.getFieldValue("enabled"));
      const notifyValues = normalizeNotify(
        notifyEnabled
          ? await notifyForm.validateFields()
          : notifyForm.getFieldsValue(true),
      );
      const nextSettings = await saveSystemSettings({
        ...systemValues,
        ...allSystemValues,
        logPollIntervalSeconds: Number(systemValues.logPollIntervalSeconds),
      });
      setSettings(nextSettings);
      try {
        await saveNotifySettings(notifyValues);
        message.success("系统设置已保存");
      } catch (error) {
        message.warning(
          `系统设置已保存，但通知配置未保存：${formatError(error)}`,
        );
      }
    } catch (error) {
      message.error(formatError(error));
    } finally {
      setSaving(false);
    }
  };

  const sendTest = async () => {
    setTesting(true);
    try {
      const notifyValues = normalizeNotify(await notifyForm.validateFields());
      await testNotification(notifyValues);
      message.success("测试通知已发送");
    } catch (error) {
      message.error(formatError(error));
    } finally {
      setTesting(false);
    }
  };

  const confirmClearLogs = () => {
    confirmDanger({
      title: "清理 Session 日志",
      content: "将清空本机 Session 日志，执行记录不会被删除。",
      onOk: () => {
        void clearLogs();
      },
    });
  };

  const refreshMigrationPreview = async () => {
    setPreviewingMigration(true);
    try {
      setMigrationPreview(await previewConfigMigration());
      message.success("迁移预览已刷新");
    } catch (error) {
      message.error(formatError(error));
    } finally {
      setPreviewingMigration(false);
    }
  };

  const confirmApplyMigration = () => {
    confirmDanger({
      title: "应用多平台配置迁移",
      content:
        "执行前会自动备份 accounts.yaml 和 actions.db。迁移会补齐 platform 字段，并把旧 TikTok 配置写入 platforms.tiktok。",
      onOk: () => {
        void applyMigration();
      },
    });
  };

  const applyMigration = async () => {
    setApplyingMigration(true);
    try {
      const result = await applyConfigMigration();
      setMigrationPreview(result.preview);
      message.success(`迁移完成，已创建 ${result.backupPaths.length} 个备份`);
      await refresh();
    } catch (error) {
      message.error(formatError(error));
    } finally {
      setApplyingMigration(false);
    }
  };

  const clearLogs = async () => {
    try {
      const result = await clearSessionLog();
      message.success(
        result.cleared ? "已清理 Session 日志" : "Session 日志尚未生成",
      );
    } catch (error) {
      message.error(formatError(error));
    }
  };

  const autoFillChromiumExecutable = async () => {
    const current = String(systemForm.getFieldValue("chromiumExecutable") ?? "").trim();
    if (current) {
      return;
    }
    setDetectingChromium(true);
    try {
      const status = await getBuiltinChromiumStatus();
      setBuiltinChromiumStatus(status);
      if (status.available && status.executablePath) {
        systemForm.setFieldValue("chromiumExecutable", status.executablePath);
        message.success("已自动检测并填入内置浏览器可执行文件");
      } else {
        message.warning("未检测到可用内置浏览器，请安装 Chrome/Edge 或手动指定可执行文件。");
      }
    } catch (error) {
      message.error(formatError(error));
    } finally {
      setDetectingChromium(false);
    }
  };

  const handleAdvancedPathChange = (keys: string | string[]) => {
    setAdvancedPathKeys(normalizeCollapseKeys(keys));
  };

  const handleDiagnosticPathChange = (keys: string | string[]) => {
    setDiagnosticPathKeys(normalizeCollapseKeys(keys));
  };

  return (
    <>
      <PageHeader
        title="系统设置"
        description="维护运行环境、浏览器连接、日志轮询和通知配置。"
        extra={
          <Space>
            <Button
              icon={<RefreshCw size={16} />}
              loading={loading}
              onClick={() => void refresh()}
            >
              刷新
            </Button>
            <Button
              type="primary"
              icon={<Save size={16} />}
              loading={saving}
              onClick={() => void save()}
            >
              保存设置
            </Button>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Alert
            showIcon
            type="info"
            message="系统设置仅影响本机应用"
            description="常用配置会直接展示；完整路径已收起到高级配置和高级诊断信息中，仅用于部署或技术支持排查。"
          />
        </Col>

        <Col span={24}>
          <Card title="浏览器提供方能力矩阵">
            <Row gutter={[12, 12]}>
              {providerMatrix.map((provider) => (
                <Col xs={24} md={12} key={provider.provider}>
                  <Descriptions
                    size="small"
                    column={1}
                    bordered
                    style={{ width: "100%" }}
                  >
                    <Descriptions.Item
                      label={formatProviderLabel(
                        provider.provider,
                        provider.label,
                      )}
                    >
                      <Space direction="vertical" size={4}>
                        <Space wrap>
                          <Tag
                            color={provider.implemented ? "green" : "orange"}
                          >
                            {provider.implemented ? "已实现" : "预留"}
                          </Tag>
                          <Tag
                            color={provider.productionReady ? "green" : "gold"}
                          >
                            {formatProviderRisk(provider.riskLevel)}
                          </Tag>
                        </Space>
                        <Typography.Text type="secondary">
                          {formatProviderNotes(provider)}
                        </Typography.Text>
                      </Space>
                    </Descriptions.Item>
                    <Descriptions.Item label="CDP 端点">
                      {formatYesNo(provider.providesCdpEndpoint)}
                    </Descriptions.Item>
                    <Descriptions.Item label="TikTok">
                      {formatSupport(provider.supportsTiktok)}
                    </Descriptions.Item>
                  </Descriptions>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>

        <Col xs={24} xl={14}>
          <Card title="运行环境">
            <Form
              form={systemForm}
              layout="vertical"
              requiredMark={false}
              disabled={loading}
            >
              <Form.Item
                name="runtimeMode"
                label="运行模式"
                rules={[{ required: true }]}
              >
                <Select
                  options={[
                    { value: "bundled", label: "内置运行时" },
                    { value: "source", label: "源码开发模式" },
                  ]}
                />
              </Form.Item>
              <Form.Item
                name="defaultBrowserProvider"
                label="默认浏览器提供方"
                rules={[{ required: true }]}
              >
                <Select
                  onChange={(value) => {
                    if (value === "builtin_chromium") {
                      void autoFillChromiumExecutable();
                    }
                  }}
                  options={[
                    { value: "bitbrowser", label: "Bit浏览器" },
                    { value: "builtin_chromium", label: "内置浏览器" },
                  ]}
                />
              </Form.Item>
              {defaultBrowserProvider === "builtin_chromium" ? (
                <Form.Item
                  name="chromiumExecutable"
                  label="内置浏览器可执行文件"
                  extra="系统会自动检测 Chrome/Edge 等浏览器；检测不到时再手动指定。Bit浏览器仍是 TikTok 默认推荐方案。"
                >
                  <Input
                    placeholder="C:/Program Files/Google/Chrome/Application/chrome.exe"
                    suffix={
                      <Button
                        type="link"
                        size="small"
                        loading={detectingChromium}
                        onClick={() => void autoFillChromiumExecutable()}
                      >
                        自动检测
                      </Button>
                    }
                  />
                </Form.Item>
              ) : null}
              {builtinChromiumStatus ? (
                <Alert
                  type={builtinChromiumStatus.available ? "info" : "warning"}
                  showIcon
                  message="内置浏览器是生产可选方案"
                  description={
                    builtinChromiumStatus.available
                      ? "已检测到可用的内置浏览器。账号浏览器数据将保存在本机应用数据中；不等价替代 Bit浏览器的指纹环境能力。"
                      : "未检测到可用的内置浏览器。使用内置浏览器时，请确认本机已安装，或指定可执行文件。"
                  }
                />
              ) : null}
              <Row gutter={12}>
                <Col xs={24} md={12}>
                  <Form.Item
                    name="pythonExecutable"
                    label="Python 可执行文件"
                    rules={[
                      { required: true, message: "请配置 Python 可执行文件" },
                    ]}
                  >
                    <Input placeholder="py 或 C:/Python313/python.exe" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item
                    name="bitbrowserApiUrl"
                    label="Bit浏览器 API 地址"
                    rules={[
                      { required: true, message: "请配置 Bit浏览器 API 地址" },
                      {
                        type: "url",
                        message: "请输入 http:// 或 https:// URL",
                      },
                    ]}
                  >
                    <Input placeholder="http://127.0.0.1:54345" />
                  </Form.Item>
                </Col>
              </Row>
              <Descriptions
                size="small"
                column={2}
                bordered
                style={{ marginBottom: 16 }}
              >
                <Descriptions.Item label="数据存储">
                  <Space>
                    <Typography.Text>本机应用数据</Typography.Text>
                    {renderReadyTag(dataDir)}
                  </Space>
                </Descriptions.Item>
                <Descriptions.Item label="账号配置">
                  <Space>
                    <Typography.Text>本机配置文件</Typography.Text>
                    {renderReadyTag(configPath)}
                  </Space>
                </Descriptions.Item>
                <Descriptions.Item label="通用评论素材">
                  <Space>
                    <Typography.Text>本机素材库</Typography.Text>
                    {renderReadyTag(commentsPath)}
                  </Space>
                </Descriptions.Item>
                <Descriptions.Item label="品牌评论素材">
                  <Space>
                    <Typography.Text>本机素材库</Typography.Text>
                    {renderReadyTag(brandCommentsPath)}
                  </Space>
                </Descriptions.Item>
              </Descriptions>
              <Collapse
                size="small"
                style={{ marginBottom: 16 }}
                activeKey={advancedPathKeys}
                onChange={handleAdvancedPathChange}
                items={[
                  {
                    key: "advanced-paths",
                    label: (
                      <Space>
                        <Typography.Text>高级路径配置</Typography.Text>
                      </Space>
                    ),
                    forceRender: true,
                    children: (
                      <>
                        <Alert
                          type="warning"
                          showIcon
                          message="高级路径配置仅用于部署和技术支持"
                          description="修改这些配置可能导致应用无法正常运行。请在技术支持指导下调整。"
                          style={{ marginBottom: 16 }}
                        />
                        <Form.Item
                          name="projectRoot"
                          label={
                            runtimeMode === "source"
                              ? "项目根目录（源码模式）"
                              : "项目根目录（仅源码模式使用）"
                          }
                        >
                          <Input placeholder="D:/apps/account-matrix" />
                        </Form.Item>
                        <Form.Item
                          name="dataDir"
                          label="数据存储目录"
                          rules={[{ required: true }]}
                        >
                          <Input placeholder="data" />
                        </Form.Item>
                        <Form.Item
                          name="configPath"
                          label="账号配置文件"
                          rules={[{ required: true }]}
                        >
                          <Input placeholder="config/accounts.yaml" />
                        </Form.Item>
                        <Row gutter={12}>
                          <Col xs={24} md={12}>
                            <Form.Item
                              name="commentsPath"
                              label="通用评论素材文件"
                              rules={[{ required: true }]}
                            >
                              <Input placeholder="config/comments.txt" />
                            </Form.Item>
                          </Col>
                          <Col xs={24} md={12}>
                            <Form.Item
                              name="brandCommentsPath"
                              label="品牌评论素材文件"
                              rules={[{ required: true }]}
                            >
                              <Input placeholder="config/comments_brand.txt" />
                            </Form.Item>
                          </Col>
                        </Row>
                      </>
                    ),
                  },
                ]}
              />
              <Row gutter={12}>
                <Col xs={24} md={12}>
                  <Form.Item
                    name="autoCloseProfile"
                    label="任务结束自动关闭 profile"
                    valuePropName="checked"
                  >
                    <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item
                    name="logPollIntervalSeconds"
                    label="日志轮询间隔"
                    rules={[{ required: true, message: "请配置日志轮询间隔" }]}
                  >
                    <InputNumber
                      min={1}
                      max={60}
                      precision={0}
                      addonAfter="秒"
                      style={{ width: "100%" }}
                    />
                  </Form.Item>
                </Col>
              </Row>
            </Form>
          </Card>
        </Col>

        <Col xs={24} xl={10}>
          <Card
            title="通知"
            extra={
              <Button
                icon={<Send size={16} />}
                loading={testing}
                onClick={() => void sendTest()}
              >
                测试发送
              </Button>
            }
          >
            <Form
              form={notifyForm}
              layout="vertical"
              requiredMark={false}
              disabled={loading}
            >
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item
                    name="enabled"
                    label="启用通知"
                    valuePropName="checked"
                  >
                    <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="type"
                    label="通知类型"
                    rules={[{ required: true }]}
                  >
                    <Select
                      options={[
                        { value: "serverchan", label: "ServerChan" },
                        { value: "bark", label: "Bark" },
                        { value: "webhook", label: "Webhook" },
                      ]}
                    />
                  </Form.Item>
                </Col>
              </Row>

              {notifyType === "serverchan" ? (
                <Form.Item
                  name={["serverchan", "sendkey"]}
                  label="Server 酱 SendKey"
                  rules={[
                    { required: true, message: "请输入 Server 酱 SendKey" },
                  ]}
                >
                  <Input.Password
                    autoComplete="off"
                    placeholder="默认隐藏，日志中不输出"
                  />
                </Form.Item>
              ) : null}

              {notifyType === "bark" ? (
                <Form.Item
                  name={["bark", "url"]}
                  label="Bark 地址"
                  rules={[
                    { required: true, message: "请输入 Bark URL" },
                    { type: "url", message: "请输入有效 URL" },
                  ]}
                >
                  <Input.Password
                    autoComplete="off"
                    placeholder="https://api.day.app/your-key"
                  />
                </Form.Item>
              ) : null}

              {notifyType === "webhook" ? (
                <Form.Item
                  name={["webhook", "url"]}
                  label="Webhook 地址"
                  rules={[
                    { required: true, message: "请输入 Webhook 地址" },
                    { type: "url", message: "请输入有效 URL" },
                  ]}
                >
                  <Input.Password
                    autoComplete="off"
                    placeholder="https://example.com/webhook"
                  />
                </Form.Item>
              ) : null}
            </Form>
          </Card>

          <Card title="当前生效配置" style={{ marginTop: 16 }}>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="运行模式">
                {formatRuntimeMode(settings?.runtimeMode)}
              </Descriptions.Item>
              <Descriptions.Item label="运行时版本">
                {settings?.runtimeVersion ?? "-"}
              </Descriptions.Item>
              <Descriptions.Item label="初始化应用版本">
                {settings?.initializedAppVersion ??
                  initializationStatus?.initializedAppVersion ??
                  "-"}
              </Descriptions.Item>
              <Descriptions.Item label="账号配置">
                {renderReadyTag(settings?.configPath)}
              </Descriptions.Item>
              <Descriptions.Item label="数据存储">
                <Space>
                  <Typography.Text>本机</Typography.Text>
                  {renderReadyTag(settings?.dataDir)}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="评论素材">
                {renderCommentLibraryStatus(settings)}
              </Descriptions.Item>
              <Descriptions.Item label="执行记录">
                {renderSqliteStatus(sqliteStatus)}
              </Descriptions.Item>
              <Descriptions.Item label="Session 日志">
                {renderReadyTag(settings?.logsDir)}
              </Descriptions.Item>
            </Descriptions>
            <Collapse
              size="small"
              style={{ marginTop: 12 }}
              activeKey={diagnosticPathKeys}
              onChange={handleDiagnosticPathChange}
              items={[
                {
                  key: "diagnostic-paths",
                  label: (
                    <Space>
                      <Typography.Text>高级诊断信息</Typography.Text>
                    </Space>
                  ),
                  children: (
                    <Descriptions size="small" column={1} bordered>
                      <Descriptions.Item label="设置文件">
                        {settings?.settingsPath ?? "-"}
                      </Descriptions.Item>
                      <Descriptions.Item label="项目根目录">
                        {settings?.projectRoot ?? "-"}
                      </Descriptions.Item>
                      <Descriptions.Item label="运行时清单">
                        {settings?.runtimeManifestPath ?? "-"}
                      </Descriptions.Item>
                      <Descriptions.Item label="用户配置目录">
                        {initializationStatus?.configDir ?? "-"}
                      </Descriptions.Item>
                      <Descriptions.Item label="日志目录">
                        {settings?.logsDir ?? "-"}
                      </Descriptions.Item>
                      <Descriptions.Item label="执行记录库">
                        {settings ? `${settings.dataDir}/actions.db` : "-"}
                      </Descriptions.Item>
                      <Descriptions.Item label="Session 日志">
                        {settings ? `${settings.dataDir}/sessions.log` : "-"}
                      </Descriptions.Item>
                      <Descriptions.Item label="任务锁">
                        {settings ? `${settings.dataDir}/run.lock` : "-"}
                      </Descriptions.Item>
                    </Descriptions>
                  ),
                },
              ]}
            />
            <Typography.Paragraph
              type="secondary"
              style={{ marginTop: 12, marginBottom: 0 }}
            >
              高级诊断信息仅用于技术支持排查；通知 secret
              默认以密码框展示，测试发送时不写入命令行。
            </Typography.Paragraph>
          </Card>
        </Col>

        <Col span={24}>
          <Card title="多平台配置迁移">
            <Space direction="vertical" size={12} className="full-width">
              <Typography.Text type="secondary">
                迁移工具会把旧 TikTok 配置复制到
                platforms.tiktok，并补齐旧数据的 platform 维度。
              </Typography.Text>
              <Space wrap>
                <Tag color={migrationPreview?.required ? "gold" : "green"}>
                  {migrationPreview?.required ? "需要迁移" : "无需迁移"}
                </Tag>
                {migrationPreview?.warnings.map((warning) => (
                  <Tag color="orange" key={warning}>
                    {warning}
                  </Tag>
                ))}
              </Space>
              <Row gutter={[12, 12]}>
                {(migrationPreview?.operations ?? []).map((operation) => (
                  <Col xs={24} md={12} xl={8} key={operation.key}>
                    <Descriptions size="small" column={1} bordered>
                      <Descriptions.Item label={operation.label}>
                        <Space direction="vertical" size={2}>
                          <Tag color={operation.pending ? "gold" : "green"}>
                            {operation.pending ? "待执行" : "已兼容"}
                          </Tag>
                          <Typography.Text type="secondary">
                            {operation.detail}
                          </Typography.Text>
                        </Space>
                      </Descriptions.Item>
                    </Descriptions>
                  </Col>
                ))}
              </Row>
              <Space>
                <Button
                  icon={<RefreshCw size={16} />}
                  loading={previewingMigration}
                  onClick={() => void refreshMigrationPreview()}
                >
                  刷新预览
                </Button>
                <Button
                  type="primary"
                  icon={<DatabaseBackup size={16} />}
                  loading={applyingMigration}
                  disabled={!migrationPreview?.required}
                  onClick={confirmApplyMigration}
                >
                  应用迁移
                </Button>
              </Space>
            </Space>
          </Card>
        </Col>

        <Col span={24}>
          <Card title="危险操作">
            <Space direction="vertical" size={12} className="full-width">
              <Typography.Text type="secondary">
                这些操作只影响本地运行环境，不会删除 Bit浏览器 profile。
              </Typography.Text>
              <Button
                danger
                icon={<Trash2 size={16} />}
                onClick={confirmClearLogs}
              >
                清理 Session 日志
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>
    </>
  );
}

function normalizeNotify(value?: NotifySettings | null): NotifySettings {
  return {
    enabled: value?.enabled ?? DEFAULT_NOTIFY.enabled,
    type: value?.type ?? DEFAULT_NOTIFY.type,
    serverchan: {
      sendkey: value?.serverchan?.sendkey ?? "",
    },
    bark: {
      url: value?.bark?.url ?? "",
    },
    webhook: {
      url: value?.webhook?.url ?? "",
    },
  };
}

function formatProviderLabel(
  provider: BrowserProviderCapability["provider"],
  fallback: string,
) {
  const labels: Record<BrowserProviderCapability["provider"], string> = {
    bitbrowser: "Bit浏览器",
    builtin_chromium: "内置浏览器",
  };
  return labels[provider] ?? fallback;
}

function formatProviderRisk(riskLevel: BrowserProviderCapability["riskLevel"]) {
  const labels: Record<BrowserProviderCapability["riskLevel"], string> = {
    stable: "稳定",
    production_optional: "生产可选",
    advanced: "高级",
  };
  return labels[riskLevel] ?? riskLevel;
}

function formatProviderNotes(provider: BrowserProviderCapability) {
  const notes: Record<BrowserProviderCapability["provider"], string> = {
    bitbrowser:
      "生产默认方案。使用 Bit浏览器 Local API 和现有 Bit浏览器 profile_id。",
    builtin_chromium:
      "生产可选方案。使用本机内置浏览器、账号独立数据目录和临时 CDP 端口启动；不等价替代 Bit浏览器的指纹环境能力，Bit浏览器仍是默认推荐。",
  };
  return notes[provider.provider] ?? provider.notes;
}

function formatYesNo(value: boolean) {
  return value ? "是" : "否";
}

function formatSupport(value: boolean) {
  return value ? "支持" : "不支持";
}

function formatRuntimeMode(value?: string) {
  if (value === "bundled") {
    return "内置运行时";
  }
  if (value === "source") {
    return "源码开发模式";
  }
  return value ?? "-";
}

function renderReadyTag(value?: string | null) {
  return (
    <Tag color={value ? "green" : "default"}>{value ? "已配置" : "未配置"}</Tag>
  );
}

function renderCommentLibraryStatus(settings: SystemSettingsSnapshot | null) {
  const loaded = Boolean(settings?.commentsPath && settings?.brandCommentsPath);
  return (
    <Space>
      <Typography.Text>本机素材库</Typography.Text>
      <Tag color={loaded ? "green" : "default"}>
        {loaded ? "已配置" : "未配置"}
      </Tag>
    </Space>
  );
}

function renderSqliteStatus(status: SqliteStatus | null) {
  if (!status) {
    return <Tag>检测中</Tag>;
  }
  if (!status.exists) {
    return <Tag color="gold">未初始化</Tag>;
  }
  if (status.actionLog && status.targetEngagements && status.targetFollows) {
    return <Tag color="green">已就绪</Tag>;
  }
  return <Tag color="red">读取异常</Tag>;
}

function normalizeCollapseKeys(keys: string | string[]) {
  return Array.isArray(keys) ? keys : [keys].filter(Boolean);
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
