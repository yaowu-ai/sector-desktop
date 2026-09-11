import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Descriptions,
  Drawer,
  Empty,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import type { Dayjs } from "dayjs";
import {
  Activity,
  Database,
  Eye,
  Heart,
  RefreshCw,
  ThumbsUp,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { usePageScopeContext } from "../app/pageScope";
import { PageHeader } from "../components/PageHeader";
import {
  getSqliteStatus,
  loadConfig,
  queryProfileStatsDetail,
  queryProfileStatsHistory,
  queryProfileStatsLatest,
  queryProfileStatsSummary,
} from "../services/api";
import type {
  Account,
  Platform,
  ProfileStatsFilter,
  ProfileStatsSnapshot,
  ProfileStatsSummary,
  SqliteStatus,
} from "../services/types";

const { RangePicker } = DatePicker;

type TimeRange = [Dayjs, Dayjs] | null;
type ProfileStatsStatusFilter =
  | "all"
  | "success"
  | "partial_success"
  | "failed"
  | "uncollected";

interface FilterState {
  accountId?: string;
  status: ProfileStatsStatusFilter;
  timeRange: TimeRange;
}

interface LatestProfileRow {
  accountId: string;
  platform: Platform;
  enabled?: boolean;
  configured: boolean;
  snapshot?: ProfileStatsSnapshot;
}

interface ActivityMatchRow {
  key: string;
  action?: string;
  text?: string;
}

const DEFAULT_FILTERS: FilterState = {
  status: "all",
  timeRange: null,
};

const EMPTY_SUMMARY: ProfileStatsSummary = {
  accountCount: 0,
  collectedAccountCount: 0,
  recent24hCount: 0,
  successCount: 0,
  partialSuccessCount: 0,
  failedCount: 0,
  commentEvidenceAccountCount: 0,
  totalFollowing: 0,
  totalFollowers: 0,
  totalLikes: 0,
  totalLiked: 0,
};

export function ProfileStatsPage() {
  const pageScope = usePageScopeContext();
  const currentPlatform =
    pageScope.platformFilter === "all" ? "tiktok" : pageScope.platformFilter;
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [sqliteStatus, setSqliteStatus] = useState<SqliteStatus | null>(null);
  const [latestSnapshots, setLatestSnapshots] = useState<
    ProfileStatsSnapshot[]
  >([]);
  const [historySnapshots, setHistorySnapshots] = useState<
    ProfileStatsSnapshot[]
  >([]);
  const [summary, setSummary] = useState<ProfileStatsSummary>(EMPTY_SUMMARY);
  const [loading, setLoading] = useState(true);
  const [detailSnapshot, setDetailSnapshot] =
    useState<ProfileStatsSnapshot | null>(null);

  const platformAccounts = useMemo(
    () => accounts.filter((account) => account.platform === currentPlatform),
    [accounts, currentPlatform],
  );
  const accountOptions = useMemo(
    () =>
      platformAccounts.map((account) => ({
        value: account.id,
        label: `${account.id}${account.enabled ? "" : "（停用）"}`,
      })),
    [platformAccounts],
  );
  const latestRows = useMemo(
    () =>
      buildLatestRows(
        platformAccounts,
        latestSnapshots,
        currentPlatform,
        filters,
      ),
    [currentPlatform, filters, latestSnapshots, platformAccounts],
  );
  const displayedHistory = useMemo(
    () =>
      historySnapshots.filter((snapshot) =>
        snapshotMatchesStatus(snapshot, filters.status),
      ),
    [filters.status, historySnapshots],
  );
  const detailHistory = useMemo(
    () =>
      detailSnapshot
        ? historySnapshots.filter(
            (snapshot) => snapshot.accountId === detailSnapshot.accountId,
          )
        : [],
    [detailSnapshot, historySnapshots],
  );

  const refresh = async (sourceFilters = filters) => {
    setLoading(true);
    try {
      const queryFilter = toProfileStatsFilter(currentPlatform, sourceFilters);
      const [config, sqlite, latest, history, nextSummary] = await Promise.all([
        loadConfig(),
        getSqliteStatus(),
        queryProfileStatsLatest({ ...queryFilter, limit: 10000 }),
        sourceFilters.status === "uncollected"
          ? Promise.resolve([])
          : queryProfileStatsHistory({
              ...queryFilter,
              status: toBackendHistoryStatus(sourceFilters.status),
              limit: 500,
            }),
        queryProfileStatsSummary({ platform: currentPlatform }),
      ]);
      setAccounts(config.accounts);
      setSqliteStatus(sqlite);
      setLatestSnapshots(latest);
      setHistorySnapshots(history);
      setSummary(nextSummary);
    } catch (error) {
      message.error(formatError(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh(DEFAULT_FILTERS);
  }, [currentPlatform]);

  const updateFilter = <K extends keyof FilterState>(
    key: K,
    value: FilterState[K],
  ) => {
    setFilters((current) => ({
      ...current,
      [key]: value,
    }));
  };

  const resetFilters = () => {
    setFilters(DEFAULT_FILTERS);
    void refresh(DEFAULT_FILTERS);
  };

  const openDetail = useCallback(async (snapshot: ProfileStatsSnapshot) => {
    setDetailSnapshot(snapshot);
    try {
      const detail = await queryProfileStatsDetail({ id: snapshot.id });
      if (detail) {
        setDetailSnapshot(detail);
      }
    } catch (error) {
      message.warning(`未能读取采集详情：${formatError(error)}`);
    }
  }, []);

  const latestColumns = useMemo(
    () => buildLatestColumns((snapshot) => void openDetail(snapshot)),
    [openDetail],
  );

  const storeStatus = getProfileStoreStatus(sqliteStatus);
  const accountCount = platformAccounts.length || summary.accountCount;

  return (
    <>
      <PageHeader
        title="账号数据"
        description="只读展示 TikTok 养号任务完成后自动采集的账号快照。"
        extra={
          <Space>
            <Button onClick={resetFilters}>清空筛选</Button>
            <Button
              type="primary"
              icon={<RefreshCw size={16} />}
              loading={loading}
              onClick={() => void refresh()}
            >
              查询
            </Button>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col span={24}>
          {sqliteStatus && !sqliteStatus.exists ? (
            <Alert
              showIcon
              type="info"
              message="账号数据记录库尚未初始化"
              description="首次完成 TikTok 养号任务后会自动生成采集快照；当前暂无数据。"
              style={{ marginBottom: 16 }}
            />
          ) : null}
          {sqliteStatus?.exists && !sqliteStatus.profileStatsSnapshots ? (
            <Alert
              showIcon
              type="info"
              message="账号数据快照表尚未创建"
              description="完成一次新版 TikTok 养号任务后会自动创建并写入快照。"
              style={{ marginBottom: 16 }}
            />
          ) : null}
          <Alert
            showIcon
            type="info"
            message="未观察到评论获赞通知不代表评论失败。"
            style={{ marginBottom: 16 }}
          />
          <Card>
            <Space direction="vertical" size={14} className="full-width">
              <Space wrap size={12}>
                <Select
                  allowClear
                  showSearch
                  placeholder="账号"
                  value={filters.accountId}
                  options={accountOptions}
                  style={{ width: 220 }}
                  onChange={(value) => updateFilter("accountId", value)}
                />
                <Select
                  value={filters.status}
                  options={[
                    { value: "all", label: "全部状态" },
                    { value: "success", label: "采集成功" },
                    { value: "partial_success", label: "部分成功" },
                    { value: "failed", label: "采集失败" },
                    { value: "uncollected", label: "未采集" },
                  ]}
                  style={{ width: 150 }}
                  onChange={(value) =>
                    updateFilter("status", value as ProfileStatsStatusFilter)
                  }
                />
                <RangePicker
                  showTime
                  value={filters.timeRange}
                  onChange={(value) =>
                    updateFilter("timeRange", value as TimeRange)
                  }
                />
              </Space>
              <Space size={8}>
                <Database size={15} />
                <Typography.Text type="secondary">数据源</Typography.Text>
                <Typography.Text>本机采集快照库</Typography.Text>
                <Tag color={storeStatus.color}>{storeStatus.label}</Tag>
              </Space>
            </Space>
          </Card>
        </Col>

        <Col span={24}>
          <Row gutter={[16, 16]}>
            <SummaryCard
              title="TikTok 账号总数"
              value={accountCount}
              icon={<Users size={18} />}
            />
            <SummaryCard
              title="已采集账号"
              value={summary.collectedAccountCount}
              icon={<Database size={18} />}
            />
            <SummaryCard
              title="最近 24 小时采集"
              value={summary.recent24hCount}
              icon={<Activity size={18} />}
            />
            <SummaryCard
              title="采集成功"
              value={summary.successCount}
              icon={<ThumbsUp size={18} />}
            />
            <SummaryCard
              title="部分成功"
              value={summary.partialSuccessCount}
              icon={<Activity size={18} />}
            />
            <SummaryCard
              title="采集失败"
              value={summary.failedCount}
              icon={<Activity size={18} />}
            />
            <SummaryCard
              title="评论获赞证据"
              value={summary.commentEvidenceAccountCount}
              icon={<Heart size={18} />}
            />
            <SummaryCard
              title="总关注"
              value={summary.totalFollowing}
              icon={<Users size={18} />}
            />
            <SummaryCard
              title="总粉丝"
              value={summary.totalFollowers}
              icon={<Users size={18} />}
            />
            <SummaryCard
              title="总获赞"
              value={summary.totalLikes}
              icon={<ThumbsUp size={18} />}
            />
            <SummaryCard
              title="总点赞"
              value={summary.totalLiked}
              icon={<Heart size={18} />}
            />
          </Row>
        </Col>

        <Col span={24}>
          <Card title="最新数据">
            <Table
              rowKey="accountId"
              loading={loading}
              columns={latestColumns}
              dataSource={latestRows}
              locale={{
                emptyText: (
                  <Empty description="暂无账号数据。完成 TikTok 养号任务后会自动采集。" />
                ),
              }}
              pagination={{
                defaultPageSize: 12,
                showSizeChanger: true,
                pageSizeOptions: [10, 12, 20, 50, 100],
              }}
              scroll={{ x: 1280 }}
            />
          </Card>
        </Col>

        <Col span={24}>
          <Card title="历史记录">
            <Table
              rowKey="id"
              loading={loading}
              columns={historyColumns}
              dataSource={displayedHistory}
              locale={{
                emptyText: (
                  <Empty description="暂无历史快照。每次正常养号任务完成后会写入一条记录。" />
                ),
              }}
              pagination={{
                defaultPageSize: 12,
                showSizeChanger: true,
                pageSizeOptions: [10, 12, 20, 50, 100],
              }}
              scroll={{ x: 1260 }}
            />
          </Card>
        </Col>
      </Row>

      <ProfileStatsDetailDrawer
        snapshot={detailSnapshot}
        history={detailHistory}
        onClose={() => setDetailSnapshot(null)}
      />
    </>
  );
}

function SummaryCard({
  title,
  value,
  icon,
}: {
  title: string;
  value: number;
  icon: ReactNode;
}) {
  return (
    <Col xs={24} sm={12} lg={8} xl={6}>
      <Card>
        <Space
          align="start"
          className="full-width"
          style={{ justifyContent: "space-between" }}
        >
          <Statistic title={title} value={value} />
          {icon}
        </Space>
      </Card>
    </Col>
  );
}

function ProfileStatsDetailDrawer({
  snapshot,
  history,
  onClose,
}: {
  snapshot: ProfileStatsSnapshot | null;
  history: ProfileStatsSnapshot[];
  onClose(): void;
}) {
  const matches = useMemo(
    () => parseActivityMatches(snapshot?.activityMatchesJson),
    [snapshot?.activityMatchesJson],
  );

  return (
    <Drawer
      width={760}
      title={snapshot ? `${snapshot.accountId} 采集详情` : "采集详情"}
      open={Boolean(snapshot)}
      onClose={onClose}
    >
      {snapshot ? (
        <Space direction="vertical" size={16} className="full-width">
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="账号">
              {snapshot.accountId}
            </Descriptions.Item>
            <Descriptions.Item label="主页名">
              {snapshot.handle ? `@${snapshot.handle}` : "-"}
            </Descriptions.Item>
            <Descriptions.Item label="关注数">
              {formatNumber(snapshot.following)}
            </Descriptions.Item>
            <Descriptions.Item label="粉丝数">
              {formatNumber(snapshot.followers)}
            </Descriptions.Item>
            <Descriptions.Item label="主页获赞">
              {formatNumber(snapshot.likes)}
            </Descriptions.Item>
            <Descriptions.Item label="点赞视频">
              {formatNumber(snapshot.liked)}
            </Descriptions.Item>
            <Descriptions.Item label="已点赞加载">
              {formatLikedCompleteness(snapshot)}
            </Descriptions.Item>
            <Descriptions.Item label="评论获赞证据">
              {formatCommentEvidence(snapshot)}
            </Descriptions.Item>
            <Descriptions.Item label="通知状态">
              {snapshot.activityStatus ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="通知范围">
              {snapshot.activityScope ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="采集状态">
              {formatCollectionStatus(snapshot.status, snapshot.error)}
            </Descriptions.Item>
            <Descriptions.Item label="采集时间">
              {formatDateTime(snapshot.collectedAt)}
            </Descriptions.Item>
            <Descriptions.Item label="关联任务" span={2}>
              {snapshot.taskRunId ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="失败原因" span={2}>
              {snapshot.error ?? "-"}
            </Descriptions.Item>
          </Descriptions>

          <Card size="small" title="评论获赞通知证据">
            <Table
              size="small"
              rowKey="key"
              columns={activityMatchColumns}
              dataSource={matches}
              pagination={false}
              locale={{
                emptyText: (
                  <Empty description="未观察到评论获赞通知；这不代表评论失败。" />
                ),
              }}
            />
          </Card>

          <Card size="small" title="该账号历史快照">
            <Table
              size="small"
              rowKey="id"
              columns={historyColumns}
              dataSource={history}
              pagination={{ pageSize: 6 }}
              scroll={{ x: 1260 }}
            />
          </Card>
        </Space>
      ) : null}
    </Drawer>
  );
}

function buildLatestColumns(
  onView: (snapshot: ProfileStatsSnapshot) => void,
): ColumnsType<LatestProfileRow> {
  return [
    {
      title: "账号",
      dataIndex: "accountId",
      width: 160,
      fixed: "left",
      render: (accountId: string, row) => (
        <Space size={6}>
          <Typography.Text strong>{accountId}</Typography.Text>
          {row.configured && row.enabled === false ? <Tag>停用</Tag> : null}
        </Space>
      ),
    },
    {
      title: "主页名",
      width: 150,
      render: (_, row) =>
        row.snapshot?.handle ? `@${row.snapshot.handle}` : "-",
    },
    {
      title: "关注数",
      width: 110,
      render: (_, row) => formatNumber(row.snapshot?.following),
    },
    {
      title: "粉丝数",
      width: 110,
      render: (_, row) => formatNumber(row.snapshot?.followers),
    },
    {
      title: "主页获赞",
      width: 100,
      render: (_, row) => formatNumber(row.snapshot?.likes),
    },
    {
      title: "点赞视频",
      width: 100,
      render: (_, row) => formatNumber(row.snapshot?.liked),
    },
    {
      title: "评论获赞证据",
      width: 140,
      render: (_, row) =>
        row.snapshot ? formatCommentEvidence(row.snapshot) : "-",
    },
    {
      title: "已点赞完整性",
      width: 130,
      render: (_, row) =>
        row.snapshot ? formatLikedCompleteness(row.snapshot) : "-",
    },
    {
      title: "通知状态",
      width: 150,
      render: (_, row) => row.snapshot?.activityStatus ?? "-",
    },
    {
      title: "采集状态",
      width: 130,
      render: (_, row) =>
        row.snapshot ? (
          formatCollectionStatus(row.snapshot.status, row.snapshot.error)
        ) : (
          <Tag>未采集</Tag>
        ),
    },
    {
      title: "最近采集时间",
      width: 180,
      render: (_, row) => formatDateTime(row.snapshot?.collectedAt),
    },
    {
      title: "失败原因",
      width: 220,
      render: (_, row) => row.snapshot?.error ?? "-",
    },
    {
      title: "关联任务",
      width: 180,
      render: (_, row) => row.snapshot?.taskRunId ?? "-",
    },
    {
      title: "操作",
      fixed: "right",
      width: 132,
      align: "center",
      render: (_, row) => (
        <div style={{ padding: "0 8px" }}>
          <Button
            size="small"
            icon={<Eye size={14} />}
            disabled={!row.snapshot}
            style={{ minWidth: 92 }}
            onClick={() => row.snapshot && onView(row.snapshot)}
          >
            查看详情
          </Button>
        </div>
      ),
    },
  ];
}

const historyColumns: ColumnsType<ProfileStatsSnapshot> = [
  { title: "账号", dataIndex: "accountId", width: 150, fixed: "left" },
  {
    title: "主页名",
    width: 150,
    render: (_, row) => (row.handle ? `@${row.handle}` : "-"),
  },
  {
    title: "粉丝数",
    width: 110,
    render: (_, row) => formatNumber(row.followers),
  },
  {
    title: "主页获赞",
    width: 100,
    render: (_, row) => formatNumber(row.likes),
  },
  {
    title: "点赞视频",
    width: 100,
    render: (_, row) => formatNumber(row.liked),
  },
  {
    title: "评论获赞证据",
    width: 140,
    render: (_, row) => formatCommentEvidence(row),
  },
  {
    title: "已点赞完整性",
    width: 130,
    render: (_, row) => formatLikedCompleteness(row),
  },
  {
    title: "采集状态",
    width: 130,
    render: (_, row) => formatCollectionStatus(row.status, row.error),
  },
  {
    title: "采集时间",
    width: 180,
    render: (_, row) => formatDateTime(row.collectedAt),
  },
  {
    title: "关联任务",
    dataIndex: "taskRunId",
    width: 180,
    render: (value) => value ?? "-",
  },
  {
    title: "失败原因",
    dataIndex: "error",
    width: 220,
    render: (value) => value ?? "-",
  },
];

const activityMatchColumns: ColumnsType<ActivityMatchRow> = [
  {
    title: "动作",
    dataIndex: "action",
    width: 220,
    render: (value) => value ?? "-",
  },
  {
    title: "通知文本",
    dataIndex: "text",
    render: (value) => value ?? "-",
  },
];

function buildLatestRows(
  accounts: Account[],
  snapshots: ProfileStatsSnapshot[],
  platform: Platform,
  filters: FilterState,
) {
  const snapshotsByAccount = new Map(
    snapshots.map((snapshot) => [snapshot.accountId, snapshot]),
  );
  const rows: LatestProfileRow[] = accounts.map((account) => ({
    accountId: account.id,
    platform: account.platform,
    enabled: account.enabled,
    configured: true,
    snapshot: snapshotsByAccount.get(account.id),
  }));

  for (const snapshot of snapshots) {
    if (!rows.some((row) => row.accountId === snapshot.accountId)) {
      rows.push({
        accountId: snapshot.accountId,
        platform,
        configured: false,
        snapshot,
      });
    }
  }

  return rows
    .filter((row) => !filters.accountId || row.accountId === filters.accountId)
    .filter((row) => {
      if (filters.status === "all") return true;
      if (filters.status === "uncollected") return !row.snapshot;
      return row.snapshot
        ? snapshotMatchesStatus(row.snapshot, filters.status)
        : false;
    })
    .sort((left, right) => {
      const leftTs = left.snapshot?.collectedAt ?? "";
      const rightTs = right.snapshot?.collectedAt ?? "";
      return (
        rightTs.localeCompare(leftTs) ||
        left.accountId.localeCompare(right.accountId)
      );
    });
}

function snapshotMatchesStatus(
  snapshot: ProfileStatsSnapshot,
  status: ProfileStatsStatusFilter,
) {
  if (status === "all") return true;
  if (status === "uncollected") return false;
  if (status === "partial_success") {
    return (
      snapshot.status === "partial_success" || snapshot.status === "partial"
    );
  }
  if (status === "failed") {
    return snapshot.status === "failed" || snapshot.status === "error";
  }
  return snapshot.status === status;
}

function toProfileStatsFilter(
  platform: Platform,
  filters: FilterState,
): ProfileStatsFilter {
  return {
    platform,
    accountId: filters.accountId,
    startTs: filters.timeRange?.[0]?.toISOString(),
    endTs: filters.timeRange?.[1]?.toISOString(),
  };
}

function toBackendHistoryStatus(status: ProfileStatsStatusFilter) {
  if (status === "success" || status === "failed") {
    return status;
  }
  return undefined;
}

function formatNumber(value?: number) {
  return value === undefined || value === null ? "-" : value.toLocaleString();
}

function formatDateTime(value?: string) {
  if (!value) return "-";
  const ts = Date.parse(value);
  if (Number.isNaN(ts)) return value;
  return new Date(ts).toLocaleString();
}

function formatCollectionStatus(status: string, error?: string) {
  if (status === "success") {
    return <Tag color="green">成功</Tag>;
  }
  if (status === "partial_success" || status === "partial") {
    return <Tag color="gold">部分成功</Tag>;
  }
  if (status === "failed" || status === "error") {
    return <Tag color="red">失败</Tag>;
  }
  return <Tag>{status || "未知"}</Tag>;
}

function formatLikedCompleteness(snapshot: ProfileStatsSnapshot) {
  if (snapshot.likedComplete === true) {
    return <Tag color="green">完整</Tag>;
  }
  if (snapshot.likedComplete === false) {
    return <Tag color="gold">不完整</Tag>;
  }
  return <Tag>未知</Tag>;
}

function formatCommentEvidence(snapshot: ProfileStatsSnapshot) {
  if (
    snapshot.commentPublishEvidence === "observed" ||
    snapshot.activityHasLikedYourComment
  ) {
    return <Tag color="green">有证据</Tag>;
  }
  return <Tag>未观察到</Tag>;
}

function parseActivityMatches(value?: string): ActivityMatchRow[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed)) return [];
    return parsed.map((item, index) => ({
      key: String(index),
      action: typeof item?.action === "string" ? item.action : undefined,
      text: typeof item?.text === "string" ? item.text : undefined,
    }));
  } catch {
    return [];
  }
}

function getProfileStoreStatus(status: SqliteStatus | null) {
  if (!status) {
    return { label: "检查中", color: "default" };
  }
  if (!status.exists) {
    return { label: "未初始化", color: "default" };
  }
  if (!status.profileStatsSnapshots) {
    return { label: "未创建快照表", color: "gold" };
  }
  return { label: "可用", color: "green" };
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
