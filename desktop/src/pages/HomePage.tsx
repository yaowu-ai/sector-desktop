import {
  Button,
  Card,
  Col,
  DatePicker,
  Descriptions,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import dayjs from "dayjs";
import type { Dayjs } from "dayjs";
import {
  CalendarClock,
  FileText,
  Play,
  RefreshCw,
  RotateCw,
  Send,
  Settings2,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "../components/PageHeader";
import { PlatformScopeFilter } from "../components/PlatformScopeFilter";
import { ProcessOutputPanel } from "../components/ProcessOutputPanel";
import { StatusTag } from "../components/StatusTag";
import {
  getHomeSummary,
  getProjectPaths,
  loadAccounts,
  runPlatformTask,
  startScheduler,
} from "../services/api";
import {
  getAutomaticExecutionDisabledReason,
  getPlatformLabel,
  isExecutablePlatform,
  PLATFORMS,
} from "../services/platforms";
import type {
  AccountSummary,
  HomeSummary,
  Platform,
  ProcessStartResult,
  ProjectPaths,
} from "../services/types";
import type { PlatformFilterValue } from "../app/pageScope";

const { RangePicker } = DatePicker;

type TimeRange = [Dayjs, Dayjs] | null;

export function HomePage() {
  const [platformFilter, setPlatformFilter] =
    useState<PlatformFilterValue>("all");
  const [timeRange, setTimeRange] = useState<TimeRange>(null);
  const [paths, setPaths] = useState<ProjectPaths | null>(null);
  const [summary, setSummary] = useState<HomeSummary | null>(null);
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [startingRun, setStartingRun] = useState(false);
  const [startingScheduler, setStartingScheduler] = useState(false);

  const selectedAccount = useMemo(
    () =>
      accounts.find(
        (account) =>
          account.id === selectedAccountId &&
          accountMatchesPlatform(account, platformFilter),
      ),
    [accounts, platformFilter, selectedAccountId],
  );
  const filteredAccounts = useMemo(
    () =>
      accounts.filter((account) =>
        accountMatchesPlatform(account, platformFilter),
      ),
    [accounts, platformFilter],
  );
  const executableEnabledAccounts = useMemo(
    () =>
      filteredAccounts.filter(
        (account) => account.enabled && isExecutablePlatform(account.platform),
      ).length,
    [filteredAccounts],
  );
  const platformSummaries = useMemo(
    () =>
      PLATFORMS.map((platform) => {
        const platformAccounts = filteredAccounts.filter(
          (account) => account.platform === platform.id,
        );
        return {
          ...platform,
          total: platformAccounts.length,
          enabled: platformAccounts.filter((account) => account.enabled).length,
        };
      }),
    [filteredAccounts],
  );
  const accountOptions = useMemo(
    () =>
      filteredAccounts.map((account) => ({
        value: account.id,
        label: `${account.id} · ${getPlatformLabel(account.platform)}${account.enabled ? "" : "（停用）"}${
          isExecutablePlatform(account.platform) ? "" : "（未适配）"
        }`,
        disabled: !isExecutablePlatform(account.platform),
      })),
    [filteredAccounts],
  );
  const runAllDisabledReason =
    executableEnabledAccounts === 0
      ? platformFilter === "all"
        ? "当前筛选下没有可执行账号"
        : getAutomaticExecutionDisabledReason(platformFilter, "warmupTask")
      : undefined;
  const runSelectedDisabledReason = !selectedAccountId
    ? "请先选择账号"
    : !selectedAccount
      ? "所选账号不在当前筛选范围内"
      : !isExecutablePlatform(selectedAccount.platform)
        ? getAutomaticExecutionDisabledReason(
            selectedAccount.platform,
            "warmupTask",
          )
        : undefined;

  const refresh = async () => {
    setLoading(true);
    try {
      const [nextPaths, nextAccounts, nextSummary] = await Promise.all([
        getProjectPaths(),
        loadAccounts(),
        getHomeSummary(),
      ]);
      setPaths(nextPaths);
      setAccounts(nextAccounts);
      setSummary(nextSummary);
      setSelectedAccountId((current) => {
        if (current && nextAccounts.some((account) => account.id === current)) {
          return current;
        }
        return (
          nextAccounts.find((account) => account.id === "tiktok_101")?.id ??
          nextAccounts[0]?.id
        );
      });
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  const runSelected = async () => {
    if (!selectedAccountId) {
      message.warning("请先选择账号");
      return;
    }
    if (selectedAccount && !isExecutablePlatform(selectedAccount.platform)) {
      message.warning(
        `${getPlatformLabel(selectedAccount.platform)} 尚未适配自动执行`,
      );
      return;
    }

    await runScript(() =>
      runPlatformTask({
        platform: selectedAccount?.platform ?? "tiktok",
        taskType: "fyp",
        accountIds: [selectedAccountId],
        mode: "single",
      }),
    );
  };

  const runAll = async () => {
    if (executableEnabledAccounts === 0) {
      message.warning("没有可执行平台的启用账号");
      return;
    }
    await runScript(() =>
      runPlatformTask({
        platform: platformFilter === "all" ? "tiktok" : platformFilter,
        taskType: "fyp",
        accountIds: [],
        mode: "all",
      }),
    );
  };

  const runScript = async (runner: () => Promise<ProcessStartResult>) => {
    setStartingRun(true);
    try {
      const nextResult = await runner();
      message.success(`任务已启动，PID ${nextResult.processId ?? "-"}`);
      await refresh();
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setStartingRun(false);
    }
  };

  const runScheduler = async () => {
    setStartingScheduler(true);
    try {
      const startResult = await startScheduler();
      message.success(`调度服务已启动，PID ${startResult.processId}`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setStartingScheduler(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    setSelectedAccountId((current) => {
      if (
        current &&
        filteredAccounts.some((account) => account.id === current)
      ) {
        return current;
      }
      return (
        filteredAccounts.find((account) => account.id === "tiktok_101")?.id ??
        filteredAccounts[0]?.id
      );
    });
  }, [filteredAccounts]);

  return (
    <div>
      <PageHeader
        title="首页"
        description="运营概览、脚本启动和常用入口。"
        extra={
          <Button
            icon={<RefreshCw size={16} />}
            onClick={refresh}
            loading={loading}
          >
            刷新
          </Button>
        }
      />

      <Spin spinning={loading}>
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Card>
              <Space wrap size={12}>
                <PlatformScopeFilter
                  value={platformFilter}
                  onChange={setPlatformFilter}
                />
                <RangePicker
                  showTime
                  value={timeRange}
                  onChange={(value) => setTimeRange(value as TimeRange)}
                />
                <Tag color="blue">
                  {platformFilter === "all"
                    ? "全部平台"
                    : getPlatformLabel(platformFilter)}
                </Tag>
                {timeRange ? (
                  <Tag>{formatTimeRange(timeRange)}</Tag>
                ) : (
                  <Tag>全部时间</Tag>
                )}
              </Space>
            </Card>
          </Col>
          <Col xs={24} md={12} xl={4}>
            <MetricCard
              title="可执行启用账号"
              value={executableEnabledAccounts}
            />
          </Col>
          <Col xs={24} md={12} xl={4}>
            <Card>
              <Statistic
                title="BitBrowser API"
                value={summary?.bitbrowser.available ? "在线" : "不可用"}
                valueStyle={{ fontSize: 22 }}
              />
              <div className="metric-footnote">
                <StatusTag
                  status={summary?.bitbrowser.available ? "ok" : "error"}
                  label={summary?.bitbrowser.apiUrl ?? "未检测"}
                />
              </div>
            </Card>
          </Col>
          <Col xs={24} md={12} xl={4}>
            <MetricCard
              title="今日计划任务"
              value={summary?.todayPlannedTasks ?? 0}
            />
          </Col>
          <Col xs={24} md={12} xl={4}>
            <MetricCard
              title="今日完成账号"
              value={summary?.todayCompletedAccounts ?? 0}
            />
          </Col>
          <Col xs={24} md={12} xl={4}>
            <MetricCard
              title="今日失败账号"
              value={summary?.todayFailedAccounts ?? 0}
              danger
            />
          </Col>
          <Col xs={24} md={12} xl={4}>
            <MetricCard
              title="今日目标互动"
              value={summary?.todayTargetInteractions ?? 0}
            />
          </Col>

          <Col xs={24} xl={10}>
            <Card title="快捷操作">
              <Space direction="vertical" size={14} className="full-width">
                <Tooltip title={runAllDisabledReason}>
                  <span>
                    <Button
                      block
                      type="primary"
                      icon={<Users size={16} />}
                      onClick={runAll}
                      loading={startingRun}
                      disabled={Boolean(runAllDisabledReason)}
                    >
                      运行全部可执行账号
                    </Button>
                  </span>
                </Tooltip>
                <Space.Compact block>
                  <Select
                    value={selectedAccountId}
                    onChange={setSelectedAccountId}
                    placeholder="选择账号"
                    options={accountOptions}
                    showSearch
                  />
                  <Tooltip title={runSelectedDisabledReason}>
                    <span>
                      <Button
                        type="primary"
                        icon={<Play size={16} />}
                        onClick={runSelected}
                        loading={startingRun}
                        disabled={Boolean(runSelectedDisabledReason)}
                      >
                        运行
                      </Button>
                    </span>
                  </Tooltip>
                </Space.Compact>
                <Button
                  block
                  icon={<Send size={16} />}
                  onClick={runScheduler}
                  loading={startingScheduler}
                >
                  启动调度服务
                </Button>
                <Row gutter={[10, 10]}>
                  <Col span={8}>
                    <Button
                      block
                      icon={<CalendarClock size={16} />}
                      onClick={() => goRoute("scheduler")}
                    >
                      今日排期
                    </Button>
                  </Col>
                  <Col span={8}>
                    <Button
                      block
                      icon={<RotateCw size={16} />}
                      onClick={() => goRoute("browser")}
                    >
                      同步账号
                    </Button>
                  </Col>
                  <Col span={8}>
                    <Button
                      block
                      icon={<FileText size={16} />}
                      onClick={() => goRoute("comments")}
                    >
                      评论池
                    </Button>
                  </Col>
                </Row>
                {selectedAccount ? (
                  <Descriptions size="small" column={1} bordered>
                    <Descriptions.Item label="当前账号">
                      {selectedAccount.id}
                    </Descriptions.Item>
                    <Descriptions.Item label="平台">
                      {getPlatformLabel(selectedAccount.platform)}
                    </Descriptions.Item>
                    <Descriptions.Item label="状态">
                      {selectedAccount.enabled ? "启用" : "停用"}
                    </Descriptions.Item>
                    <Descriptions.Item label="备注">
                      {selectedAccount.notes || "-"}
                    </Descriptions.Item>
                  </Descriptions>
                ) : null}
              </Space>
            </Card>
          </Col>

          <Col xs={24} xl={14}>
            <Space direction="vertical" size={16} className="full-width">
              <Card title="运行状态" extra={<Settings2 size={16} />}>
                <Descriptions size="small" column={1} bordered>
                  <Descriptions.Item label="运行模式">
                    {formatRuntimeMode(paths?.runtimeMode)}
                  </Descriptions.Item>
                  <Descriptions.Item label="账号配置">
                    <StatusTag
                      status={paths?.configPath ? "ok" : "warning"}
                      label={paths?.configPath ? "已加载" : "未加载"}
                    />
                  </Descriptions.Item>
                  <Descriptions.Item label="最近读取">
                    {dayjs().format("YYYY-MM-DD HH:mm:ss")}
                  </Descriptions.Item>
                </Descriptions>
              </Card>

              <Card title="平台账号概览">
                <Row gutter={[12, 12]}>
                  {platformSummaries.map((platform) => (
                    <Col xs={24} sm={12} xl={6} key={platform.id}>
                      <div className="platform-summary-tile">
                        <Space
                          direction="vertical"
                          size={6}
                          className="full-width"
                        >
                          <Space
                            align="center"
                            className="platform-summary-head"
                          >
                            <Typography.Text strong>
                              {platform.localeName}
                            </Typography.Text>
                            <Tag
                              color={
                                platform.automaticExecutionSupported
                                  ? "green"
                                  : "gold"
                              }
                            >
                              {platform.automaticExecutionSupported
                                ? "可执行"
                                : "预留"}
                            </Tag>
                          </Space>
                          <Typography.Text type="secondary">
                            启用 {platform.enabled} / 总计 {platform.total}
                          </Typography.Text>
                          <Typography.Text type="secondary" ellipsis>
                            {platform.accountPrefix}*
                          </Typography.Text>
                        </Space>
                      </div>
                    </Col>
                  ))}
                </Row>
              </Card>
            </Space>
          </Col>

          <Col span={24}>
            <ProcessOutputPanel title="脚本输出" />
          </Col>
        </Row>
      </Spin>
    </div>
  );
}

function MetricCard({
  title,
  value,
  danger,
}: {
  title: string;
  value: number;
  danger?: boolean;
}) {
  return (
    <Card>
      <Statistic
        title={title}
        value={value}
        valueStyle={danger ? { color: "#dc2626" } : undefined}
      />
    </Card>
  );
}

function goRoute(routeKey: string) {
  window.location.hash = routeKey;
}

function accountMatchesPlatform(
  account: { platform: Platform },
  platformFilter: PlatformFilterValue,
) {
  return platformFilter === "all" || account.platform === platformFilter;
}

function formatTimeRange(timeRange: TimeRange) {
  if (!timeRange) {
    return "全部时间";
  }
  return `${timeRange[0].format("YYYY-MM-DD HH:mm")} - ${timeRange[1].format("YYYY-MM-DD HH:mm")}`;
}

function formatRuntimeMode(mode?: ProjectPaths["runtimeMode"]) {
  if (mode === "bundled") {
    return "内置运行时";
  }
  if (mode === "source") {
    return "源码开发模式";
  }
  return "未检测";
}
