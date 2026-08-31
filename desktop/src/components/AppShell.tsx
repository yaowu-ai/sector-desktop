import {
  Alert,
  Badge,
  Button,
  Layout,
  Menu,
  Space,
  Switch,
  Tooltip,
  Typography,
  message,
} from "antd";
import type { MenuProps } from "antd";
import { Bell, LogOut, Moon, RefreshCw, Sun, UserRound } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useDesktopAuth } from "../app/DesktopAuthContext";
import { useDesktopNotifications } from "../app/DesktopNotificationsContext";
import {
  DESKTOP_USER_ROLES,
  filterRoutesByRole,
  normalizeDesktopUserRole,
} from "../app/routePermissions";
import { appRoutes, routes, type AppRoute } from "../app/routes";
import {
  PROCESS_STARTED_EVENT,
  checkBitbrowserApi,
  getCurrentRunStatus,
} from "../services/api";
import {
  reportDesktopUsage,
  type DesktopSession,
} from "../services/desktopApi";
import { runStatusLabel } from "../services/runStatus";
import type {
  ApiStatus,
  ProcessStartResult,
  ProcessStatus,
  RunStatus,
} from "../services/types";
import { PlatformSelector } from "./PlatformSelector";
import { RouteScopeFrame } from "./RouteScopeFrame";
import { StatusTag, type StatusTone } from "./StatusTag";

const { Header, Sider, Content } = Layout;

const TASK_POLL_MS = 1500;
const BITBROWSER_POLL_MS = 10000;

interface AppShellProps {
  themeMode: "light" | "dark";
  onThemeModeChange: (mode: "light" | "dark") => void;
}

