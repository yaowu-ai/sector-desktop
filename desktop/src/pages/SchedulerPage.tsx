import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Form,
  InputNumber,
  Modal,
  Row,
  Segmented,
  Space,
  Statistic,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import {
  CalendarClock,
  PauseCircle,
  Play,
  RefreshCw,
  Save,
  TimerReset,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { confirmDanger } from "../components/ConfirmDanger";
import { PageHeader } from "../components/PageHeader";
import { StatusTag } from "../components/StatusTag";
import { useDesktopAuth } from "../app/DesktopAuthContext";
import { usePlatformContext } from "../app/PlatformContext";
import {
  checkBitbrowserApi,
  clearRunLock,
  getSchedulerHealth,
  getSchedulerProcessStatus,
  loadConfig,
  querySchedulerJobRuns,
  saveSchedulerSettings,
  startScheduler,
  stopScheduler,
} from "../services/api";
import { readDesktopLicenseLimits } from "../services/desktopApi";
import {
  getAutomaticExecutionDisabledReason,
  getPlatformLabel,
  isExecutablePlatform,
} from "../services/platforms";
import type {
  Account,
  ApiStatus,
  IpGroupConflict,
  Platform,
  SchedulerAccountSettings,
  SchedulerHealth,
  SchedulerJob,
  SchedulerJobRunRecord,
  SchedulerProcessStatus,
} from "../services/types";

interface SchedulerRow {
  id: string;
  enabled: boolean;
  scheduled: boolean;
  platform: Platform;
  ipGroup?: number;
  activeHours: [number, number][];
  notes?: string;
}

interface ActiveHoursFormValues {
  activeHours: Array<{ start?: number; end?: number }>;
}

type RunHistoryRange = 1 | 3;

const EMPTY_HEALTH: SchedulerHealth = {
  status: "stopped",
  jobs: [],
  todayScheduleCount: 0,
  firesPerDay: 3,
  runLock: {
    path: "data/run.lock",
    exists: false,
    active: false,
  },
  ipGroupConflicts: [],
};

const EMPTY_PROCESS: SchedulerProcessStatus = {
  status: "stopped",
  command: ["py", "-3.13", "src/scheduler.py"],
  healthUrl: "http://127.0.0.1:9601/health",
};

export function SchedulerPage() {
  const { currentPlatform } = usePlatformContext();
  const { license } = useDesktopAuth();
  const licenseLimits = readDesktopLicenseLimits(license);
  const [form] = Form.useForm<ActiveHoursFormValues>();
  const [bitbrowser, setBitbrowser] = useState<ApiStatus | null>(null);
  const [health, setHealth] = useState<SchedulerHealth>(EMPTY_HEALTH);
  const [processStatus, setProcessStatus] =
    useState<SchedulerProcessStatus>(EMPTY_PROCESS);
  const [rows, setRows] = useState<SchedulerRow[]>([]);
  const [runHistory, setRunHistory] = useState<SchedulerJobRunRecord[]>([]);
  const [runHistoryDays, setRunHistoryDays] = useState<RunHistoryRange>(1);
  const [firesPerDay, setFiresPerDay] = useState(3);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingRow, setEditingRow] = useState<SchedulerRow | null>(null);

  const schedulableRows = useMemo(
    () =>
      rows.filter(
        (row) =>
          row.enabled && row.scheduled && isExecutablePlatform(row.platform),
      ),
    [rows],
  );
  const schedulerStartDisabledReason =
    processStatus.status === "running"
      ? "调度服务已在运行"
      : schedulerDisabledReason(licenseLimits.scheduler, currentPlatform);
  const rowAccountIds = useMemo(
    () => new Set(rows.map((row) => row.id)),
    [rows],
  );
  const scopedJobs = useMemo(
    () =>
      health.jobs.filter(
        (job) => !job.accountId || rowAccountIds.has(job.accountId),
      ),
    [health.jobs, rowAccountIds],
  );
  const nextScopedJob = useMemo(
    () => scopedJobs.find((job) => job.accountId && job.nextRun),
    [scopedJobs],
  );
  const scopedConflicts = useMemo(
    () =>
      health.ipGroupConflicts.filter(
        (conflict) =>
          rowAccountIds.has(conflict.leftAccountId) ||
          rowAccountIds.has(conflict.rightAccountId),
      ),
    [health.ipGroupConflicts, rowAccountIds],
  );
  const scopedRunHistory = useMemo(
    () => runHistory.filter((record) => rowAccountIds.has(record.accountId)),
    [rowAccountIds, runHistory],
  );
  const todayRunHistory = useMemo(
    () =>
      scopedRunHistory.filter((record) =>
        isToday(record.startedAt ?? record.scheduledRun),
      ),
    [scopedRunHistory],
  );
  const todayPendingJobs = useMemo(
    () => scopedJobs.filter((job) => isToday(job.nextRun)),
    [scopedJobs],
  );
  const todayTaskTotal = useMemo(
    () =>
      new Set([
        ...todayRunHistory.map((record) => record.jobId),
        ...todayPendingJobs.map((job) => job.id),
      ]).size,
    [todayPendingJobs, todayRunHistory],
  );

  const refresh = useCallback(
    async (options: { showLoading?: boolean } = {}) => {
      const showLoading = options.showLoading ?? false;
      if (showLoading) {
        setLoading(true);
      } else {
        setRefreshing(true);
      }
      try {
        const historyStartTs = dayjs()
          .subtract(runHistoryDays, "day")
          .format("YYYY-MM-DDTHH:mm:ss");
        const [
          snapshot,
          nextProcess,
          nextHealth,
          nextBitbrowser,
          nextRunHistory,
        ] = await Promise.all([
          loadConfig(),
          getSchedulerProcessStatus(),
          getSchedulerHealth(),
          checkBitbrowserApi(),
          querySchedulerJobRuns({
            platform: currentPlatform,
            startTs: historyStartTs,
            limit: 120,
          }),
        ]);
        setRows(
          snapshot.accounts
            .filter((account) => account.platform === currentPlatform)
            .map(accountToRow),
        );
        setRunHistory(nextRunHistory);
        setFiresPerDay(
          snapshot.schedulerSettings?.firesPerDay ??
            nextHealth.firesPerDay ??
            3,
        );
        setProcessStatus(nextProcess);
        setHealth(nextHealth);
        setBitbrowser(nextBitbrowser);
      } catch (error) {
        message.error(formatError(error));
      } finally {
        if (showLoading) {
          setLoading(false);
        } else {
          setRefreshing(false);
        }
      }
    },
    [currentPlatform, runHistoryDays],
  );

  useEffect(() => {
    void refresh({ showLoading: true });
    const timer = window.setInterval(() => {
      void refresh();
    }, 10000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const start = async () => {
    const disabledReason = schedulerDisabledReason(licenseLimits.scheduler, currentPlatform);
    if (disabledReason) {
      message.warning(disabledReason);
      return;
    }
    setStarting(true);
    try {
      const result = await startScheduler();
      message.success(`调度服务已启动，PID ${result.processId}`);
      await refresh();
    } catch (error) {
      message.error(formatError(error));
    } finally {
      setStarting(false);
    }
  };

  const confirmStop = () => {
    confirmDanger({
      title: "停止调度服务",
      content:
        "停止 scheduler.py 只会停止后续排期，不等于立刻停止已经触发的账号任务。",
      onOk: () => {
        void stop();
      },
    });
  };

  const confirmClearRunLock = () => {
    confirmDanger({
      title: "清理任务锁",
      content:
        "将清理本机任务锁。仅当确认没有养号脚本正在运行时执行；活跃任务锁会被后端拒绝。",
      onOk: () => {
        void clearLock();
      },
    });
  };

  const clearLock = async () => {
    try {
      const result = await clearRunLock();
      message.success(result.message);
      await refresh();
    } catch (error) {
      message.error(formatError(error));
    }
  };

  const stop = async () => {
    setStopping(true);
    try {
      const result = await stopScheduler();
      message.success(result.message);
      await refresh();
    } catch (error) {
      message.error(formatError(error));
    } finally {
      setStopping(false);
    }
  };

  const save = async () => {
    const disabledReason = schedulerDisabledReason(licenseLimits.scheduler, currentPlatform);
    if (disabledReason) {
      message.warning(disabledReason);
      return;
    }
    setSaving(true);
    try {
      await saveSchedulerSettings({
        firesPerDay,
        accounts: rows.map(rowToSchedulerAccount),
      });
      message.success("调度配置已保存到 accounts.yaml");
      await refresh();
    } catch (error) {
      message.error(formatError(error));
    } finally {
      setSaving(false);
    }
  };

  const updateIpGroup = (accountId: string, value: number | null) => {
    setRows((current) =>
      current.map((row) =>
        row.id === accountId
          ? {
              ...row,
              ipGroup: value === null ? undefined : Number(value),
            }
          : row,
      ),
    );
  };

  const updateScheduled = (accountId: string, scheduled: boolean) => {
    setRows((current) =>
      current.map((row) =>
        row.id === accountId
          ? {
              ...row,
              scheduled,
            }
          : row,
      ),
    );
  };

  const openActiveHoursEditor = (row: SchedulerRow) => {
    setEditingRow(row);
    form.setFieldsValue({
      activeHours: row.activeHours.map(([start, end]) => ({ start, end })),
    });
  };

  const saveActiveHours = async () => {
    const values = await form.validateFields();
    if (!editingRow) {
      return;
    }
    const nextActiveHours = values.activeHours.map(
      (range) => [Number(range.start), Number(range.end)] as [number, number],
    );
    setRows((current) =>
      current.map((row) =>
        row.id === editingRow.id
          ? {
              ...row,
              activeHours: nextActiveHours,
            }
          : row,
      ),
    );
    setEditingRow(null);
  };

  return (
    <>
      <PageHeader
        title="调度计划"
        description="按平台和账号活跃时段生成本机时间排期；当前只调度已适配自动执行的平台。"
        extra={
          <Space>
            <Button
              icon={<RefreshCw size={16} />}
              loading={loading || refreshing}
              onClick={() => void refresh({ showLoading: true })}
            >
              刷新
            </Button>
            <Button
              icon={<PauseCircle size={16} />}
              danger
              loading={stopping}
              disabled={processStatus.status !== "running" && !health.processId}
              onClick={confirmStop}
            >
              停止调度
            </Button>
            <Tooltip title={schedulerStartDisabledReason}>
              <span>
                <Button
                  type="primary"
                  icon={<Play size={16} />}
                  loading={starting}
                  disabled={Boolean(schedulerStartDisabledReason)}
                  onClick={() => void start()}
                >
                  启动调度
                </Button>
              </span>
            </Tooltip>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Alert
            showIcon
            type="info"
            message="V1 调度使用运行机器本地时间"
            description="保存账号或调度配置后，调度器会在约 10 秒内自动重建剩余排期；如果检测到旧版本或配置路径不一致的调度进程，请先停止后重新启动。"
          />
        </Col>

        <Col xs={24} md={8} xl={4}>
          <Card>
            <Space direction="vertical" size={8}>
              <Typography.Text type="secondary">调度服务</Typography.Text>
              <SchedulerStatusTag status={health.status} />
              <Typography.Text type="secondary">
                PID {health.processId ?? processStatus.processId ?? "-"}
              </Typography.Text>
            </Space>
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Space direction="vertical" size={8}>
              <Typography.Text type="secondary">BitBrowser API</Typography.Text>
              <StatusTag
                status={bitbrowser?.available ? "ok" : "error"}
                label={bitbrowser?.available ? "可用" : "不可用"}
              />
              <Typography.Text
                type="secondary"
                ellipsis
                style={{ maxWidth: 180 }}
              >
                {bitbrowser?.apiUrl ?? "-"}
              </Typography.Text>
            </Space>
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Statistic
              title="今日任务"
              value={todayRunHistory.length}
              suffix={`/ ${todayTaskTotal}`}
              prefix={<CalendarClock size={16} />}
            />
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Statistic
              title="每日触发次数"
              value={firesPerDay}
              prefix={<TimerReset size={16} />}
            />
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Statistic
              title="下一账号"
              value={nextScopedJob?.accountId ?? "-"}
            />
          </Card>
        </Col>
        <Col xs={24} md={8} xl={4}>
          <Card>
            <Statistic
              title="任务锁"
              value={
                health.runLock.active
                  ? "活跃"
                  : health.runLock.exists
                    ? "存在"
                    : "无"
              }
            />
          </Card>
        </Col>

        <Col span={24}>
          <Card>
            <Space direction="vertical" size={12} className="full-width">
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
                  border: "1px solid #f0f0f0",
                  borderRadius: 6,
                  overflow: "hidden",
                }}
              >
                <ScheduleSummaryItem
                  label="下次执行"
                  value={formatScheduleTime(nextScopedJob?.nextRun)}
                />
                <ScheduleSummaryItem
                  label="调度状态"
                  value={formatSchedulerStatusText(health.status)}
                />
                <ScheduleSummaryItem
                  label="服务状态"
                  value={formatServiceStatus(health, processStatus)}
                />
                <ScheduleSummaryItem
                  label="排班检查"
                  value={formatConflictSummary(scopedConflicts)}
                />
              </div>
              {health.error ? (
                <Alert
                  type="warning"
                  showIcon
                  message={formatSchedulerHealthError(health.error)}
                />
              ) : null}
              {health.runLock.exists ? (
                <Alert
                  type={health.runLock.active ? "warning" : "info"}
                  showIcon
                  message={`任务锁${health.runLock.active ? "正在被运行任务占用" : "存在但任务已不活跃"}`}
                  description={
                    health.runLock.pid ? `PID ${health.runLock.pid}` : undefined
                  }
                  action={
                    <Button
                      size="small"
                      danger
                      icon={<Trash2 size={14} />}
                      onClick={confirmClearRunLock}
                    >
                      清理
                    </Button>
                  }
                />
              ) : null}
              <ConflictAlert conflicts={scopedConflicts} />
            </Space>
          </Card>
        </Col>

        <Col xs={24} xl={10}>
          <Card
            title="调度配置"
            extra={
              <Button
                type="primary"
                icon={<Save size={16} />}
                loading={saving}
                disabled={Boolean(schedulerDisabledReason(licenseLimits.scheduler, currentPlatform))}
                onClick={() => void save()}
              >
                保存配置
              </Button>
            }
          >
            <Space direction="vertical" size={16} className="full-width">
              <Space>
                <Typography.Text>每账号每日触发次数</Typography.Text>
                <InputNumber
                  min={0}
                  max={24}
                  precision={0}
                  value={firesPerDay}
                  onChange={(value) => setFiresPerDay(Number(value ?? 0))}
                />
              </Space>
              <Typography.Text type="secondary">
                今日任务 = 已运行 {todayRunHistory.length} / 总任务{" "}
                {todayTaskTotal}；当前配置预计 {schedulableRows.length} ×
                每日触发次数 {firesPerDay}。
              </Typography.Text>
            </Space>
          </Card>
        </Col>

        <Col xs={24} xl={14}>
          <Card title={`当前调度任务 ${scopedJobs.length}`}>
            <Table
              rowKey="id"
              loading={loading}
              columns={jobColumns}
              dataSource={scopedJobs}
              pagination={{ pageSize: 6 }}
              scroll={{ x: 680 }}
            />
          </Card>
        </Col>

        <Col span={24}>
          <section>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                marginBottom: 12,
              }}
            >
              <Space direction="vertical" size={2}>
                <Typography.Title level={4} style={{ margin: 0 }}>
                  已运行任务 {scopedRunHistory.length}
                </Typography.Title>
                <Typography.Text type="secondary">
                  一次调度任务显示一条，按当前平台和账号范围展示。
                </Typography.Text>
              </Space>
              <Segmented
                value={runHistoryDays}
                options={[
                  { label: "最近 1 天", value: 1 },
                  { label: "最近 3 天", value: 3 },
                ]}
                onChange={(value) =>
                  setRunHistoryDays(value as RunHistoryRange)
                }
              />
            </div>
            <Table
              rowKey="jobId"
              loading={loading}
              columns={runHistoryColumns}
              dataSource={scopedRunHistory}
              pagination={{ pageSize: 7, showSizeChanger: true }}
              scroll={{ x: 1180 }}
              locale={{
                emptyText: (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description={`最近 ${runHistoryDays} 天暂无已运行任务`}
                  />
                ),
              }}
            />
          </section>
        </Col>

        <Col span={24}>
          <Card title="账号班次与 IP 分组">
            <Table
              rowKey="id"
              loading={loading}
              columns={accountColumns(
                updateIpGroup,
                updateScheduled,
                openActiveHoursEditor,
              )}
              dataSource={rows}
              pagination={{ pageSize: 12, showSizeChanger: true }}
              scroll={{ x: 1100 }}
            />
          </Card>
        </Col>
      </Row>

      <Modal
        title={editingRow ? `编辑 ${editingRow.id} 班次` : "编辑班次"}
        open={Boolean(editingRow)}
        okText="应用"
        cancelText="取消"
        onOk={() => void saveActiveHours()}
        onCancel={() => setEditingRow(null)}
      >
        <Form form={form} layout="vertical" requiredMark={false}>
          <Form.List name="activeHours">
            {(fields, { add, remove }) => (
              <Space direction="vertical" className="full-width">
                {fields.map((field) => (
                  <Space key={field.key} align="baseline">
                    <Form.Item
                      {...field}
                      name={[field.name, "start"]}
                      rules={[{ required: true, message: "开始小时必填" }]}
                    >
                      <InputNumber
                        min={0}
                        max={24}
                        step={0.5}
                        placeholder="开始"
                      />
                    </Form.Item>
                    <Typography.Text>到</Typography.Text>
                    <Form.Item
                      {...field}
                      name={[field.name, "end"]}
                      rules={[
                        { required: true, message: "结束小时必填" },
                        {
                          validator: () => validateActiveHours(form),
                        },
                      ]}
                    >
                      <InputNumber
                        min={0}
                        max={24}
                        step={0.5}
                        placeholder="结束"
                      />
                    </Form.Item>
                    <Button
                      disabled={fields.length <= 1}
                      onClick={() => remove(field.name)}
                    >
                      删除
                    </Button>
                  </Space>
                ))}
                <Button onClick={() => add({ start: 19, end: 23 })}>
                  新增班次
                </Button>
              </Space>
            )}
          </Form.List>
        </Form>
      </Modal>
    </>
  );
}

