import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import type { Key } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  Edit3,
  FileSearch,
  Plus,
  Power,
  RefreshCw,
  Save,
  Trash2,
  UserPlus,
} from "lucide-react";

import { confirmDanger } from "../components/ConfirmDanger";
import { AccountBrowserEnvironment } from "../components/AccountBrowserEnvironment";
import { PageHeader } from "../components/PageHeader";
import { ProcessOutputPanel } from "../components/ProcessOutputPanel";
import { StatusTag } from "../components/StatusTag";
import {
  loadConfig,
  queryAccountLogs,
  saveAccounts,
  getLoginCredentialStatus,
  saveLoginPassword,
  deleteLoginPassword,
  cleanupBuiltinChromiumData,
  listBrowserProfiles,
  checkBitbrowserApi,
  getCurrentRunStatus,
  runTikTokRegister,
  runTikTokRegisterBatch,
} from "../services/api";
import { usePlatformContext } from "../app/PlatformContext";
import {
  getPlatformLabel,
  isExecutablePlatform,
  PLATFORMS,
} from "../services/platforms";
import type {
  Account,
  AccountLastStatus,
  ActionLog,
  ConfigSnapshot,
  Platform,
  ValidationIssue,
  BrowserProviderId,
  LoginCredentialStatus,
  BrowserProfile,
  ProcessStatus,
} from "../services/types";

interface AccountFormValues {
  id: string;
  platform: Platform;
  enabled: boolean;
  ipGroup?: number;
  activeHours: Array<{ start?: number; end?: number }>;
  browserProvider?: BrowserProviderId;
  bitbrowserProfileId?: string;
  proxyType?: "http" | "https" | "socks5";
  proxy?: string;
  userDataDir?: string;
  loginEnabled: boolean;
  loginMethod: "password";
  loginUsername?: string;
  loginCredentialRef?: string;
  loginPassword?: string;
  notes?: string;
}

const BITBROWSER_DOWNLOAD_URL = "https://www.bitbrowser.cn/download";
const BUSY_RUN_STATUSES = new Set([
  "starting",
  "running",
  "pause_pending",
  "intervention_required",
]);
const ACCOUNT_DRAFT_FIELD_NAMES = [
  "id",
  "platform",
  "enabled",
  "ipGroup",
  "activeHours",
  "browserProvider",
  "bitbrowserProfileId",
  "proxyType",
  "proxy",
  "userDataDir",
  "loginEnabled",
  "loginMethod",
  "loginUsername",
  "notes",
] as const;

