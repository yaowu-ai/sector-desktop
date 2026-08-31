import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Segmented,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from "antd";
import { FolderOpen, KeyRound, Mail, Play, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PageHeader } from "../components/PageHeader";
import { ProcessOutputPanel } from "../components/ProcessOutputPanel";
import { StatusTag } from "../components/StatusTag";
import { usePlatformContext } from "../app/PlatformContext";
import {
  getCurrentRunStatus,
  getStderrChunk,
  getStdoutChunk,
  runGmailSetup,
} from "../services/api";
import type { GmailSetupRequest, ProcessStatus } from "../services/types";

type Mode = "single" | "batch";

interface SingleFormValues {
  browserName: string;
  email?: string;
  password?: string;
  newPassword?: string;
  query: string;
  timeoutSeconds: number;
  termsTimeoutSeconds: number;
}

interface BatchFormValues {
  browserName: string;
  emailFile: string;
  query: string;
  timeoutSeconds: number;
  termsTimeoutSeconds: number;
  keepOpenOnError: boolean;
}

const DEFAULT_SINGLE: SingleFormValues = {
  browserName: "",
  email: "",
  password: "",
  newPassword: "",
  query: "gmail",
  timeoutSeconds: 60,
  termsTimeoutSeconds: 60,
};

const DEFAULT_BATCH: BatchFormValues = {
  browserName: "",
  emailFile: "",
  query: "gmail",
  timeoutSeconds: 60,
  termsTimeoutSeconds: 60,
  keepOpenOnError: false,
};