const jobColumns: ColumnsType<SchedulerJob> = [
  {
    title: "任务 ID",
    dataIndex: "id",
    width: 260,
    render: (value: string) => <Typography.Text code>{value}</Typography.Text>,
  },
  {
    title: "账号",
    dataIndex: "accountId",
    width: 150,
    render: (value?: string) => value ?? "-",
  },
  {
    title: "下次执行",
    dataIndex: "nextRun",
    width: 220,
    render: (value?: string) => formatScheduleTime(value),
  },
  {
    title: "状态",
    dataIndex: "status",
    width: 120,
    render: (value?: string) => (
      <Tag color="blue">{formatSchedulerJobStatus(value)}</Tag>
    ),
  },
];

const runHistoryColumns: ColumnsType<SchedulerJobRunRecord> = [
  {
    title: "任务 ID",
    dataIndex: "jobId",
    width: 280,
    render: (value: string) => <Typography.Text code>{value}</Typography.Text>,
  },
  { title: "账号", dataIndex: "accountId", width: 150 },
  {
    title: "运行开始时间",
    dataIndex: "startedAt",
    width: 190,
    render: (value?: string) => formatScheduleTime(value),
  },
  {
    title: "运行结束时间",
    dataIndex: "endedAt",
    width: 190,
    render: (value?: string) => (value ? formatScheduleTime(value) : "-"),
  },
  {
    title: "运行结果",
    dataIndex: "status",
    width: 130,
    render: (status: SchedulerJobRunRecord["status"]) => (
      <Tag color={schedulerJobRunStatusColor(status)}>
        {formatSchedulerJobRunStatus(status)}
      </Tag>
    ),
  },
  {
    title: "运行详情",
    dataIndex: "detail",
    render: (detail: string, record) => {
      const visibleDetail = shouldShowRunDetail(record.status)
        ? detail || "-"
        : "-";
      return (
        <Typography.Paragraph
          style={{ marginBottom: 0, maxWidth: 460, whiteSpace: "pre-wrap" }}
          ellipsis={{ rows: 2, expandable: true, symbol: "展开" }}
        >
          {visibleDetail}
        </Typography.Paragraph>
      );
    },
  },
];