export function AccountPage() {
  const { currentPlatform } = usePlatformContext();
  const [form] = Form.useForm<AccountFormValues>();
  const [snapshot, setSnapshot] = useState<ConfigSnapshot | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [registeringAccountId, setRegisteringAccountId] = useState<
    string | null
  >(null);
  const [registeringBatch, setRegisteringBatch] = useState(false);
  const [currentRunStatus, setCurrentRunStatus] =
    useState<ProcessStatus | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<Key[]>([]);
  const [query, setQuery] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [logDrawerOpen, setLogDrawerOpen] = useState(false);
  const [logAccount, setLogAccount] = useState<Account | null>(null);
  const [accountLogs, setAccountLogs] = useState<ActionLog[]>([]);
  const [logLoading, setLogLoading] = useState(false);
  const [browserProfiles, setBrowserProfiles] = useState<BrowserProfile[]>([]);
  const [browserProfilesLoaded, setBrowserProfilesLoaded] = useState(false);

  const filteredAccounts = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const platformAccounts = accounts.filter(
      (account) => account.platform === currentPlatform,
    );
    if (!normalized) {
      return platformAccounts;
    }
    return platformAccounts.filter((account) =>
      [
        account.id,
        account.platform,
        account.bitbrowserProfileId,
        account.login?.username,
        account.notes,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalized)),
    );
  }, [accounts, currentPlatform, query]);

  const selectedAccounts = useMemo(
    () =>
      accounts.filter(
        (account) =>
          account.platform === currentPlatform &&
          selectedRowKeys.includes(account.id),
      ),
    [accounts, currentPlatform, selectedRowKeys],
  );
  const browserProfileById = useMemo(
    () => new Map(browserProfiles.map((profile) => [profile.id, profile])),
    [browserProfiles],
  );
  const currentRunBusy = Boolean(
    currentRunStatus && BUSY_RUN_STATUSES.has(currentRunStatus.status),
  );

  const refresh = async () => {
    setLoading(true);
    try {
      const nextSnapshot = await loadConfig();
      let nextBrowserProfiles: BrowserProfile[] = [];
      let nextBrowserProfilesLoaded = false;
      if (
        nextSnapshot.accounts.some(
          (account) =>
            resolveBrowserProvider(account) === "bitbrowser" &&
            Boolean(account.bitbrowserProfileId),
        )
      ) {
        try {
          nextBrowserProfiles = await listBrowserProfiles();
          nextBrowserProfilesLoaded = true;
        } catch {
          nextBrowserProfiles = [];
          nextBrowserProfilesLoaded = false;
        }
      }
      setSnapshot(nextSnapshot);
      setAccounts(nextSnapshot.accounts);
      setBrowserProfiles(nextBrowserProfiles);
      setBrowserProfilesLoaded(nextBrowserProfilesLoaded);
      setSelectedRowKeys((current) =>
        current.filter((key) =>
          nextSnapshot.accounts.some((account) => account.id === key),
        ),
      );
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    let disposed = false;
    const refreshRunStatus = async () => {
      try {
        const nextStatus = await getCurrentRunStatus();
        if (!disposed) {
          setCurrentRunStatus(nextStatus);
        }
      } catch {
        if (!disposed) {
          setCurrentRunStatus(null);
        }
      }
    };
    void refreshRunStatus();
    const intervalId = window.setInterval(() => {
      void refreshRunStatus();
    }, 1500);
    return () => {
      disposed = true;
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    setSelectedRowKeys([]);
    setQuery("");
  }, [currentPlatform]);

  const openCreate = () => {
    setEditingAccount(null);
    form.setFieldsValue({
      id: nextAccountId(accounts, currentPlatform),
      platform: currentPlatform,
      enabled: true,
      activeHours: [{ start: 9, end: 12 }],
      browserProvider: "bitbrowser",
      bitbrowserProfileId: "",
      proxyType: "socks5",
      proxy: "",
      userDataDir: "",
      loginEnabled: false,
      loginMethod: "password",
      loginUsername: "",
      loginCredentialRef: "",
      loginPassword: "",
      notes: "",
    });
    setDrawerOpen(true);
  };

  const openEdit = (account: Account) => {
    setEditingAccount(account);
    form.setFieldsValue(accountToForm(account));
    setDrawerOpen(true);
  };

  const saveForm = async () => {
    const values = await form.validateFields();
    const nextAccount = formToAccount(values, editingAccount);
    const ok = await persistAccounts(
      upsertAccount(accounts, nextAccount, editingAccount),
      "账号配置已保存",
    );
    if (ok) {
      setDrawerOpen(false);
    }
  };

  const saveAccountDraftForCredentials = async () => {
    await form.validateFields([...ACCOUNT_DRAFT_FIELD_NAMES]);
    const values = form.getFieldsValue(true) as AccountFormValues;
    const hasCredentialRef = Boolean(values.loginCredentialRef?.trim());
    const nextAccount = formToAccount(
      hasCredentialRef ? values : { ...values, loginEnabled: false },
      editingAccount,
    );
    const ok = await persistAccounts(
      upsertAccount(accounts, nextAccount, editingAccount),
      editingAccount ? "账号配置已保存" : "账号已保存，可以继续配置凭据",
    );
    if (!ok) {
      return null;
    }
    setEditingAccount(nextAccount);
    form.setFieldsValue({
      ...values,
      id: nextAccount.id,
      loginPassword: values.loginPassword ?? "",
    });
    return nextAccount;
  };

  const saveCredentialAccountSettings = async (
    account: Account,
    credentialRef: string,
  ) => {
    const values = form.getFieldsValue(true) as AccountFormValues;
    const nextAccount = formToAccount(
      { ...values, loginCredentialRef: credentialRef },
      account,
    );
    const ok = await persistAccounts(
      upsertAccount(accounts, nextAccount, account),
      "账号登录配置已保存",
    );
    if (!ok) {
      return null;
    }
    setEditingAccount(nextAccount);
    form.setFieldsValue({
      ...accountToForm(nextAccount),
      loginPassword: "",
    });
    return nextAccount;
  };

  const toggleAccount = async (account: Account, enabled: boolean) => {
    await persistAccounts(
      accounts.map((item) =>
        item.id === account.id ? { ...item, enabled } : item,
      ),
      `${account.id} 已${enabled ? "启用" : "停用"}`,
    );
  };

  const confirmDeleteAccount = (account: Account) => {
    confirmDanger({
      title: `删除账号 ${account.id}`,
      content: `只会从 accounts.yaml 删除该账号配置，不会删除 BitBrowser profile ${account.bitbrowserProfileId ?? "未绑定"}。此操作不可撤销。`,
      onOk: () => {
        void persistAccounts(
          accounts.filter((item) => item.id !== account.id),
          `${account.id} 已删除`,
        );
      },
    });
  };

  const batchSetEnabled = async (enabled: boolean) => {
    if (selectedAccounts.length === 0) {
      message.warning("请先选择账号");
      return;
    }

    await persistAccounts(
      accounts.map((account) =>
        selectedRowKeys.includes(account.id)
          ? { ...account, enabled }
          : account,
      ),
      `已${enabled ? "启用" : "停用"} ${selectedAccounts.length} 个账号`,
    );
  };

  const batchRegisterAccounts = async () => {
    const disabledReason = batchRegisterDisabledReason(
      selectedAccounts,
      currentRunBusy,
      registeringAccountId,
      registeringBatch,
    );
    if (disabledReason) {
      message.warning(disabledReason);
      return;
    }

    const accountIds = selectedAccounts.map((account) => account.id);
    setRegisteringBatch(true);
    try {
      const result = await runTikTokRegisterBatch(accountIds);
      message.success(
        `批量注册流程已启动，${accountIds.length} 个账号，PID ${
          result.processId ?? "-"
        }`,
      );
      setCurrentRunStatus(await getCurrentRunStatus());
      await refresh();
    } catch (error) {
      message.error(formatRegisterStartError(error));
    } finally {
      setRegisteringBatch(false);
    }
  };

  const persistAccounts = async (
    nextAccounts: Account[],
    successText: string,
  ): Promise<boolean> => {
    setSaving(true);
    try {
      await saveAccounts({
        platform: currentPlatform,
        accounts: nextAccounts.filter(
          (account) => account.platform === currentPlatform,
        ),
      });
      message.success(successText);
      await refresh();
      return true;
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
      return false;
    } finally {
      setSaving(false);
    }
  };

  const registerAccount = async (account: Account) => {
    const disabledReason = accountRegisterDisabledReason(
      account,
      currentRunBusy,
      registeringAccountId,
      registeringBatch,
    );
    if (disabledReason) {
      message.warning(disabledReason);
      return;
    }

    setRegisteringAccountId(account.id);
    try {
      const result = await runTikTokRegister(account.id);
      message.success(`账号注册流程已启动，PID ${result.processId ?? "-"}`);
      setCurrentRunStatus(await getCurrentRunStatus());
      await refresh();
    } catch (error) {
      message.error(formatRegisterStartError(error));
    } finally {
      setRegisteringAccountId(null);
    }
  };

  const openLogs = async (account: Account) => {
    setLogAccount(account);
    setLogDrawerOpen(true);
    setLogLoading(true);
    try {
      setAccountLogs(await queryAccountLogs(account.id));
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLogLoading(false);
    }
  };

  const cleanupBuiltinData = (account: Account) => {
    Modal.confirm({
      title: `清理内置 Chromium 数据 ${account.id}`,
      content:
        "只会删除该账号在 Account Matrix 内置 Chromium 下的本地用户数据，不会删除 BitBrowser profile。",
      okText: "清理",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        try {
          const result = await cleanupBuiltinChromiumData(account.id);
          message.success(`${result.accountId}: ${result.message}`);
          await refresh();
        } catch (error) {
          message.error(error instanceof Error ? error.message : String(error));
        }
      },
    });
  };

  const columns: ColumnsType<Account> = [
    {
      title: "账号 ID",
      dataIndex: "id",
      key: "id",
      fixed: "left",
      width: 150,
      sorter: (a, b) => a.id.localeCompare(b.id),
      render: (id: string) => <Typography.Text strong>{id}</Typography.Text>,
    },
    {
      title: "平台",
      dataIndex: "platform",
      key: "platform",
      width: 120,
      filters: PLATFORMS.map((platform) => ({
        text: platform.localeName,
        value: platform.id,
      })),
      onFilter: (value, record) => record.platform === value,
      render: (platform: Platform) => (
        <StatusTag
          status={isExecutablePlatform(platform) ? "ok" : "warning"}
          label={getPlatformLabel(platform)}
        />
      ),
    },
    {
      title: "浏览器环境",
      key: "browserEnvironment",
      width: 300,
      render: (_, account) => (
        <AccountBrowserEnvironment accounts={[account]} />
      ),
    },
    {
      title: "登录邮箱",
      dataIndex: ["login", "username"],
      key: "loginUsername",
      width: 220,
      ellipsis: true,
      render: (_value, account) => account.login?.username || "-",
    },
    {
      title: "登录状态",
      dataIndex: "loginCheck",
      key: "loginState",
      width: 150,
      render: (_value, account) => <LoginStateTag account={account} />,
    },
    {
      title: "自动登录",
      dataIndex: ["login", "enabled"],
      key: "autoLogin",
      width: 130,
      render: (_value, account) => <AutoLoginTag account={account} />,
    },
    {
      title: "启用",
      dataIndex: "enabled",
      key: "enabled",
      width: 90,
      filters: [
        { text: "启用", value: "true" },
        { text: "停用", value: "false" },
      ],
      onFilter: (value, record) => String(record.enabled) === value,
      render: (enabled: boolean, account) => (
        <Switch
          size="small"
          checked={enabled}
          loading={saving}
          onChange={(checked) => void toggleAccount(account, checked)}
        />
      ),
    },
    {
      title: "IP 分组",
      dataIndex: "ipGroup",
      key: "ipGroup",
      width: 100,
      render: (value?: number) => value ?? "-",
    },
    {
      title: "运行班次",
      dataIndex: "activeHours",
      key: "activeHours",
      width: 160,
      render: (ranges: Account["activeHours"]) => formatActiveHours(ranges),
    },
    {
      title: "代理",
      key: "proxy",
      width: 260,
      render: (_, account) => (
        <ProxyCell
          account={account}
          bitbrowserProfile={profileForAccount(account, browserProfileById)}
          bitbrowserProfilesLoaded={browserProfilesLoaded}
        />
      ),
    },
    {
      title: "profile 状态",
      dataIndex: "profileOpen",
      key: "profileOpen",
      width: 120,
      render: (profileOpen?: boolean) => {
        if (profileOpen === true) {
          return <StatusTag status="running" label="已打开" />;
        }
        if (profileOpen === false) {
          return <StatusTag status="idle" label="未打开" />;
        }
        return <StatusTag status="idle" label="未检测" />;
      },
    },
    {
      title: "最近执行",
      dataIndex: "lastRunAt",
      key: "lastRunAt",
      width: 180,
      render: (value?: string) => value ?? "-",
    },
    {
      title: "最近结果",
      dataIndex: "lastStatus",
      key: "lastStatus",
      width: 110,
      render: (status?: AccountLastStatus) => (
        <LastStatusTag status={status ?? "unknown"} />
      ),
    },
    {
      title: "备注",
      dataIndex: "notes",
      key: "notes",
      width: 240,
      ellipsis: true,
      render: (value?: string) => value || "-",
    },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: 220,
      render: (_, account) => (
        <Space size={6}>
          <Tooltip title="编辑" placement="top">
            <Button
              aria-label="编辑"
              icon={<Edit3 size={15} />}
              onClick={() => openEdit(account)}
            />
          </Tooltip>
          <Tooltip
            title={
              accountRegisterDisabledReason(
                account,
                currentRunBusy,
                registeringAccountId,
                registeringBatch,
              ) ?? "打开该账号浏览器环境并进入 TikTok 注册"
            }
            placement="top"
          >
            <span>
              <Button
                aria-label="注册"
                icon={<UserPlus size={15} />}
                onClick={() => void registerAccount(account)}
                loading={registeringAccountId === account.id}
                disabled={Boolean(
                  accountRegisterDisabledReason(
                    account,
                    currentRunBusy,
                    registeringAccountId,
                    registeringBatch,
                  ),
                )}
              >
                注册
              </Button>
            </span>
          </Tooltip>
          <Tooltip title="日志" placement="top">
            <Button
              aria-label="日志"
              icon={<FileSearch size={15} />}
              onClick={() => void openLogs(account)}
            />
          </Tooltip>
          <Tooltip title="删除" placement="top">
            <Button
              danger
              aria-label="删除"
              icon={<Trash2 size={15} />}
              onClick={() => confirmDeleteAccount(account)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="账号管理"
        description="读取、编辑、校验 accounts.yaml 中的账号。"
        extra={
          <Space>
            <Button
              icon={<RefreshCw size={16} />}
              onClick={refresh}
              loading={loading}
            >
              刷新
            </Button>
            <Button
              type="primary"
              icon={<Plus size={16} />}
              onClick={openCreate}
            >
              新增账号
            </Button>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card>
            <Space direction="vertical" size={12} className="full-width">
              {snapshot?.validation.errors.length ? (
                <IssueAlert
                  type="error"
                  title="配置错误"
                  issues={snapshot.validation.errors}
                />
              ) : null}
              {snapshot?.validation.warnings.length ? (
                <IssueAlert
                  type="warning"
                  title="配置告警"
                  issues={snapshot.validation.warnings}
                  defaultCollapsed
                />
              ) : null}

              <Space
                wrap
                className="full-width"
                style={{ justifyContent: "space-between" }}
              >
                <Space wrap>
                  <Input.Search
                    allowClear
                    placeholder="搜索账号、平台、profile 或备注"
                    style={{ width: 320 }}
                    onSearch={setQuery}
                    onChange={(event) => setQuery(event.target.value)}
                  />
                  <Tag color="blue">总数 {accounts.length}</Tag>
                  <Tag color="green">
                    启用 {accounts.filter((account) => account.enabled).length}
                  </Tag>
                  <Tag>已选 {selectedAccounts.length}</Tag>
                </Space>
                <Space>
                  <Tooltip
                    title={
                      batchRegisterDisabledReason(
                        selectedAccounts,
                        currentRunBusy,
                        registeringAccountId,
                        registeringBatch,
                      ) ?? "对已选账号依次启动 TikTok Google 注册"
                    }
                    placement="top"
                  >
                    <span>
                      <Button
                        icon={<UserPlus size={15} />}
                        disabled={Boolean(
                          batchRegisterDisabledReason(
                            selectedAccounts,
                            currentRunBusy,
                            registeringAccountId,
                            registeringBatch,
                          ),
                        )}
                        loading={registeringBatch}
                        onClick={() => void batchRegisterAccounts()}
                      >
                        批量注册
                      </Button>
                    </span>
                  </Tooltip>
                  <Button
                    icon={<Power size={15} />}
                    disabled={selectedAccounts.length === 0}
                    loading={saving}
                    onClick={() => void batchSetEnabled(true)}
                  >
                    批量启用
                  </Button>
                  <Button
                    icon={<Power size={15} />}
                    disabled={selectedAccounts.length === 0}
                    loading={saving}
                    onClick={() => void batchSetEnabled(false)}
                  >
                    批量停用
                  </Button>
                </Space>
              </Space>

              <Table
                rowKey="id"
                loading={loading || saving}
                columns={columns}
                dataSource={filteredAccounts}
                rowSelection={{
                  selectedRowKeys,
                  onChange: setSelectedRowKeys,
                }}
                scroll={{ x: 2250 }}
                pagination={{ pageSize: 12, showSizeChanger: true }}
              />
            </Space>
          </Card>
        </Col>

        <Col span={24}>
          <ProcessOutputPanel title="任务输出" />
        </Col>
      </Row>

      <Drawer
        title={editingAccount ? `编辑账号 ${editingAccount.id}` : "新增账号"}
        width={560}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        extra={
          <Button
            type="primary"
            icon={<Save size={16} />}
            loading={saving}
            onClick={() => void saveForm()}
          >
            保存
          </Button>
        }
      >
        <AccountForm
          form={form}
          accounts={accounts}
          editingAccount={editingAccount}
          currentPlatform={currentPlatform}
          saving={saving}
          onEnsureAccountSaved={saveAccountDraftForCredentials}
          onSaveCredentialAccount={saveCredentialAccountSettings}
        />
      </Drawer>

      <Drawer
        title={logAccount ? `${logAccount.id} 执行日志` : "执行日志"}
        width={720}
        open={logDrawerOpen}
        onClose={() => setLogDrawerOpen(false)}
      >
        <Table
          rowKey="id"
          loading={logLoading}
          dataSource={accountLogs}
          pagination={{ pageSize: 12 }}
          columns={[
            { title: "时间", dataIndex: "ts", width: 180 },
            { title: "动作", dataIndex: "action", width: 140 },
            {
              title: "状态",
              dataIndex: "status",
              width: 100,
              render: (status: string) => (
                <Tag color={statusColor(status)}>{status}</Tag>
              ),
            },
            { title: "详情", dataIndex: "detail", ellipsis: true },
          ]}
        />
      </Drawer>
    </>
  );
}

function AccountForm({
  form,
  accounts,
  editingAccount,
  currentPlatform,
  saving,
  onEnsureAccountSaved,
  onSaveCredentialAccount,
}: {
  form: ReturnType<typeof Form.useForm<AccountFormValues>>[0];
  accounts: Account[];
  editingAccount: Account | null;
  currentPlatform: Platform;
  saving: boolean;
  onEnsureAccountSaved: () => Promise<Account | null>;
  onSaveCredentialAccount: (
    account: Account,
    credentialRef: string,
  ) => Promise<Account | null>;
}) {
  const browserProvider =
    Form.useWatch("browserProvider", form) ?? "bitbrowser";
  const loginEnabled = Form.useWatch("loginEnabled", form) ?? false;
  const loginCredentialRef = Form.useWatch("loginCredentialRef", form) ?? "";
  const [credentialStatus, setCredentialStatus] =
    useState<LoginCredentialStatus | null>(null);
  const [credentialLoading, setCredentialLoading] = useState(false);
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [bitbrowserUnavailable, setBitbrowserUnavailable] = useState(false);

  useEffect(() => {
    if (editingAccount || browserProvider !== "bitbrowser") {
      setBitbrowserUnavailable(false);
      return;
    }

    let active = true;
    checkBitbrowserApi()
      .then((status) => {
        if (active) {
          setBitbrowserUnavailable(!status.available);
        }
      })
      .catch(() => {
        if (active) {
          setBitbrowserUnavailable(true);
        }
      });

    return () => {
      active = false;
    };
  }, [browserProvider, editingAccount]);

  const refreshCredentialStatus = async () => {
    if (!editingAccount) {
      setCredentialStatus(null);
      return null;
    }
    setCredentialLoading(true);
    try {
      const result = await getLoginCredentialStatus(editingAccount.id);
      setCredentialStatus(result);
      if (result.credentialRef) {
        form.setFieldValue("loginCredentialRef", result.credentialRef);
      }
      return result;
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
      return null;
    } finally {
      setCredentialLoading(false);
    }
  };

  useEffect(() => {
    void refreshCredentialStatus();
  }, [editingAccount?.id]);

  const ensureCredentialAccount = async () => {
    if (editingAccount) {
      return editingAccount;
    }
    return onEnsureAccountSaved();
  };

  const savePassword = async () => {
    const password = form.getFieldValue("loginPassword");
    if (!password) {
      message.warning("请输入要保存的密码。");
      return;
    }
    const account = await ensureCredentialAccount();
    if (!account) {
      return;
    }
    setPasswordSaving(true);
    try {
      const result = await saveLoginPassword({
        accountId: account.id,
        password,
      });
      setCredentialStatus(result);
      form.setFieldValue("loginCredentialRef", result.credentialRef ?? "");
      form.setFieldValue("loginPassword", "");
      if (form.getFieldValue("loginEnabled") && result.credentialRef) {
        await onSaveCredentialAccount(account, result.credentialRef);
      }
      message.success("登录密码已保存到本机安全凭据存储。");
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setPasswordSaving(false);
    }
  };

  const deletePassword = async () => {
    const account = await ensureCredentialAccount();
    if (!account) {
      return;
    }
    Modal.confirm({
      title: `删除 ${account.id} 的登录密码`,
      content:
        "只会删除本机加密保存的登录凭据，不会改动 accounts.yaml 中的账号配置。",
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        setCredentialLoading(true);
        try {
          const result = await deleteLoginPassword(account.id);
          setCredentialStatus(result);
          message.success("登录密码已删除。");
        } catch (error) {
          message.error(error instanceof Error ? error.message : String(error));
        } finally {
          setCredentialLoading(false);
        }
      },
    });
  };

  const checkLoginStatus = async () => {
    const account = await ensureCredentialAccount();
    if (!account) {
      return;
    }
    setCredentialLoading(true);
    let result: LoginCredentialStatus | null = null;
    try {
      result = await getLoginCredentialStatus(account.id);
      setCredentialStatus(result);
      if (result.credentialRef) {
        form.setFieldValue("loginCredentialRef", result.credentialRef);
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setCredentialLoading(false);
    }
    if (!result) {
      return;
    }
    if (result.saved && result.readable) {
      message.success(
        "凭据已保存且可读取。真实网页登录状态会在任务运行时检测。",
      );
    } else if (result.saved) {
      message.error(result.error ?? "凭据存在，但当前无法读取。");
    } else {
      message.warning("尚未保存登录凭据。真实网页登录状态会在任务运行时检测。");
    }
  };

  const testAutoLogin = async () => {
    const account = await ensureCredentialAccount();
    if (!account) {
      return;
    }
    Modal.confirm({
      title: "测试自动登录",
      content:
        "当前会使用运行时登录流程检测并处理登录页；遇到验证码、二次验证或安全检查会暂停并提示人工接管。",
      okText: "确认",
      cancelText: "取消",
      onOk: () => message.info("请从任务运行或诊断入口触发实际登录检测。"),
    });
  };

  return (
    <Form form={form} layout="vertical" requiredMark={false}>
      <Form.Item
        name="id"
        label="账号 ID"
        rules={[
          { required: true, message: "请输入账号 ID" },
          {
            pattern: /^[A-Za-z0-9_-]+$/,
            message: "账号 ID 只能包含字母、数字、下划线和短横线",
          },
          {
            validator: (_, value?: string) => {
              const id = value?.trim();
              if (!id || id === editingAccount?.id) {
                return Promise.resolve();
              }
              if (accounts.some((account) => account.id === id)) {
                return Promise.reject(new Error("账号 ID 已存在"));
              }
              return Promise.resolve();
            },
          },
        ]}
      >
        <Input placeholder="例如 tiktok_106、instagram_106、whatsapp_106、douyin_106" />
      </Form.Item>

      <Row gutter={12}>
        <Col span={12}>
          <Form.Item name="platform" label="平台" rules={[{ required: true }]}>
            <Select
              disabled
              options={PLATFORMS.filter(
                (platform) => platform.id === currentPlatform,
              ).map((platform) => ({
                value: platform.id,
                label: getPlatformLabel(platform.id),
              }))}
              onChange={(platform: Platform) => {
                if (!editingAccount) {
                  form.setFieldValue("id", nextAccountId(accounts, platform));
                }
              }}
            />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Space align="center">
              <Switch />
              <Typography.Text type="secondary">
                开启后可被养号任务、目标号互动和调度使用；关闭后仅保留配置，不自动执行。
              </Typography.Text>
            </Space>
          </Form.Item>
        </Col>
      </Row>

      <Form.Item name="ipGroup" label="IP 分组">
        <InputNumber
          min={0}
          precision={0}
          className="full-width"
          placeholder="例如 101"
        />
      </Form.Item>

      <Form.Item
        name="browserProvider"
        label="浏览器提供方"
        rules={[{ required: true }]}
        extra={
          bitbrowserUnavailable ? (
            <Typography.Link href={BITBROWSER_DOWNLOAD_URL} target="_blank">
              下载 BitBrowser
            </Typography.Link>
          ) : null
        }
      >
        <Select
          options={[
            { value: "bitbrowser", label: "BitBrowser" },
            { value: "builtin_chromium", label: "内置 Chromium" },
          ]}
        />
      </Form.Item>

      {browserProvider === "bitbrowser" ? (
        <Form.Item
          name="bitbrowserProfileId"
          label="BitBrowser 窗口 ID"
          rules={[
            {
              validator: (_, value?: string) => {
                const profileId = value?.trim();
                if (!profileId) {
                  return Promise.resolve();
                }
                const conflict = accounts.find(
                  (account) =>
                    account.id !== editingAccount?.id &&
                    account.bitbrowserProfileId === profileId,
                );
                if (conflict) {
                  return Promise.reject(
                    new Error(`profile_id 已被 ${conflict.id} 使用`),
                  );
                }
                return Promise.resolve();
              },
            },
          ]}
        >
          <Input placeholder="BitBrowser 窗口 ID" />
        </Form.Item>
      ) : null}

      {browserProvider === "builtin_chromium" ? (
        <>
          <Alert
            type="warning"
            showIcon
            message="内置 Chromium 是生产可选方案。TikTok 默认推荐仍是 BitBrowser。"
            description="Account Matrix 会为每个账号使用独立用户数据目录，打开临时 CDP 端口，并且只关闭由它自己启动的浏览器进程；它不等价替代 BitBrowser 的指纹环境能力。"
          />
          <Row gutter={12}>
            <Col xs={24} md={8}>
              <Form.Item name="proxyType" label="代理类型">
                <Select
                  options={[
                    { value: "http", label: "HTTP" },
                    { value: "https", label: "HTTPS" },
                    { value: "socks5", label: "SOCKS5" },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={16}>
              <Form.Item
                name="proxy"
                label="代理"
                extra="可选。格式：主机:端口:用户名:密码"
              >
                <Input placeholder="127.0.0.1:1080" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            name="userDataDir"
            label="用户数据目录"
            extra="可选。留空时 Account Matrix 会自动创建 data/browser/builtin_chromium/<账号>/user-data。"
          >
            <Input placeholder="留空使用每账号默认目录" />
          </Form.Item>
        </>
      ) : null}

      <Space
        direction="vertical"
        size={12}
        className="full-width"
        style={{ marginBottom: 18 }}
      >
        <Typography.Text strong>登录信息</Typography.Text>
        <Alert
          type="info"
          showIcon
          message="这里配置平台账号和自动登录凭据。"
          description="密码只保存在本机加密凭据存储中；accounts.yaml 只保存登录用户名和 credential_ref。"
        />
        <Form.Item name="loginEnabled" label="自动登录" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item name="loginMethod" hidden initialValue="password">
          <Input />
        </Form.Item>
        <Form.Item
          name="loginCredentialRef"
          hidden
          rules={[
            {
              validator: (_, value?: string) => {
                if (!loginEnabled || value?.trim()) {
                  return Promise.resolve();
                }
                return Promise.reject(
                  new Error("开启自动登录前请先保存密码。"),
                );
              },
            },
          ]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          name="loginUsername"
          label="登录邮箱/用户名"
          rules={[
            {
              validator: (_, value?: string) => {
                if (!loginEnabled || value?.trim()) {
                  return Promise.resolve();
                }
                return Promise.reject(
                  new Error("开启自动登录时必须填写登录邮箱或用户名。"),
                );
              },
            },
          ]}
        >
          <Input placeholder="平台登录邮箱或用户名" />
        </Form.Item>
        <Form.Item
          label="凭据状态"
          required={loginEnabled && !loginCredentialRef}
          validateStatus={
            loginEnabled && !loginCredentialRef ? "error" : undefined
          }
          help={
            loginEnabled && !loginCredentialRef
              ? "开启自动登录前请先保存密码。"
              : undefined
          }
        >
          <Space wrap>
            <CredentialStateTag
              status={credentialStatus}
              credentialRef={loginCredentialRef}
            />
            {loginCredentialRef ? (
              <Typography.Text code>{loginCredentialRef}</Typography.Text>
            ) : null}
          </Space>
        </Form.Item>
        <Form.Item name="loginPassword" label="登录密码">
          <Input.Password
            autoComplete="new-password"
            placeholder={
              editingAccount
                ? "仅在保存或更新密码时填写"
                : "填写后点击保存密码，会先保存账号"
            }
          />
        </Form.Item>
        <Space wrap>
          <Button
            onClick={() => void savePassword()}
            loading={passwordSaving}
            disabled={saving || credentialLoading}
          >
            保存密码
          </Button>
          <Button
            danger
            onClick={() => void deletePassword()}
            loading={credentialLoading}
            disabled={saving || passwordSaving}
          >
            删除密码
          </Button>
          <Button
            onClick={() => void checkLoginStatus()}
            loading={credentialLoading}
            disabled={saving || passwordSaving}
          >
            检查凭据
          </Button>
          <Button
            onClick={() => void testAutoLogin()}
            disabled={saving || passwordSaving || credentialLoading}
          >
            测试自动登录
          </Button>
        </Space>
      </Space>

      <Form.List name="activeHours">
        {(fields, { add, remove }) => (
          <Space direction="vertical" className="full-width">
            <Typography.Text strong>运行班次</Typography.Text>
            {fields.map((field) => (
              <Space key={field.key} align="baseline">
                <Form.Item
                  {...field}
                  name={[field.name, "start"]}
                  rules={[{ required: true, message: "开始小时必填" }]}
                >
                  <InputNumber min={0} max={24} step={0.5} placeholder="开始" />
                </Form.Item>
                <Typography.Text>到</Typography.Text>
                <Form.Item
                  {...field}
                  name={[field.name, "end"]}
                  rules={[
                    { required: true, message: "结束小时必填" },
                    {
                      validator: () => validateActiveHourRows(form),
                    },
                  ]}
                >
                  <InputNumber min={0} max={24} step={0.5} placeholder="结束" />
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

      <Form.Item name="notes" label="备注" style={{ marginTop: 18 }}>
        <Input.TextArea rows={4} placeholder="账号说明、班次或代理备注" />
      </Form.Item>
    </Form>
  );
}

function IssueAlert({
  type,
  title,
  issues,
  defaultCollapsed = false,
}: {
  type: "error" | "warning";
  title: string;
  issues: ValidationIssue[];
  defaultCollapsed?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <Alert
      type={type}
      showIcon
      message={
        <Space size={8}>
          <Typography.Text strong>{title}</Typography.Text>
          {defaultCollapsed ? (
            <Tag color={type === "warning" ? "gold" : "red"}>
              {issues.length} 条
            </Tag>
          ) : null}
        </Space>
      }
      description={collapsed ? undefined : <IssueList issues={issues} />}
      action={
        defaultCollapsed ? (
          <Button
            type="text"
            size="small"
            onClick={() => setCollapsed((nextCollapsed) => !nextCollapsed)}
          >
            {collapsed ? "展开 ↓" : "收起 ↑"}
          </Button>
        ) : undefined
      }
    />
  );
}

function IssueList({ issues }: { issues: ValidationIssue[] }) {
  return (
    <Space direction="vertical" size={2}>
      {issues.slice(0, 6).map((issue) => (
        <Typography.Text key={`${issue.path}-${issue.message}`}>
          {issue.path}: {issue.message}
        </Typography.Text>
      ))}
      {issues.length > 6 ? (
        <Typography.Text type="secondary">
          还有 {issues.length - 6} 条
        </Typography.Text>
      ) : null}
    </Space>
  );
}

function CredentialStateTag({
  status,
  credentialRef,
}: {
  status: LoginCredentialStatus | null;
  credentialRef?: string;
}) {
  if (status?.saved && status.readable) {
    return <Tag color="green">已保存</Tag>;
  }
  if (status?.saved && !status.readable) {
    return <Tag color="red">读取失败</Tag>;
  }
  if (credentialRef) {
    return <Tag color="gold">缺失</Tag>;
  }
  return <Tag>未保存</Tag>;
}

function LoginStateTag({ account }: { account: Account }) {
  const loginCheck = account.loginCheck;
  if (!loginCheck) {
    return <StatusTag status="idle" label="未检测" />;
  }

  const status = loginCheck.status;
  const tooltip = `${loginCheck.ts}${loginCheck.detail ? ` ${loginCheck.detail}` : ""}`;
  if (status === "ok" || status === "logged_in") {
    return (
      <Tooltip title={tooltip}>
        <span>
          <StatusTag status="ok" label="登录正常" />
        </span>
      </Tooltip>
    );
  }
  if (status === "logged_out") {
    return (
      <Tooltip title={tooltip}>
        <span>
          <StatusTag status="warning" label="登录过期" />
        </span>
      </Tooltip>
    );
  }
  if (status === "login_page") {
    return (
      <Tooltip title={tooltip}>
        <span>
          <StatusTag status="warning" label="未登录" />
        </span>
      </Tooltip>
    );
  }
  if (status === "captcha") {
    return (
      <Tooltip title={tooltip}>
        <span>
          <StatusTag status="warning" label="需要验证码" />
        </span>
      </Tooltip>
    );
  }
  if (status === "mfa" || status === "security_check") {
    return (
      <Tooltip title={tooltip}>
        <span>
          <StatusTag status="warning" label="需要人工验证" />
        </span>
      </Tooltip>
    );
  }
  return (
    <Tooltip title={tooltip}>
      <span>
        <StatusTag status="idle" label="状态未知" />
      </span>
    </Tooltip>
  );
}

function AutoLoginTag({ account }: { account: Account }) {
  const login = account.login;
  if (!login?.username) {
    return <StatusTag status="idle" label="未配置" />;
  }
  if (login.enabled && login.credentialRef) {
    return <StatusTag status="ok" label="已配置" />;
  }
  if (login.enabled && !login.credentialRef) {
    return <StatusTag status="error" label="缺少密码" />;
  }
  return <StatusTag status="idle" label="未启用" />;
}

function LastStatusTag({ status }: { status: AccountLastStatus }) {
  if (status === "ok") {
    return <StatusTag status="ok" label="成功" />;
  }
  if (status === "error") {
    return <StatusTag status="error" label="失败" />;
  }
  if (status === "skip") {
    return <StatusTag status="warning" label="跳过" />;
  }
  return <StatusTag status="idle" label="未知" />;
}

function accountToForm(account: Account): AccountFormValues {
  return {
    id: account.id,
    platform: account.platform,
    enabled: account.enabled,
    ipGroup: account.ipGroup,
    activeHours: account.activeHours.map(([start, end]) => ({ start, end })),
    browserProvider:
      account.browserProvider ?? account.browser?.provider ?? "bitbrowser",
    bitbrowserProfileId: account.bitbrowserProfileId ?? "",
    proxyType: account.browser?.proxyType ?? "socks5",
    proxy: account.browser?.proxy ?? "",
    userDataDir: account.browser?.userDataDir ?? "",
    loginEnabled: account.login?.enabled ?? false,
    loginMethod: "password",
    loginUsername: account.login?.username ?? "",
    loginCredentialRef: account.login?.credentialRef ?? "",
    loginPassword: "",
    notes: account.notes ?? "",
  };
}

function formToAccount(
  values: AccountFormValues,
  existing: Account | null,
): Account {
  const provider = values.browserProvider ?? "bitbrowser";
  const profileId = values.bitbrowserProfileId?.trim() || undefined;
  const proxy = values.proxy?.trim() || undefined;
  const userDataDir = values.userDataDir?.trim() || undefined;
  return {
    ...existing,
    id: values.id.trim(),
    platform: values.platform,
    enabled: values.enabled,
    scheduled: existing?.scheduled ?? true,
    ipGroup: values.ipGroup,
    activeHours: values.activeHours.map((range) => [
      Number(range.start),
      Number(range.end),
    ]),
    browserProvider: provider,
    browser: {
      provider,
      profileId: provider === "bitbrowser" ? profileId : undefined,
      proxyType:
        provider === "builtin_chromium"
          ? (values.proxyType ?? "socks5")
          : undefined,
      proxy: provider === "builtin_chromium" ? proxy : undefined,
      userDataDir: provider === "builtin_chromium" ? userDataDir : undefined,
    },
    login: {
      enabled: Boolean(values.loginEnabled),
      method: "password",
      username: values.loginUsername?.trim() || undefined,
      credentialRef: values.loginCredentialRef?.trim() || undefined,
    },
    bitbrowserProfileId: provider === "bitbrowser" ? profileId : undefined,
    notes: values.notes?.trim() || undefined,
    lastRunAt: existing?.lastRunAt,
    lastStatus: existing?.lastStatus ?? "unknown",
  };
}

function upsertAccount(
  accounts: Account[],
  nextAccount: Account,
  existing: Account | null,
) {
  if (existing) {
    let replaced = false;
    const nextAccounts = accounts.map((account) => {
      if (account.id !== existing.id) {
        return account;
      }
      replaced = true;
      return nextAccount;
    });
    return replaced ? nextAccounts : [...accounts, nextAccount];
  }
  if (accounts.some((account) => account.id === nextAccount.id)) {
    return accounts.map((account) =>
      account.id === nextAccount.id ? nextAccount : account,
    );
  }
  return [...accounts, nextAccount];
}

function accountRegisterDisabledReason(
  account: Account,
  currentRunBusy: boolean,
  registeringAccountId: string | null,
  registeringBatch: boolean,
) {
  if (account.platform !== "tiktok") {
    return "仅 TikTok 账号支持注册";
  }
  if (currentRunBusy) {
    return "当前已有任务运行，请到任务输出面板停止或等待完成";
  }
  if (registeringBatch) {
    return "当前已有批量注册入口正在处理";
  }
  if (registeringAccountId && registeringAccountId !== account.id) {
    return "当前已有注册入口正在处理";
  }
  const provider = resolveBrowserProvider(account);
  if (
    provider === "bitbrowser" &&
    !account.bitbrowserProfileId &&
    !account.browser?.profileId
  ) {
    return `${account.id} 未绑定 BitBrowser profile`;
  }
  return undefined;
}

function batchRegisterDisabledReason(
  accounts: Account[],
  currentRunBusy: boolean,
  registeringAccountId: string | null,
  registeringBatch: boolean,
) {
  if (accounts.length === 0) {
    return "请先选择账号";
  }
  if (currentRunBusy) {
    return "当前已有任务运行，请到任务输出面板停止或等待完成";
  }
  if (registeringBatch) {
    return "当前已有批量注册入口正在处理";
  }
  if (registeringAccountId) {
    return "当前已有注册入口正在处理";
  }
  const blockedAccount = accounts
    .map((account) => ({
      account,
      reason: accountRegisterDisabledReason(account, false, null, false),
    }))
    .find(({ reason }) => Boolean(reason));
  if (blockedAccount?.reason) {
    return `${blockedAccount.account.id}: ${blockedAccount.reason}`;
  }
  return undefined;
}

function formatRegisterStartError(error: unknown) {
  const messageText = error instanceof Error ? error.message : String(error);
  return messageText.replace(
    /(password|credential|proxy password|token|cookie|session)\s*[:=]\s*[^,\s;]+/gi,
    "$1=[已隐藏]",
  );
}

function resolveBrowserProvider(account: Account): BrowserProviderId {
  return account.browserProvider ?? account.browser?.provider ?? "bitbrowser";
}

function validateActiveHourRows(
  form: ReturnType<typeof Form.useForm<AccountFormValues>>[0],
) {
  const ranges = form.getFieldValue("activeHours") as
    | AccountFormValues["activeHours"]
    | undefined;
  const invalid = ranges?.some((range) => {
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

function formatActiveHours(ranges: Account["activeHours"]) {
  if (!ranges.length) {
    return "-";
  }
  return ranges.map(([start, end]) => `${start}-${end}`).join(", ");
}

function ProxyCell({
  account,
  bitbrowserProfile,
  bitbrowserProfilesLoaded,
}: {
  account: Account;
  bitbrowserProfile?: BrowserProfile;
  bitbrowserProfilesLoaded: boolean;
}) {
  const localProxy = account.browser?.proxy?.trim();
  const bitbrowserProxy = bitbrowserProfile?.proxy?.trim();
  const provider = resolveBrowserProvider(account);

  if (provider === "bitbrowser") {
    return (
      <BitBrowserProxyCell
        localProxy={localProxy}
        bitbrowserProxy={bitbrowserProxy}
        profileFound={Boolean(bitbrowserProfile)}
        profilesLoaded={bitbrowserProfilesLoaded}
      />
    );
  }

  if (!localProxy) {
    return <Typography.Text type="secondary">-</Typography.Text>;
  }

  const proxyType = account.browser?.proxyType;
  const displayProxy = formatProxyDisplay(localProxy);

  return (
    <Space size={6} wrap>
      {proxyType ? <Tag>{proxyType}</Tag> : <Tag>本地</Tag>}
      <Typography.Text code ellipsis title={displayProxy}>
        {displayProxy}
      </Typography.Text>
    </Space>
  );
}

function BitBrowserProxyCell({
  localProxy,
  bitbrowserProxy,
  profileFound,
  profilesLoaded,
}: {
  localProxy?: string;
  bitbrowserProxy?: string;
  profileFound: boolean;
  profilesLoaded: boolean;
}) {
  const localDisplay = localProxy ? formatProxyDisplay(localProxy) : undefined;
  const bitbrowserDisplay = bitbrowserProxy
    ? formatProxyDisplay(bitbrowserProxy)
    : undefined;

  if (!profilesLoaded) {
    return localDisplay ? (
      <ProxyDisplay
        status="本地"
        color="gold"
        value={localDisplay}
        detail="BitBrowser 代理同步失败"
      />
    ) : (
      <Typography.Text type="secondary">同步失败</Typography.Text>
    );
  }
  if (!profileFound) {
    return <Typography.Text type="secondary">未找到窗口</Typography.Text>;
  }
  if (!localDisplay && !bitbrowserDisplay) {
    return <Typography.Text type="secondary">-</Typography.Text>;
  }
  if (bitbrowserDisplay && !localDisplay) {
    return (
      <ProxyDisplay
        status="BitBrowser"
        color="blue"
        value={bitbrowserDisplay}
      />
    );
  }
  if (localDisplay && !bitbrowserDisplay) {
    return (
      <ProxyDisplay
        status="本地"
        color="gold"
        value={localDisplay}
        detail="BitBrowser 未返回代理"
      />
    );
  }
  if (localDisplay && bitbrowserDisplay && localDisplay === bitbrowserDisplay) {
    return (
      <ProxyDisplay status="已同步" color="green" value={bitbrowserDisplay} />
    );
  }
  if (!localDisplay || !bitbrowserDisplay) {
    return <Typography.Text type="secondary">-</Typography.Text>;
  }
  return (
    <Space direction="vertical" size={2}>
      <ProxyDisplay status="不一致" color="gold" value={bitbrowserDisplay} />
      <Typography.Text type="secondary" title={localDisplay}>
        本地 {localDisplay}
      </Typography.Text>
    </Space>
  );
}

function ProxyDisplay({
  status,
  color,
  value,
  detail,
}: {
  status: string;
  color: string;
  value: string;
  detail?: string;
}) {
  return (
    <Space size={6} wrap>
      <Tag color={color}>{status}</Tag>
      <Typography.Text
        code
        ellipsis
        title={detail ? `${value}；${detail}` : value}
      >
        {value}
      </Typography.Text>
    </Space>
  );
}

function formatProxyDisplay(proxy: string) {
  const trimmed = proxy.trim();

  try {
    const value = trimmed.includes("://") ? trimmed : `proxy://${trimmed}`;
    const url = new URL(value);
    if (url.hostname && url.port) {
      return `${url.hostname}:${url.port}`;
    }
  } catch {
    // Fall back to colon-delimited proxy formats such as host:port:user:pass.
  }

  const parts = trimmed.split(":");
  if (parts.length >= 2) {
    return `${parts[0]}:${parts[1]}`;
  }
  return trimmed;
}

function profileForAccount(
  account: Account,
  profiles: Map<string, BrowserProfile>,
) {
  const profileId = account.bitbrowserProfileId ?? account.browser?.profileId;
  return profileId ? profiles.get(profileId) : undefined;
}

function nextAccountId(accounts: Account[], platform: Platform) {
  const used = new Set(accounts.map((account) => account.id));
  const prefix = `${platform}_`;
  for (
    let index = accounts.length + 1;
    index < accounts.length + 1000;
    index += 1
  ) {
    const id = `${prefix}${index}`;
    if (!used.has(id)) {
      return id;
    }
  }
  return `${prefix}new`;
}

function statusColor(status: string) {
  if (status === "ok") {
    return "green";
  }
  if (status === "error" || status === "fail" || status === "failed") {
    return "red";
  }
  if (status === "skip") {
    return "gold";
  }
  return "default";
}
