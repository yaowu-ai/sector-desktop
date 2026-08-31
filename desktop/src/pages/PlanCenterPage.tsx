import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Row,
  Skeleton,
  Space,
  Tag,
  Typography,
} from "antd";
import {
  CalendarClock,
  Crown,
  CheckCircle2,
  CreditCard,
  Gauge,
  Monitor,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Users,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useDesktopAuth } from "../app/DesktopAuthContext";
import { PageHeader } from "../components/PageHeader";
import { StatusTag, type StatusTone } from "../components/StatusTag";
import {
  loadDesktopPlans,
  type DesktopPlanItem,
  type DesktopPlansResponse,
  type DesktopSession,
  type DesktopSubscriptionCurrentResponse,
} from "../services/desktopApi";

const PLAN_QUOTA_ITEMS = [
  { key: "maxEnabledAccounts", label: "启用账号上限", type: "number" },
  { key: "maxDevices", label: "授权设备上限", type: "number" },
  { key: "dailyTaskRuns", label: "每日任务次数", type: "number" },
  { key: "scheduler", label: "自动调度", type: "boolean" },
  { key: "targetEngagement", label: "目标号互动", type: "boolean" },
  { key: "exportCsv", label: "CSV 导出", type: "boolean" },
  { key: "aiComment", label: "AI评论", type: "boolean" },
] as const;

type PlanVisualTier = "free" | "monthly" | "annual" | "standard";

const PLAN_CACHE_TTL_MS = 5 * 60 * 1000;
const PLAN_CACHE_STORAGE_PREFIX = "account-matrix-desktop-plans:";
const planCache = new Map<string, PlanCacheEntry>();
const planRequestCache = new Map<string, Promise<DesktopPlansResponse>>();

interface PlanCacheEntry {
  data: DesktopPlansResponse;
  cachedAt: number;
}