function formatSchedulerJobRunStatus(status: SchedulerJobRunRecord["status"]) {
  if (status === "pending") {
    return "未运行";
  }
  if (status === "running") {
    return "运行中";
  }
  if (status === "success") {
    return "成功运行";
  }
  if (status === "failed") {
    return "运行失败";
  }
  if (status === "skipped") {
    return "未运行";
  }
  return status || "-";
}

function schedulerDisabledReason(schedulerAllowed: boolean, currentPlatform: Platform) {
  if (!schedulerAllowed) return "当前套餐不支持自动调度";
  if (!isExecutablePlatform(currentPlatform)) {
    return getAutomaticExecutionDisabledReason(currentPlatform, "scheduler");
  }
  return undefined;
}

function schedulerJobRunStatusColor(status: SchedulerJobRunRecord["status"]) {
  if (status === "success") {
    return "green";
  }
  if (status === "failed") {
    return "red";
  }
  if (status === "skipped" || status === "pending") {
    return "gold";
  }
  if (status === "running") {
    return "blue";
  }
  return "default";
}

function formatSchedulerJobStatus(status?: string) {
  if (!status || status === "scheduled") {
    return "已排期";
  }
  if (status === "running") {
    return "运行中";
  }
  if (status === "paused") {
    return "已暂停";
  }
  if (status === "error") {
    return "异常";
  }
  return status;
}