export function GmailSetupPage() {
  const { currentPlatform, currentPlatformDefinition } = usePlatformContext();
  const [singleForm] = Form.useForm<SingleFormValues>();
  const [batchForm] = Form.useForm<BatchFormValues>();
  const [mode, setMode] = useState<Mode>("single");
  const [starting, setStarting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const runSingle = async () => {
    const values = await singleForm.validateFields();
    const request: GmailSetupRequest = {
      browserName: values.browserName.trim(),
      email: values.email?.trim() || undefined,
      password: values.password || undefined,
      newPassword: values.newPassword || undefined,
      query: values.query.trim() || "gmail",
      timeoutSeconds: values.timeoutSeconds,
      termsTimeoutSeconds: values.termsTimeoutSeconds,
      keepOpenOnError: false,
    };
    confirmRun("单账号 Gmail 初始化", request, [
      ["窗口名称", request.browserName ?? "-"],
      ["Google 邮箱", request.email ?? "仅打开登录页"],
      ["当前密码", request.password ? "通过环境变量传递" : "未提供"],
      [
        "新密码",
        request.newPassword
          ? "通过环境变量传递"
          : request.password
            ? "使用脚本默认新密码"
            : "未提供",
      ],
    ]);
  };

  const runBatch = async () => {
    const values = await batchForm.validateFields();
    const request: GmailSetupRequest = {
      browserName: values.browserName.trim(),
      emailFile: values.emailFile.trim(),
      query: values.query.trim() || "gmail",
      timeoutSeconds: values.timeoutSeconds,
      termsTimeoutSeconds: values.termsTimeoutSeconds,
      keepOpenOnError: values.keepOpenOnError,
    };
    confirmRun("批量 Gmail 初始化", request, [
      ["起始窗口", request.browserName ?? "-"],
      ["邮箱文件", maskPath(request.emailFile ?? "-")],
      ["失败保留窗口", request.keepOpenOnError ? "是" : "否"],
      ["密码来源", "从邮箱文件读取，日志不展示密码"],
    ]);
  };

  const confirmRun = (
    title: string,
    request: GmailSetupRequest,
    rows: Array<[string, string]>,
  ) => {
    Modal.confirm({
      title,
      okText: "确认启动",
      cancelText: "取消",
      width: 620,
      content: (
        <Descriptions
          size="small"
          column={1}
          bordered
          style={{ marginTop: 12 }}
        >
          {rows.map(([label, value]) => (
            <Descriptions.Item key={label} label={label}>
              {value}
            </Descriptions.Item>
          ))}
          <Descriptions.Item label="页面超时">
            {request.timeoutSeconds} 秒
          </Descriptions.Item>
          <Descriptions.Item label="条款页超时">
            {request.termsTimeoutSeconds} 秒
          </Descriptions.Item>
        </Descriptions>
      ),
      onOk: async () => {
        setStarting(true);
        try {
          const result = await runGmailSetup(request);
          message.success(
            `Gmail 初始化脚本已启动，PID ${result.processId ?? "-"}`,
          );
        } catch (error) {
          message.error(formatError(error));
          throw error;
        } finally {
          setStarting(false);
        }
      },
    });
  };

  const chooseMailFile = () => {
    fileInputRef.current?.click();
  };

  const onMailFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const tauriPath = (file as unknown as { path?: string }).path;
    batchForm.setFieldValue("emailFile", tauriPath || file.name);
    event.target.value = "";
  };

  return (
    <>
      <PageHeader
        title="Gmail 初始化"
        description={`按 ${currentPlatformDefinition.localeName} 浏览器窗口执行单账号和批量邮箱文件初始化。`}
        extra={
          <Space>
            <Segmented
              value={mode}
              options={[
                { label: "单账号", value: "single" },
                { label: "批量文件", value: "batch" },
              ]}
              onChange={(value) => setMode(value as Mode)}
            />
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col span={24}></Col>

        <Col xs={24} xl={10}>
          {mode === "single" ? (
            <SingleAccountForm
              form={singleForm}
              platformPrefix={currentPlatform}
              onRun={() => void runSingle()}
              starting={starting}
            />
          ) : (
            <BatchFileForm
              form={batchForm}
              platformPrefix={currentPlatform}
              onChooseFile={chooseMailFile}
              onRun={() => void runBatch()}
              starting={starting}
            />
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.csv,.log"
            style={{ display: "none" }}
            onChange={onMailFileChange}
          />
        </Col>

        <Col xs={24} xl={14}>
          <GmailRunStatus />
        </Col>

        <Col span={24}>
          <ProcessOutputPanel title="Gmail 初始化步骤日志" />
        </Col>
      </Row>
    </>
  );
}

function SingleAccountForm({
  form,
  platformPrefix,
  onRun,
  starting,
}: {
  form: ReturnType<typeof Form.useForm<SingleFormValues>>[0];
  platformPrefix: string;
  onRun: () => void;
  starting: boolean;
}) {
  return (
    <Card
      title="单账号"
      extra={
        <Button
          type="primary"
          icon={<Play size={16} />}
          loading={starting}
          onClick={onRun}
        >
          启动
        </Button>
      }
    >
      <Form
        form={form}
        layout="vertical"
        requiredMark={false}
        initialValues={DEFAULT_SINGLE}
      >
        <Form.Item
          name="browserName"
          label="Bit浏览器窗口名称"
          rules={[{ required: true, message: "请输入窗口名称" }]}
        >
          <Input
            prefix={<Mail size={15} />}
            placeholder={`例如 ${platformPrefix}_001`}
          />
        </Form.Item>
        <Form.Item name="email" label="Google 邮箱">
          <Input placeholder="name@example.com；为空时只打开 Google 登录页" />
        </Form.Item>
        <Form.Item name="password" label="当前密码">
          <Input.Password
            prefix={<KeyRound size={15} />}
            placeholder="通过环境变量传给脚本"
            autoComplete="off"
          />
        </Form.Item>
        <Form.Item name="newPassword" label="新密码">
          <Input.Password
            prefix={<KeyRound size={15} />}
            placeholder="为空时脚本按自身默认策略处理"
            autoComplete="new-password"
          />
        </Form.Item>
        <SharedFields />
      </Form>
    </Card>
  );
}

function BatchFileForm({
  form,
  platformPrefix,
  onChooseFile,
  onRun,
  starting,
}: {
  form: ReturnType<typeof Form.useForm<BatchFormValues>>[0];
  platformPrefix: string;
  onChooseFile: () => void;
  onRun: () => void;
  starting: boolean;
}) {
  return (
    <Card
      title="批量邮箱文件"
      extra={
        <Button
          type="primary"
          icon={<Play size={16} />}
          loading={starting}
          onClick={onRun}
        >
          启动批量
        </Button>
      }
    >
      <Form
        form={form}
        layout="vertical"
        requiredMark={false}
        initialValues={DEFAULT_BATCH}
      >
        <Form.Item
          name="browserName"
          label="起始 Bit浏览器窗口名称"
          rules={[{ required: true, message: "请输入起始窗口名称" }]}
        >
          <Input
            prefix={<Mail size={15} />}
            placeholder={`例如 ${platformPrefix}_001，后续自动递增`}
          />
        </Form.Item>
        <Form.Item
          name="emailFile"
          label="邮箱文件"
          rules={[{ required: true, message: "请选择或输入邮箱文件路径" }]}
        >
          <Input
            placeholder="每行：账号----密码----备注"
            addonAfter={
              <Button
                type="text"
                size="small"
                icon={<FolderOpen size={14} />}
                onClick={onChooseFile}
              >
                选择
              </Button>
            }
          />
        </Form.Item>
        <Form.Item
          name="keepOpenOnError"
          label="失败时保留窗口"
          valuePropName="checked"
        >
          <Switch checkedChildren="保留" unCheckedChildren="关闭" />
        </Form.Item>
        <SharedFields />
      </Form>
    </Card>
  );
}

function SharedFields() {
  return (
    <Row gutter={12}>
      <Col span={24}>
        <Form.Item
          name="query"
          label="搜索词"
          rules={[{ required: true, message: "请输入搜索词" }]}
        >
          <Input placeholder="gmail" />
        </Form.Item>
      </Col>
      <Col xs={24} md={12}>
        <Form.Item
          name="timeoutSeconds"
          label="页面超时（秒）"
          rules={[{ required: true, message: "请输入页面超时" }]}
        >
          <InputNumber min={1} max={600} precision={0} className="full-width" />
        </Form.Item>
      </Col>
      <Col xs={24} md={12}>
        <Form.Item
          name="termsTimeoutSeconds"
          label="条款页超时（秒）"
          rules={[{ required: true, message: "请输入条款页超时" }]}
        >
          <InputNumber min={1} max={600} precision={0} className="full-width" />
        </Form.Item>
      </Col>
    </Row>
  );
}

function GmailRunStatus() {
  const [status, setStatus] = useState<ProcessStatus | null>(null);
  const [stdoutOffset, setStdoutOffset] = useState(0);
  const [stderrOffset, setStderrOffset] = useState(0);
  const [recentOutput, setRecentOutput] = useState("");

  const refresh = useCallback(async () => {
    const nextStatus = await getCurrentRunStatus();
    setStatus((current) => {
      if (current?.processId !== nextStatus.processId) {
        setStdoutOffset(0);
        setStderrOffset(0);
        setRecentOutput("");
      }
      return nextStatus;
    });

    const [stdout, stderr] = await Promise.all([
      getStdoutChunk(stdoutOffset),
      getStderrChunk(stderrOffset),
    ]);
    setStdoutOffset(stdout.nextOffset);
    setStderrOffset(stderr.nextOffset);
    if (stdout.content || stderr.content) {
      setRecentOutput((current) =>
        `${current}${stdout.content}${stderr.content}`.slice(-8000),
      );
    }
  }, [stderrOffset, stdoutOffset]);

  useEffect(() => {
    void refresh().catch(() => undefined);
    const timer = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 1800);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const gmailActive = status?.taskType === "gmail";
  const derived = deriveGmailStatus(status, recentOutput);

  return (
    <Card
      title="运行状态"
      extra={
        <Button icon={<RefreshCw size={16} />} onClick={() => void refresh()}>
          刷新
        </Button>
      }
    >
      <Space direction="vertical" size={14} className="full-width">
        <Descriptions size="small" column={1} bordered>
          <Descriptions.Item label="任务">
            {gmailActive ? "Gmail 初始化" : (status?.taskType ?? "-")}
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <StatusTag status={derived.tone} label={derived.label} />
          </Descriptions.Item>
          <Descriptions.Item label="PID">
            {status?.processId ?? "-"}
          </Descriptions.Item>
          <Descriptions.Item label="开始时间">
            {status?.startedAt ?? "-"}
          </Descriptions.Item>
          <Descriptions.Item label="结束时间">
            {status?.endedAt ?? "-"}
          </Descriptions.Item>
        </Descriptions>
        <Alert
          showIcon
          type={derived.alertType}
          message={derived.message}
          description={derived.description}
        />
        <Space wrap>
          <Tag>额外验证会保留窗口</Tag>
          <Tag>密码环境变量传递</Tag>
          <Tag>日志默认脱敏</Tag>
        </Space>
      </Space>
    </Card>
  );
}

function deriveGmailStatus(status: ProcessStatus | null, output: string) {
  const text = output.toLowerCase();
  const needsManual =
    output.includes("额外验证") ||
    output.includes("人工检查") ||
    output.includes("窗口保持打开") ||
    text.includes("challenge") ||
    text.includes("workspace");

  if (needsManual) {
    return {
      tone: "warning" as const,
      label: "需要人工处理",
      alertType: "warning" as const,
      message: "检测到登录挑战或需要人工检查",
      description:
        "请在 Bit浏览器当前窗口完成验证或检查页面状态，再根据输出决定是否重试。",
    };
  }

  if (!status || status.taskType !== "gmail") {
    return {
      tone: "idle" as const,
      label: "空闲",
      alertType: "info" as const,
      message: "暂无 Gmail 初始化任务",
      description: "启动单账号或批量任务后，这里会显示脚本状态和人工处理提示。",
    };
  }

  if (status.status === "running" || status.status === "starting") {
    return {
      tone: "running" as const,
      label: "运行中",
      alertType: "info" as const,
      message: "Gmail 初始化正在运行",
      description:
        "步骤日志会持续刷新，遇到 Google 额外验证时窗口会停留以便人工处理。",
    };
  }

  if (status.status === "completed") {
    return {
      tone: "ok" as const,
      label: "已完成",
      alertType: "success" as const,
      message: "Gmail 初始化流程已结束",
      description: "请根据步骤日志确认具体账号和窗口处理结果。",
    };
  }

  if (status.status === "failed" || status.status === "partial_failed") {
    return {
      tone: "error" as const,
      label: "失败",
      alertType: "error" as const,
      message: "Gmail 初始化失败",
      description: status.error ?? "请查看 stderr 和步骤日志定位失败原因。",
    };
  }

  return {
    tone: "warning" as const,
    label: status.status,
    alertType: "warning" as const,
    message: `当前状态：${status.status}`,
    description: status.error ?? "请查看步骤日志。",
  };
}

function maskPath(path: string) {
  const normalized = path.replace(/\\/g, "/");
  const parts = normalized.split("/").filter(Boolean);
  return parts.length > 1 ? `.../${parts[parts.length - 1]}` : path;
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
