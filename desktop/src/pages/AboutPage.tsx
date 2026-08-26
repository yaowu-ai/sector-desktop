import { useCallback, useEffect, useState } from "react";
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
import { CheckCircle2, Download, Info, RefreshCw } from "lucide-react";

import { PageHeader } from "../components/PageHeader";
import { getAppReleaseContext, openExternalLink } from "../services/api";
import {
  loadDesktopDownloadOptions,
  resolveDesktopDownloadUrl,
  type DesktopDownloadOptionResponse,
  type DesktopUpdateArch,
  type DesktopUpdatePlatform,
} from "../services/desktopApi";
import type { AppReleaseContext } from "../services/types";
import desktopIcon from "../../src-tauri/icons/icon.png";

const APP_VERSION = "0.1.0";
const DEFAULT_RELEASE_CONTEXT: AppReleaseContext = {
  version: APP_VERSION,
  platform: inferBrowserPlatform(),
  arch: "x64",
};

type UpdateStatus =
  | "idle"
  | "checking"
  | "available"
  | "opening"
  | "current"
  | "unavailable"
  | "error";

interface UpdateState {
  status: UpdateStatus;
  latestVersion?: string;
  downloadUrl?: string;
  platformLabel?: string;
  message?: string;
}

export function AboutPage() {
  const [releaseContext, setReleaseContext] = useState<AppReleaseContext>(
    DEFAULT_RELEASE_CONTEXT,
  );
  const [updateState, setUpdateState] = useState<UpdateState>({
    status: "idle",
  });

  useEffect(() => {
    let disposed = false;

    getAppReleaseContext()
      .then((context) => {
        if (!disposed) setReleaseContext(context);
      })
      .catch(() => {
        if (!disposed) setReleaseContext(DEFAULT_RELEASE_CONTEXT);
      });

    return () => {
      disposed = true;
    };
  }, []);

  const checkUpdate = useCallback(async () => {
    setUpdateState({ status: "checking" });

    try {
      const context = await resolveReleaseContext();
      setReleaseContext(context);

      if (!isSupportedDownloadTarget(context)) {
        setUpdateState({
          status: "unavailable",
          message: "当前系统暂未配置对应的桌面端安装包。",
        });
        return;
      }

      const response = await loadDesktopDownloadOptions();
      const option = findDownloadOption(response.options, context);

      if (!option?.available || !option.url) {
        setUpdateState({
          status: "unavailable",
          latestVersion: response.version,
          message: "服务端暂未发布当前系统对应的安装包。",
        });
        return;
      }

      const latestVersion = option.version || response.version || "";
      const downloadUrl = resolveDesktopDownloadUrl(option.url);
      const platformLabel = formatDownloadTarget(option);

      if (latestVersion && compareVersions(latestVersion, context.version) <= 0) {
        setUpdateState({
          status: "current",
          latestVersion,
          downloadUrl,
          platformLabel,
          message: "当前已是最新版本。",
        });
        return;
      }

      setUpdateState({
        status: "available",
        latestVersion,
        downloadUrl,
        platformLabel,
        message: latestVersion
          ? `发现新版本 ${latestVersion}。`
          : "发现当前系统可用的最新安装包。",
      });
    } catch (error) {
      setUpdateState({
        status: "error",
        message:
          error instanceof Error
            ? error.message
            : "检查更新失败，请稍后重试。",
      });
    }
  }, []);

  const handleUpdateAction = async () => {
    if (updateState.status !== "available" || !updateState.downloadUrl) {
      await checkUpdate();
      return;
    }

    setUpdateState((current) => ({
      ...current,
      status: "opening",
      message: "正在打开下载链接。",
    }));

    try {
      await openExternalLink(updateState.downloadUrl);
      setUpdateState((current) => ({
        ...current,
        status: "available",
        message: "已打开下载链接，请下载后退出当前客户端手动安装。",
      }));
      message.success("已打开浏览器下载链接，请下载后手动安装。");
    } catch {
      const opened = window.open(
        updateState.downloadUrl,
        "_blank",
        "noopener,noreferrer",
      );
      if (opened) {
        setUpdateState((current) => ({
          ...current,
          status: "available",
          message: "已打开下载链接，请下载后退出当前客户端手动安装。",
        }));
        message.success("已打开浏览器下载链接，请下载后手动安装。");
      } else {
        setUpdateState((current) => ({
          ...current,
          status: "error",
          message: "无法打开下载链接，请检查系统浏览器设置。",
        }));
        message.error("无法打开下载链接，请检查系统浏览器设置。");
      }
    }
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
                  <Typography.Text strong>
                    版本 {releaseContext.version}
                  </Typography.Text>
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
                {releaseContext.version}
              </Descriptions.Item>
              <Descriptions.Item
                label={
                  <InfoLabel
                    icon={<CheckCircle2 size={15} />}
                    text="更新状态"
                  />
                }
              >
                {renderUpdateStatus(updateState)}
              </Descriptions.Item>
              <Descriptions.Item label="当前平台">
                {formatReleaseContext(releaseContext)}
              </Descriptions.Item>
              <Descriptions.Item label="最新版本">
                {updateState.latestVersion || "未检查"}
              </Descriptions.Item>
            </Descriptions>
            <Space className="about-actions" wrap>
              <Button
                type="primary"
                icon={
                  updateState.status === "available" ? (
                    <Download size={16} />
                  ) : (
                    <RefreshCw size={16} />
                  )
                }
                loading={
                  updateState.status === "checking" ||
                  updateState.status === "opening"
                }
                onClick={handleUpdateAction}
              >
                {getUpdateActionText(updateState)}
              </Button>
            </Space>
            <Alert
              className="contact-hint"
              type={getUpdateAlertType(updateState)}
              showIcon
              message={getUpdateAlertMessage(updateState)}
              description={getUpdateAlertDescription(updateState)}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}

async function resolveReleaseContext() {
  try {
    return await getAppReleaseContext();
  } catch {
    return DEFAULT_RELEASE_CONTEXT;
  }
}

function inferBrowserPlatform(): AppReleaseContext["platform"] {
  const value = `${navigator.platform || ""} ${navigator.userAgent || ""}`.toLowerCase();
  if (value.includes("mac")) return "macos";
  if (value.includes("linux")) return "linux";
  return "windows";
}

function isSupportedDownloadTarget(context: AppReleaseContext) {
  return (
    (context.platform === "windows" || context.platform === "macos") &&
    (context.arch === "x64" || context.arch === "arm64")
  );
}

function findDownloadOption(
  options: DesktopDownloadOptionResponse[],
  context: AppReleaseContext,
) {
  return options.find(
    (option) =>
      option.platform === (context.platform as DesktopUpdatePlatform) &&
      option.arch === (context.arch as DesktopUpdateArch),
  );
}

function compareVersions(a: string, b: string) {
  const left = parseVersion(a);
  const right = parseVersion(b);
  const length = Math.max(left.length, right.length);

  for (let index = 0; index < length; index += 1) {
    const leftPart = left[index] ?? 0;
    const rightPart = right[index] ?? 0;
    if (leftPart > rightPart) return 1;
    if (leftPart < rightPart) return -1;
  }
  return 0;
}

function parseVersion(value: string) {
  return value
    .trim()
    .replace(/^v/i, "")
    .split(/[.-]/)
    .map((part) => Number.parseInt(part, 10))
    .filter((part) => Number.isFinite(part));
}

function renderUpdateStatus(state: UpdateState) {
  if (state.status === "checking") return "检查中";
  if (state.status === "opening") return "打开下载链接中";
  if (state.status === "available") {
    return (
      <Typography.Text type="success">
        {state.latestVersion ? `可更新到 ${state.latestVersion}` : "有可用安装包"}
      </Typography.Text>
    );
  }
  if (state.status === "current") return "已是最新版本";
  if (state.status === "unavailable") {
    return <Typography.Text type="secondary">暂无安装包</Typography.Text>;
  }
  if (state.status === "error") {
    return <Typography.Text type="danger">检查失败</Typography.Text>;
  }
  return "未检查";
}

function getUpdateActionText(state: UpdateState) {
  if (state.status === "checking") return "检查中";
  if (state.status === "opening") return "打开中";
  if (state.status === "available") return "下载最新版";
  if (state.status === "current") return "重新检查";
  return "检查更新";
}

function getUpdateAlertType(state: UpdateState) {
  if (state.status === "available") return "success" as const;
  if (state.status === "error") return "error" as const;
  if (state.status === "unavailable") return "warning" as const;
  return "info" as const;
}

function getUpdateAlertMessage(state: UpdateState) {
  if (state.message) return state.message;
  return "手动更新";
}

function getUpdateAlertDescription(state: UpdateState) {
  if (state.status === "opening") {
    return "正在调用系统浏览器打开安装包下载地址，不会自动安装或后台更新。";
  }
  if (state.status === "available") {
    return `适用安装包：${state.platformLabel || "当前平台"}。点击“下载最新版”会打开浏览器下载安装包，请退出当前客户端后手动安装。`;
  }
  if (state.status === "current") {
    return "服务端没有比当前客户端更高的已发布版本。";
  }
  if (state.status === "unavailable") {
    return "请先在 h-sector 后台为当前平台和架构新增并发布桌面端版本。";
  }
  if (state.status === "error") {
    return "请确认 h-sector 服务端可访问，并且桌面端 API 地址配置正确。";
  }
  return "点击按钮后会向 h-sector 获取当前系统对应的最新安装包地址，不会自动下载或自动安装。";
}

function formatReleaseContext(context: AppReleaseContext) {
  if (context.platform === "windows") return "Windows x64";
  if (context.platform === "macos" && context.arch === "arm64") {
    return "macOS Apple Silicon";
  }
  if (context.platform === "macos" && context.arch === "x64") return "macOS Intel";
  return `${context.platform} ${context.arch}`;
}

function formatDownloadTarget(option: DesktopDownloadOptionResponse) {
  if (option.platform === "windows") return "Windows x64";
  if (option.platform === "macos" && option.arch === "arm64") {
    return "macOS Apple Silicon";
  }
  if (option.platform === "macos" && option.arch === "x64") return "macOS Intel";
  return option.label;
}

function InfoLabel({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <Space size={6}>
      {icon}
      <span>{text}</span>
    </Space>
  );
}