function shouldShowRunDetail(status: SchedulerJobRunRecord["status"]) {
  return status === "pending" || status === "failed" || status === "skipped";
}

function accountColumns(
  onIpGroupChange: (accountId: string, value: number | null) => void,
  onScheduledChange: (accountId: string, scheduled: boolean) => void,
  onEditActiveHours: (row: SchedulerRow) => void,
): ColumnsType<SchedulerRow> {
  return [
    { title: "账号", dataIndex: "id", width: 150 },
    {
      title: "平台",
      dataIndex: "platform",
      width: 110,
      render: (platform: Platform) => (
        <Tag color={isExecutablePlatform(platform) ? "green" : "gold"}>
          {getPlatformLabel(platform)}
        </Tag>
      ),
    },
    {
      title: "启用",
      dataIndex: "enabled",
      width: 90,
      render: (enabled: boolean) => (
        <StatusTag
          status={enabled ? "ok" : "idle"}
          label={enabled ? "启用" : "停用"}
        />
      ),
    },
    {
      title: "参与调度",
      dataIndex: "scheduled",
      width: 120,
      render: (scheduled: boolean, row) => (
        <Switch
          size="small"
          checked={scheduled}
          disabled={!row.enabled || !isExecutablePlatform(row.platform)}
          onChange={(checked) => onScheduledChange(row.id, checked)}
        />
      ),
    },
    {
      title: "IP 分组",
      dataIndex: "ipGroup",
      width: 150,
      render: (value: number | undefined, row) => (
        <InputNumber
          min={0}
          precision={0}
          value={value}
          placeholder="未设置"
          onChange={(nextValue) => onIpGroupChange(row.id, nextValue)}
        />
      ),
    },
    {
      title: "活跃时段",
      dataIndex: "activeHours",
      render: (ranges: [number, number][], row) => (
        <Space wrap>
          {ranges.length
            ? ranges.map(([start, end]) => (
                <Tag key={`${start}-${end}`}>
                  {start}-{end}
                </Tag>
              ))
            : "-"}
          <Button size="small" onClick={() => onEditActiveHours(row)}>
            编辑
          </Button>
        </Space>
      ),
    },
    { title: "备注", dataIndex: "notes", ellipsis: true },
  ];
}