export function PlanCenterPage() {
  const auth = useDesktopAuth();
  const [plans, setPlans] = useState<DesktopPlansResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const planRequestIdRef = useRef(0);
  const currentPlanId = auth.subscription?.planId;
  const currentPlanCode = readClaimString(auth.license?.claims, "planCode");
  const planList = plans?.plans ?? [];
  const currentPlan = findCurrentPlan(
    planList,
    currentPlanId,
    currentPlanCode,
  );
  const currentPlanTier = currentPlan
    ? getPlanVisualTier(currentPlan)
    : getPlanVisualTierFromDescriptor(currentPlanCode, undefined);
  const limits = useMemo(
    () => readLimits(auth.license?.claims),
    [auth.license?.claims],
  );

  const refreshPlans = useCallback(
    async (options: { force?: boolean } = {}) => {
      if (!auth.session) return;

      const cacheKey = getPlanCacheKey(auth.apiBaseUrl, auth.session);
      const cached = readCachedPlans(cacheKey);
      const requestId = ++planRequestIdRef.current;

      if (cached) {
        setPlans(cached.data);
      }

      if (cached && isPlanCacheFresh(cached) && !options.force) {
        setLoading(false);
        setError(null);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const nextPlans = await requestDesktopPlans(
          auth.session,
          auth.apiBaseUrl,
          cacheKey,
        );
        if (requestId !== planRequestIdRef.current) return;
        writeCachedPlans(cacheKey, nextPlans);
        setPlans(nextPlans);
      } catch (nextError) {
        if (requestId !== planRequestIdRef.current) return;
        if (!cached) {
          setError(
            nextError instanceof Error ? nextError.message : String(nextError),
          );
        }
      } finally {
        if (requestId === planRequestIdRef.current) {
          setLoading(false);
        }
      }
    },
    [auth.apiBaseUrl, auth.session],
  );

  useEffect(() => {
    if (!auth.session) return;

    void refreshPlans();
  }, [auth.session, refreshPlans]);

  const handleRefreshEntitlement = useCallback(async () => {
    await Promise.all([
      auth.refreshEntitlement(),
      refreshPlans({ force: true }),
    ]);
  }, [auth, refreshPlans]);

  return (
    <div className="plan-center-page">
      <PageHeader
        title="套餐中心"
        description="查看当前套餐、订阅状态、其他套餐和本机当前额度。"
        extra={
          <Button
            icon={<RefreshCw size={16} />}
            onClick={() => void handleRefreshEntitlement()}
            loading={auth.loading || loading}
          >
            刷新授权
          </Button>
        }
      />

      {auth.subscription?.status !== "active" ? (
        <Alert
          className="shell-alert"
          type="warning"
          showIcon
          message="当前账号没有有效订阅"
          description="请完成套餐开通后再使用桌面端养号能力。"
        />
      ) : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="当前订阅" className="plan-current-card">
            <Space direction="vertical" size={14} className="full-width">
              <div
                className={[
                  "plan-current-badge",
                  "plan-option-card-current",
                  `plan-option-card-${currentPlanTier}`,
                ].join(" ")}
              >
                <div className="plan-option-head">
                  <div className="plan-option-title-group">
                    <span className="plan-option-tier-icon">
                      {renderPlanTierIcon(currentPlanTier)}
                    </span>
                    <div>
                      <Typography.Text
                        type="secondary"
                        className="plan-current-eyebrow"
                      >
                        当前套餐
                      </Typography.Text>
                      <Typography.Text strong className="plan-option-title">
                        {currentPlan?.planName || currentPlanCode || "-"}
                      </Typography.Text>
                      <div className="plan-option-tier-label">
                        {getPlanTierLabel(currentPlanTier)}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <Descriptions column={1} bordered size="small">
                <Descriptions.Item label="订阅状态">
                  <StatusTag
                    status={subscriptionTone(auth.subscription?.status)}
                    label={formatSubscriptionStatus(auth.subscription?.status)}
                  />
                </Descriptions.Item>
                <Descriptions.Item label="套餐价格">
                  {formatPrice(currentPlan?.priceCents)}
                </Descriptions.Item>
                <Descriptions.Item label="到期时间">
                  {formatDateTime(auth.subscription?.expiresAt)}
                </Descriptions.Item>
              </Descriptions>
            </Space>
          </Card>
        </Col>

        <Col xs={24} xl={16}>
          <Card title="套餐列表" className="plan-list-card">
            {loading && !plans ? (
              <Skeleton active paragraph={{ rows: 4 }} />
            ) : null}
            {loading && plans ? (
              <Typography.Text type="secondary">正在更新套餐列表...</Typography.Text>
            ) : null}
            {!loading && error && !plans ? (
              <Alert
                type="error"
                showIcon
                message="套餐列表加载失败"
                description={error}
              />
            ) : null}
            {plans && !error ? (
              <Row gutter={[12, 12]}>
                {planList.map((plan) => (
                  <Col xs={24} md={12} key={plan.planId}>
                    <PlanCard
                      plan={plan}
                      current={
                        plan.planId === currentPlanId ||
                        plan.planCode === currentPlanCode
                      }
                    />
                  </Col>
                ))}
                {planList.length === 0 ? (
                  <Col span={24}>
                    <div className="empty-state">
                      <Typography.Text type="secondary">
                        暂无可用套餐
                      </Typography.Text>
                    </div>
                  </Col>
                ) : null}
              </Row>
            ) : null}
          </Card>
        </Col>

        <Col xs={24}>
          <Card title="当前额度" className="plan-quota-card">
            <Row gutter={[12, 12]}>
              <QuotaCard
                icon={<Users size={22} />}
                title="启用账号上限"
                value={formatLimit(limits.maxEnabledAccounts)}
              />
              <QuotaCard
                icon={<Monitor size={22} />}
                title="授权设备上限"
                value={formatLimit(limits.maxDevices)}
              />
              <QuotaCard
                icon={<Gauge size={22} />}
                title="每日任务次数"
                value={formatLimit(limits.dailyTaskRuns)}
              />
              <QuotaCard
                icon={<CalendarClock size={22} />}
                title="自动调度"
                value={formatBooleanLimit(limits.scheduler)}
              />
              <QuotaCard
                icon={<CheckCircle2 size={22} />}
                title="目标号互动"
                value={formatBooleanLimit(limits.targetEngagement)}
              />
              <QuotaCard
                icon={<ShieldCheck size={22} />}
                title="CSV 导出"
                value={formatBooleanLimit(limits.exportCsv)}
              />
              <QuotaCard
                icon={<ShieldCheck size={22} />}
                title="AI评论"
                value={formatBooleanLimit(limits.aiComment)}
              />
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  );
}

function PlanCard({
  plan,
  current,
}: {
  plan: DesktopPlanItem;
  current: boolean;
}) {
  const tier = getPlanVisualTier(plan);
  const cardClassName = [
    "plan-option-card",
    `plan-option-card-${tier}`,
    current ? "plan-option-card-current" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={cardClassName}>
      <Space direction="vertical" size={10} className="full-width">
        <div className="plan-option-head">
          <div className="plan-option-title-group">
            <span className="plan-option-tier-icon">
              {renderPlanTierIcon(tier)}
            </span>
            <div>
              <Typography.Text strong className="plan-option-title">
                {plan.planName || plan.planCode || "未命名套餐"}
              </Typography.Text>
              <div className="plan-option-tier-label">
                {getPlanTierLabel(tier)}
              </div>
            </div>
          </div>
          {current ? <Tag color="blue">当前套餐</Tag> : null}
        </div>
        <div className="plan-option-price">
          <span className="plan-option-price-label">套餐价格</span>
          <span className="plan-option-price-value">
            {formatPrice(plan.priceCents)}
          </span>
        </div>
        <div className="plan-option-limits">
          {PLAN_QUOTA_ITEMS.map((item) => {
            const rawValue = plan.limits?.[item.key];
            const displayValue =
              item.type === "number"
                ? formatLimit(rawValue)
                : formatBooleanLimit(rawValue);
            return (
              <div
                className={[
                  "plan-option-limit",
                  isHighlightedLimit(rawValue)
                    ? "plan-option-limit-available"
                    : "plan-option-limit-muted",
                ].join(" ")}
                key={item.key}
              >
                <Typography.Text type="secondary">{item.label}</Typography.Text>
                <Typography.Text strong>{displayValue}</Typography.Text>
              </div>
            );
          })}
        </div>
      </Space>
    </div>
  );
}

function QuotaCard({
  icon,
  title,
  value,
}: {
  icon: React.ReactNode;
  title: string;
  value: string;
}) {
  return (
    <Col xs={24} sm={12} lg={8} xl={4}>
      <div
        className={[
          "quota-card",
          isPositiveQuotaDisplay(value)
            ? "quota-card-supported"
            : "quota-card-limited",
        ].join(" ")}
      >
        <div className="quota-card-icon">{icon}</div>
        <Typography.Text type="secondary">{title}</Typography.Text>
        <Typography.Title level={4}>{value}</Typography.Title>
      </div>
    </Col>
  );
}

function findCurrentPlan(
  plans: DesktopPlanItem[] | undefined,
  planId?: string | null,
  planCode?: string | null,
) {
  return (
    plans?.find(
      (plan) => plan.planId === planId || plan.planCode === planCode,
    ) ?? null
  );
}

function subscriptionTone(
  status?: DesktopSubscriptionCurrentResponse["status"],
): StatusTone {
  if (status === "active") return "ok";
  if (status === "expired" || status === "none") return "warning";
  return "idle";
}

function formatSubscriptionStatus(
  status?: DesktopSubscriptionCurrentResponse["status"],
) {
  if (status === "active") return "有效";
  if (status === "expired") return "已过期";
  if (status === "none") return "无订阅";
  if (status === "not_configured") return "未配置";
  return "未知";
}

function readLimits(claims?: Record<string, unknown> | null) {
  const limits = claims?.limits;
  return limits && typeof limits === "object"
    ? (limits as Record<string, unknown>)
    : {};
}

function readClaimString(
  claims: Record<string, unknown> | null | undefined,
  key: string,
) {
  const value = claims?.[key];
  return typeof value === "string" ? value : "";
}

function getPlanCacheKey(apiBaseUrl: string, session: DesktopSession) {
  return `${apiBaseUrl}|${session.userId || session.username}`;
}

function readCachedPlans(cacheKey: string) {
  const memoryCache = planCache.get(cacheKey);
  if (memoryCache) return memoryCache;

  try {
    const raw = window.sessionStorage.getItem(
      `${PLAN_CACHE_STORAGE_PREFIX}${cacheKey}`,
    );
    if (!raw) return null;

    const parsed = JSON.parse(raw) as PlanCacheEntry;
    if (!isPlanCacheEntry(parsed)) return null;
    planCache.set(cacheKey, parsed);
    return parsed;
  } catch {
    return null;
  }
}

function writeCachedPlans(cacheKey: string, data: DesktopPlansResponse) {
  const entry = { data, cachedAt: Date.now() };
  planCache.set(cacheKey, entry);

  try {
    window.sessionStorage.setItem(
      `${PLAN_CACHE_STORAGE_PREFIX}${cacheKey}`,
      JSON.stringify(entry),
    );
  } catch {
    // sessionStorage may be unavailable in restricted desktop/webview modes.
  }
}

function isPlanCacheFresh(entry: PlanCacheEntry) {
  return Date.now() - entry.cachedAt < PLAN_CACHE_TTL_MS;
}

function isPlanCacheEntry(value: unknown): value is PlanCacheEntry {
  if (!value || typeof value !== "object") return false;
  const entry = value as Partial<PlanCacheEntry>;
  return (
    typeof entry.cachedAt === "number" &&
    Boolean(entry.data) &&
    Array.isArray(entry.data?.plans)
  );
}

function requestDesktopPlans(
  session: DesktopSession,
  apiBaseUrl: string,
  cacheKey: string,
) {
  const existingRequest = planRequestCache.get(cacheKey);
  if (existingRequest) return existingRequest;

  const request = loadDesktopPlans(session, apiBaseUrl).finally(() => {
    planRequestCache.delete(cacheKey);
  });
  planRequestCache.set(cacheKey, request);
  return request;
}

function getPlanVisualTier(plan: DesktopPlanItem): PlanVisualTier {
  return getPlanVisualTierFromDescriptor(
    `${plan.planName} ${plan.planCode}`,
    plan.priceCents,
  );
}

function getPlanVisualTierFromDescriptor(
  descriptorValue: string,
  priceCents?: string | null,
): PlanVisualTier {
  const descriptor = descriptorValue.toLowerCase();
  const cents = Number(priceCents);
  if (
    descriptor.includes("free") ||
    descriptor.includes("免费") ||
    cents === 0
  ) {
    return "free";
  }
  if (
    descriptor.includes("annual") ||
    descriptor.includes("year") ||
    descriptor.includes("年度") ||
    descriptor.includes("年")
  ) {
    return "annual";
  }
  if (
    descriptor.includes("monthly") ||
    descriptor.includes("month") ||
    descriptor.includes("月度") ||
    descriptor.includes("月")
  ) {
    return "monthly";
  }
  return "standard";
}

function getPlanTierLabel(tier: PlanVisualTier) {
  if (tier === "free") return "入门体验";
  if (tier === "monthly") return "进阶运营";
  if (tier === "annual") return "年度优选";
  return "专业套餐";
}

function renderPlanTierIcon(tier: PlanVisualTier) {
  if (tier === "annual") return <Crown size={18} />;
  if (tier === "monthly") return <Zap size={18} />;
  if (tier === "free") return <CreditCard size={18} />;
  return <Sparkles size={18} />;
}

function isHighlightedLimit(value: unknown) {
  if (value === true || value === -1) return true;
  return typeof value === "number" && value > 0;
}

function isPositiveQuotaDisplay(value: string) {
  return value !== "-" && value !== "不支持";
}

function formatLimit(value: unknown) {
  if (value === -1) return "不限";
  if (typeof value === "number") return String(value);
  return "-";
}

function formatBooleanLimit(value: unknown) {
  if (value === true) return "支持";
  if (value === false) return "不支持";
  return "-";
}

function formatPrice(priceCents?: string | null) {
  if (!priceCents) return "-";
  const cents = Number(priceCents);
  if (!Number.isFinite(cents)) return "-";
  return `￥${(cents / 100).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatDateTime(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}