export function AppShell({ themeMode, onThemeModeChange }: AppShellProps) {
  const contentRef = useRef<HTMLElement>(null);
  const desktopAuth = useDesktopAuth();
  const desktopNotifications = useDesktopNotifications();
  const startupReportedRef = useRef<string | null>(null);
  const previousProcessStatusRef = useRef<ProcessStatus | null>(null);
  const terminalUsageReportedRef = useRef<Set<string>>(new Set());
  const [activeKey, setActiveKey] = useState(getInitialRouteKey);
  const [bitbrowserStatus, setBitbrowserStatus] = useState<ApiStatus | null>(
    null,
  );
  const [processStatus, setProcessStatus] = useState<ProcessStatus | null>(
    null,
  );
  const [refreshing, setRefreshing] = useState(false);
  const [shellError, setShellError] = useState<string | null>(null);
  const userRole = normalizeDesktopUserRole(desktopAuth.session?.userRole);
  const permittedRoutes = useMemo(
    () => filterRoutesByRole(routes, userRole),
    [userRole],
  );
  const permittedAppRoutes = useMemo(
    () => filterRoutesByRole(appRoutes, userRole),
    [userRole],
  );
  const defaultRouteKey = permittedRoutes[0]?.key ?? "home";
  const isTechnician = userRole === DESKTOP_USER_ROLES.technician;
  const canOpenNotifications = permittedAppRoutes.some(
    (route) => route.key === "notifications",
  );
  const siderMenuItems = useMemo(
    () =>
      buildSiderMenuItems(permittedRoutes, desktopNotifications.unreadCount),
    [desktopNotifications.unreadCount, permittedRoutes],
  );
  const [openKeys, setOpenKeys] = useState<string[]>(() =>
    getInitialOpenKeys(),
  );

  const activeRoute = useMemo(
    () =>
      permittedAppRoutes.find((route) => route.key === activeKey) ??
      permittedRoutes[0] ??
      routes[0],
    [activeKey, permittedAppRoutes, permittedRoutes],
  );

  const refreshBitbrowser = useCallback(async () => {
    const nextStatus = await checkBitbrowserApi();
    setBitbrowserStatus(nextStatus);
    return nextStatus;
  }, []);

  const reportTerminalUsageIfNeeded = useCallback(
    (nextStatus: ProcessStatus) => {
      const previous = previousProcessStatusRef.current;
      previousProcessStatusRef.current = nextStatus;

      if (!desktopAuth.session) return;
      if (!isTerminalUsageStatus(nextStatus.status)) return;
      if (
        previous?.status === nextStatus.status &&
        previous?.endedAt === nextStatus.endedAt
      )
        return;

      const reportKey = buildProcessUsageKey(nextStatus);
      if (terminalUsageReportedRef.current.has(reportKey)) return;
      terminalUsageReportedRef.current.add(reportKey);

      const taskType = nextStatus.taskType || "unknown";
      const queuedCount = nextStatus.queuedAccounts.length;
      const completedCount = nextStatus.completedAccounts.length;

      void reportUsageMetric(
        desktopAuth.session,
        `desktop_task_${nextStatus.status}`,
        1,
      );
      void reportUsageMetric(
        desktopAuth.session,
        `desktop_task_${nextStatus.status}.${taskType}`,
        1,
      );
      if (queuedCount > 0) {
        void reportUsageMetric(
          desktopAuth.session,
          "desktop_task_account_queued",
          queuedCount,
        );
      }
      if (completedCount > 0) {
        void reportUsageMetric(
          desktopAuth.session,
          "desktop_task_account_completed",
          completedCount,
        );
      }
    },
    [desktopAuth.session],
  );

  const refreshTask = useCallback(async () => {
    const nextStatus = await getCurrentRunStatus();
    setProcessStatus(nextStatus);
    reportTerminalUsageIfNeeded(nextStatus);
    return nextStatus;
  }, [reportTerminalUsageIfNeeded]);

  const refreshAll = useCallback(async () => {
    setRefreshing(true);
    setShellError(null);
    try {
      await Promise.all([refreshBitbrowser(), refreshTask()]);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      setShellError(detail);
      message.error(detail);
    } finally {
      setRefreshing(false);
    }
  }, [refreshBitbrowser, refreshTask]);

  useEffect(() => {
    window.location.hash = activeKey;
  }, [activeKey]);

  useEffect(() => {
    if (permittedAppRoutes.some((route) => route.key === activeKey)) return;
    setActiveKey(defaultRouteKey);
  }, [activeKey, defaultRouteKey, permittedAppRoutes]);

  useEffect(() => {
    const groupKey = permittedRoutes.find((route) => route.key === activeKey)
      ?.menuGroup?.key;
    if (!groupKey) return;
    setOpenKeys((current) =>
      current.includes(groupKey) ? current : [...current, groupKey],
    );
  }, [activeKey, permittedRoutes]);

  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0, left: 0 });
  }, [activeKey]);

  useEffect(() => {
    const onHashChange = () => {
      setActiveKey(getInitialRouteKey(permittedAppRoutes, defaultRouteKey));
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [defaultRouteKey, permittedAppRoutes]);

  useEffect(() => {
    void refreshAll();
  }, []);

  useEffect(() => {
    if (!desktopAuth.session) return;
    if (startupReportedRef.current === desktopAuth.session.accessToken) return;

    startupReportedRef.current = desktopAuth.session.accessToken;
    void reportUsageMetric(desktopAuth.session, "desktop_app_launch", 1);
    void reportUsageMetric(desktopAuth.session, "desktop_active_device", 1);
  }, [desktopAuth.session]);

  useEffect(() => {
    const onProcessStarted = (event: Event) => {
      const result = (event as CustomEvent<ProcessStartResult>).detail;
      if (desktopAuth.session) {
        if (result?.taskType) {
          void reportUsageMetric(
            desktopAuth.session,
            `desktop_task_started.${result.taskType}`,
            1,
          );
        }
      }
      void refreshTask().catch(handleBackgroundError(setShellError));
    };
    window.addEventListener(PROCESS_STARTED_EVENT, onProcessStarted);
    return () =>
      window.removeEventListener(PROCESS_STARTED_EVENT, onProcessStarted);
  }, [desktopAuth.session, refreshTask]);

  useEffect(() => {
    const id = window.setInterval(() => {
      void refreshTask().catch(handleBackgroundError(setShellError));
    }, TASK_POLL_MS);
    return () => window.clearInterval(id);
  }, [refreshTask]);

  useEffect(() => {
    const id = window.setInterval(() => {
      void refreshBitbrowser().catch(handleBackgroundError(setShellError));
    }, BITBROWSER_POLL_MS);
    return () => window.clearInterval(id);
  }, [refreshBitbrowser]);

  return (
    <Layout className="app-shell">
      <Sider width={208} className="app-sider">
        <div className="app-brand">
          <Typography.Title level={4}>星域</Typography.Title>
          <Typography.Text type="secondary">自动化运营工具</Typography.Text>
        </div>
        <Menu
          mode="inline"
          selectedKeys={
            permittedRoutes.some((route) => route.key === activeKey)
              ? [activeKey]
              : []
          }
          openKeys={openKeys}
          onOpenChange={setOpenKeys}
          onClick={({ key }) => {
            if (permittedRoutes.some((route) => route.key === key)) {
              setActiveKey(key);
            }
          }}
          items={siderMenuItems}
        />
        <div className="app-sider-account">
          <button
            className="app-sider-account-main"
            type="button"
            onClick={() => setActiveKey("profile")}
          >
            <span className="app-sider-account-icon">
              <UserRound size={16} />
            </span>
            <span className="app-sider-account-text">
              <Typography.Text type="secondary">当前账号</Typography.Text>
              <Typography.Text strong ellipsis>
                {desktopAuth.session?.username ?? "产品账号"}
              </Typography.Text>
            </span>
          </button>
          <Tooltip title="退出登录">
            <Button
              className="app-sider-logout"
              type="text"
              icon={<LogOut size={16} />}
              onClick={desktopAuth.logout}
            />
          </Tooltip>
        </div>
      </Sider>
      <Layout>
        <Header className="app-header">
          <Space size={16} wrap>
            <PlatformSelector
              userRole={userRole}
              canOpenSettings={isTechnician}
              onOpenSettings={() => {
                if (
                  permittedAppRoutes.some((route) => route.key === "platforms")
                ) {
                  setActiveKey("platforms");
                }
              }}
            />
            <Space size={12} wrap>
              <Tooltip title={bitbrowserTooltip(bitbrowserStatus)}>
                <span>
                  <StatusTag
                    status={bitbrowserTone(bitbrowserStatus)}
                    label={bitbrowserLabel(bitbrowserStatus)}
                  />
                </span>
              </Tooltip>
              <StatusTag
                status={processTone(processStatus)}
                label={processLabel(processStatus)}
              />
            </Space>
          </Space>
          <Space size={12}>
            {canOpenNotifications ? (
              <Tooltip title="消息通知">
                <Badge
                  className="app-header-notification-badge"
                  count={desktopNotifications.unreadCount}
                  overflowCount={99}
                  size="small"
                  offset={[-8, 10]}
                >
                  <Button
                    className="app-header-notification"
                    type="text"
                    aria-label="消息通知"
                    icon={<Bell size={22} />}
                    onClick={() => setActiveKey("notifications")}
                  />
                </Badge>
              </Tooltip>
            ) : null}
            <Tooltip
              title={themeMode === "dark" ? "切换为浅色模式" : "切换为深色模式"}
            >
              <Switch
                checked={themeMode === "dark"}
                checkedChildren={<Moon size={14} />}
                unCheckedChildren={<Sun size={14} />}
                onChange={(checked) =>
                  onThemeModeChange(checked ? "dark" : "light")
                }
              />
            </Tooltip>
            <Button
              icon={<RefreshCw size={16} />}
              onClick={refreshAll}
              loading={refreshing}
            >
              刷新
            </Button>
          </Space>
        </Header>
        <Content ref={contentRef} className="app-content">
          {shellError ? (
            <Alert
              className="shell-alert"
              type="error"
              showIcon
              closable
              message="桌面端状态刷新失败"
              description={shellError}
              onClose={() => setShellError(null)}
            />
          ) : null}
          {desktopAuth.entitlementWarning ? (
            <Alert
              className="shell-alert"
              type="warning"
              showIcon
              closable
              message="授权状态暂时无法刷新"
              description="当前网络或授权服务暂时不可用，已保留当前登录状态，系统会自动重试。"
            />
          ) : null}
          <RouteScopeFrame
            routeKey={activeRoute.key}
            routeLabel={activeRoute.label}
            scope={activeRoute.scope}
            capability={activeRoute.capability}
          >
            {activeRoute.element}
          </RouteScopeFrame>
        </Content>
      </Layout>
    </Layout>
  );
}

function getInitialRouteKey(
  permittedAppRoutes = appRoutes,
  defaultRouteKey = routes[0].key,
) {
  const hashKey = window.location.hash.replace(/^#/, "");
  if (hashKey === "targets") {
    return permittedAppRoutes.some((route) => route.key === "target-engagement")
      ? "target-engagement"
      : defaultRouteKey;
  }
  return permittedAppRoutes.some((route) => route.key === hashKey)
    ? hashKey
    : defaultRouteKey;
}

function getInitialOpenKeys() {
  const activeKey = getInitialRouteKey();
  const groupKey = routes.find((route) => route.key === activeKey)?.menuGroup
    ?.key;
  return groupKey ? [groupKey] : [];
}

function buildSiderMenuItems(
  permittedRoutes: AppRoute[],
  notificationUnreadCount: number,
): MenuProps["items"] {
  const items: NonNullable<MenuProps["items"]> = [];
  const groupIndex = new Map<string, number>();

  for (const route of permittedRoutes) {
    const Icon = route.icon;
    const item = {
      key: route.key,
      icon: <Icon size={route.menuGroup ? 16 : 18} />,
      label: buildMenuLabel(route, notificationUnreadCount),
    };

    if (!route.menuGroup) {
      items.push(item);
      continue;
    }

    const existingIndex = groupIndex.get(route.menuGroup.key);
    if (existingIndex !== undefined) {
      const group = items[existingIndex];
      if (group && "children" in group && Array.isArray(group.children)) {
        group.children.push(item);
      }
      continue;
    }

    const GroupIcon = route.menuGroup.icon;
    groupIndex.set(route.menuGroup.key, items.length);
    items.push({
      key: route.menuGroup.key,
      icon: <GroupIcon size={18} />,
      label: route.menuGroup.label,
      children: [item],
    });
  }

  return items;
}

function buildMenuLabel(route: AppRoute, notificationUnreadCount: number) {
  if (route.key !== "notifications" || notificationUnreadCount <= 0)
    return route.label;
  return (
    <span className="app-menu-notification-label">
      <span>{route.label}</span>
      <Badge count={notificationUnreadCount} overflowCount={99} size="small" />
    </span>
  );
}

function bitbrowserTone(status: ApiStatus | null): StatusTone {
  if (!status) return "idle";
  return status.available ? "ok" : "error";
}

function bitbrowserLabel(status: ApiStatus | null) {
  if (!status) return "Bit浏览器待检测";
  return status.available ? "Bit浏览器在线" : "Bit浏览器不可用";
}

function bitbrowserTooltip(status: ApiStatus | null) {
  if (!status) return "尚未检测";
  if (status.available) return status.apiUrl;
  return (
    formatBitbrowserError(status.error) ||
    `无法连接 Bit浏览器：${status.apiUrl}`
  );
}

function formatBitbrowserError(error?: string) {
  if (!error) return "";

  const normalized = error.trim();
  const matched = normalized.match(/failed to connect\s+([^:]+:\d+):\s*(.+)/i);
  if (matched) {
    return `无法连接 Bit浏览器（${matched[1]}）：${formatConnectionReason(matched[2])}`;
  }

  if (/connection timed out/i.test(normalized)) return "连接 Bit浏览器超时";
  if (/connection refused/i.test(normalized)) return "Bit浏览器拒绝连接";
  if (/failed to connect/i.test(normalized)) return "无法连接 Bit浏览器";
  return normalized;
}

function formatConnectionReason(reason: string) {
  const normalized = reason.trim();
  if (/connection timed out/i.test(normalized)) return "连接超时";
  if (/connection refused/i.test(normalized)) return "连接被拒绝";
  return normalized;
}

function processTone(status: ProcessStatus | null): StatusTone {
  if (!status || status.status === "idle") return "idle";
  if (status.status === "running" || status.status === "starting")
    return "running";
  if (status.status === "intervention_required") return "warning";
  if (status.status === "failed" || status.status === "partial_failed")
    return "error";
  return "warning";
}

function processLabel(status: ProcessStatus | null) {
  if (!status) return "当前任务待检测";
  if (status.status === "idle") return "当前任务空闲";
  return `当前任务：${runStatusLabel(status.status)}`;
}

function handleBackgroundError(setShellError: (value: string) => void) {
  return (error: unknown) => {
    setShellError(error instanceof Error ? error.message : String(error));
  };
}

function isTerminalUsageStatus(status: RunStatus) {
  return (
    status === "completed" || status === "partial_failed" || status === "failed"
  );
}

function buildProcessUsageKey(status: ProcessStatus) {
  return [
    status.processId ?? "no-process",
    status.taskType ?? "unknown",
    status.status,
    status.startedAt ?? "no-start",
    status.endedAt ?? "no-end",
  ].join(":");
}

async function reportUsageMetric(
  session: DesktopSession,
  metricKey: string,
  metricValue: number,
) {
  try {
    await reportDesktopUsage(session, {
      metricKey,
      metricValue,
      metricDate: new Date().toISOString().split("T")[0],
    });
  } catch (error) {
    console.warn("[desktop usage] report failed", metricKey, error);
  }
}