function SchedulerStatusTag({ status }: { status: SchedulerHealth["status"] }) {
  if (status === "running") {
    return <StatusTag status="running" label="运行中" />;
  }
  if (status === "starting") {
    return <StatusTag status="warning" label="启动中" />;
  }
  if (status === "error") {
    return <StatusTag status="error" label="异常" />;
  }
  return <StatusTag status="idle" label="未运行" />;
}

function ScheduleSummaryItem({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "96px minmax(0, 1fr)",
        minHeight: 40,
        borderRight: label === "排班检查" ? 0 : "1px solid #f0f0f0",
      }}
    >
      <div
        style={{
          padding: "8px 12px",
          background: "#fafafa",
          color: "#6b7280",
          whiteSpace: "nowrap",
        }}
      >
        {label}
      </div>
      <div
        style={{
          padding: "8px 12px",
          minWidth: 0,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
        title={value}
      >
        {value}
      </div>
    </div>
  );
}

function ConflictAlert({ conflicts }: { conflicts: IpGroupConflict[] }) {
  if (!conflicts.length) {
    return <Alert type="success" showIcon message="IP 排班正常" />;
  }
  return (
    <Alert
      type="error"
      showIcon
      message={`检测到 ${conflicts.length} 个 IP 排班冲突`}
      description={
        <Space direction="vertical" size={2}>
          {conflicts.slice(0, 6).map((conflict) => (
            <Typography.Text
              key={`${conflict.ipGroup}-${conflict.leftAccountId}-${conflict.rightAccountId}`}
            >
              IP 分组 {conflict.ipGroup}: {conflict.leftAccountId}{" "}
              {formatActiveHours(conflict.leftActiveHours)} 与{" "}
              {conflict.rightAccountId}{" "}
              {formatActiveHours(conflict.rightActiveHours)}
            </Typography.Text>
          ))}
          {conflicts.length > 6 ? (
            <Typography.Text type="secondary">
              还有 {conflicts.length - 6} 条
            </Typography.Text>
          ) : null}
        </Space>
      }
    />
  );
}

