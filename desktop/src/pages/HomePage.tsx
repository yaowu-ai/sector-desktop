import {
  Button,
  Card,
  Col,
  DatePicker,
  Descriptions,
  Row,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
  message,
} from "antd";
import dayjs from "dayjs";
import type { Dayjs } from "dayjs";
import {
  RefreshCw,
  Settings2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "../components/PageHeader";
import { PlatformScopeFilter } from "../components/PlatformScopeFilter";
import { StatusTag } from "../components/StatusTag";
import {
  getHomeSummary,
  getProjectPaths,
  loadAccounts,
} from "../services/api";
import {
  getPlatformLabel,
  isExecutablePlatform,
  PLATFORMS,
} from "../services/platforms";
import type {
  AccountSummary,
  HomeSummary,
  Platform,
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
  const [loading, setLoading] = useState(true);

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
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div>
      <PageHeader
        title="首页"
        description="运营概览和平台账号状态。"
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

          <Col span={24}>
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