function accountToRow(account: Account): SchedulerRow {
  return {
    id: account.id,
    enabled: account.enabled,
    scheduled: account.scheduled ?? true,
    platform: account.platform,
    ipGroup: account.ipGroup,
    activeHours: account.activeHours,
    notes: account.notes,
  };
}

function rowToSchedulerAccount(row: SchedulerRow): SchedulerAccountSettings {
  return {
    id: row.id,
    scheduled: row.scheduled,
    ipGroup: row.ipGroup,
    activeHours: row.activeHours,
  };
}

function validateActiveHours(
  form: ReturnType<typeof Form.useForm<ActiveHoursFormValues>>[0],
) {
  const ranges = form.getFieldValue("activeHours") as
    | ActiveHoursFormValues["activeHours"]
    | undefined;
  const invalid =
    !ranges?.length ||
    ranges.some((range) => {
      const start = Number(range?.start);
      const end = Number(range?.end);
      return (
        Number.isNaN(start) ||
        Number.isNaN(end) ||
        start < 0 ||
        end > 24 ||
        start >= end
      );
    });
  return invalid
    ? Promise.reject(new Error("班次必须满足 0 <= 开始 < 结束 <= 24"))
    : Promise.resolve();
}

function formatActiveHours(ranges: [number, number][]) {
  if (!ranges.length) {
    return "-";
  }
  return ranges.map(([start, end]) => `[${start}, ${end}]`).join(", ");
}

function formatScheduleTime(value?: string) {
  if (!value) {
    return "暂无排期";
  }
  const parsed = dayjs(value);
  return parsed.isValid() ? parsed.format("YYYY-MM-DD HH:mm") : value;
}

function isToday(value?: string) {
  if (!value) {
    return false;
  }
  const parsed = dayjs(value);
  return parsed.isValid() && parsed.isSame(dayjs(), "day");
}

function formatSchedulerStatusText(status: SchedulerHealth["status"]) {
  if (status === "running") {
    return "运行中";
  }
  if (status === "starting") {
    return "启动中";
  }
  if (status === "error") {
    return "异常";
  }
  return "未运行";
}

function formatServiceStatus(
  health: SchedulerHealth,
  processStatus: SchedulerProcessStatus,
) {
  if (
    health.error ||
    processStatus.error ||
    health.status === "error" ||
    processStatus.status === "error"
  ) {
    return "异常";
  }
  if (health.status === "running" || processStatus.status === "running") {
    return "正常";
  }
  if (health.status === "starting" || processStatus.status === "starting") {
    return "启动中";
  }
  return "未运行";
}

function formatConflictSummary(conflicts: IpGroupConflict[]) {
  return conflicts.length
    ? `发现 ${conflicts.length} 个 IP 排班冲突`
    : "IP 排班正常";
}

function formatSchedulerHealthError(error: string) {
  return error
    .replace(
      "scheduler health endpoint is not reachable",
      "调度健康检查接口不可访问",
    )
    .replace(
      "scheduler health endpoint returned invalid response",
      "调度健康检查接口返回异常响应",
    )
    .replace(
      "scheduler health endpoint returned status",
      "调度健康检查接口返回状态",
    );
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
