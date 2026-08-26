import { Alert, Button, Result, Spin } from "antd";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { DesktopLoginPage } from "../pages/DesktopLoginPage";
import { setLicenseEntitlements } from "../services/api";
import {
  activateDesktopDevice,
  buildDesktopSession,
  clearDesktopSession,
  deactivateDesktopDevice,
  getDeviceFingerprint,
  desktopLogin,
  getDesktopApiBaseUrl,
  loadCurrentSubscription,
  loadDesktopSession,
  loadVerifiedCurrentLicense,
  readDesktopLicenseLimits,
  saveDesktopApiBaseUrl,
  saveDesktopSession,
  type DesktopDeviceResponse,
  type DesktopLicenseCurrentResponse,
  type DesktopSession,
  type DesktopSubscriptionCurrentResponse,
} from "../services/desktopApi";

const ENTITLEMENT_POLL_MS = 10 * 1000;

interface DesktopAuthContextValue {
  apiBaseUrl: string;
  session: DesktopSession | null;
  device: DesktopDeviceResponse | null;
  subscription: DesktopSubscriptionCurrentResponse | null;
  license: DesktopLicenseCurrentResponse | null;
  loading: boolean;
  error: string | null;
  entitlementWarning: string | null;
  login: (values: {
    apiBaseUrl: string;
    username: string;
    password: string;
  }) => Promise<{ authorized: boolean }>;
  refreshEntitlement: () => Promise<void>;
  unbindCurrentDevice: () => Promise<void>;
  logout: () => void;
}

const DesktopAuthContext = createContext<DesktopAuthContextValue | null>(null);

export function DesktopAuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [apiBaseUrl, setApiBaseUrl] = useState(getDesktopApiBaseUrl);
  const [session, setSession] = useState<DesktopSession | null>(null);
  const [device, setDevice] = useState<DesktopDeviceResponse | null>(null);
  const [subscription, setSubscription] =
    useState<DesktopSubscriptionCurrentResponse | null>(null);
  const [license, setLicense] = useState<DesktopLicenseCurrentResponse | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [entitlementWarning, setEntitlementWarning] = useState<string | null>(
    null,
  );

  const clearRuntimeState = useCallback(() => {
    setSession(null);
    setDevice(null);
    setSubscription(null);
    setLicense(null);
  }, []);

  const hydrateEntitlement = useCallback(
    async (nextSession: DesktopSession, nextApiBaseUrl = apiBaseUrl) => {
      const nextSubscription = await loadCurrentSubscription(
        nextSession,
        nextApiBaseUrl,
      );
      setSubscription(nextSubscription);

      if (nextSubscription.status !== "active") {
        const unavailableLicense =
          buildUnavailableLicense("当前账号没有有效订阅");
        setDevice(null);
        setLicense(unavailableLicense);
        return {
          subscription: nextSubscription,
          license: unavailableLicense,
        };
      }

      const nextDevice = await activateDesktopDevice(
        nextSession,
        nextApiBaseUrl,
      );
      const nextLicense = await loadVerifiedCurrentLicense(
        nextSession,
        nextApiBaseUrl,
      );
      setDevice(nextDevice);
      setLicense(nextLicense);
      return {
        subscription: nextSubscription,
        license: nextLicense,
      };
    },
    [apiBaseUrl],
  );

  const logout = useCallback(() => {
    clearDesktopSession();
    clearRuntimeState();
    setError(null);
    setEntitlementWarning(null);
  }, [clearRuntimeState]);

  const unbindCurrentDevice = useCallback(async () => {
    if (!session) return;

    setLoading(true);
    setError(null);
    setEntitlementWarning(null);
    try {
      await deactivateDesktopDevice(session, apiBaseUrl);
      logout();
    } catch (error) {
      const message = formatError(error);
      setError(message);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl, logout, session]);

  const refreshEntitlement = useCallback(async () => {
    if (!session) return;

    setLoading(true);
    setError(null);
    setEntitlementWarning(null);
    try {
      await hydrateEntitlement(session, apiBaseUrl);
    } catch (error) {
      const message = formatError(error);
      if (isTransientEntitlementError(message)) {
        setEntitlementWarning(message);
        return;
      }
      setError(message);
      setLicense(buildUnavailableLicense(message));
      throw error;
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl, hydrateEntitlement, session]);

  const login = useCallback(
    async (values: {
      apiBaseUrl: string;
      username: string;
      password: string;
    }) => {
      const nextApiBaseUrl = values.apiBaseUrl.trim();
      setLoading(true);
      setError(null);
      setEntitlementWarning(null);
      try {
        saveDesktopApiBaseUrl(nextApiBaseUrl);
        setApiBaseUrl(nextApiBaseUrl);
        const auth = await desktopLogin(
          values.username,
          values.password,
          nextApiBaseUrl,
        );
        const nextSession = buildDesktopSession(values.username, auth);
        saveDesktopSession(nextSession);
        setSession(nextSession);
        const entitlement = await hydrateEntitlement(
          nextSession,
          nextApiBaseUrl,
        );
        return {
          authorized:
            entitlement.subscription.status === "active" &&
            entitlement.license.status === "active",
        };
      } catch (error) {
        clearDesktopSession();
        clearRuntimeState();
        const message = formatError(error);
        setError(message);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    [clearRuntimeState, hydrateEntitlement],
  );

  useEffect(() => {
    const bootstrap = async () => {
      const saved = loadDesktopSession();
      if (!saved) {
        setLoading(false);
        return;
      }

      setSession(saved);
      try {
        await hydrateEntitlement(saved, apiBaseUrl);
      } catch (error) {
        const message = formatError(error);
        if (isTransientEntitlementError(message)) {
          setEntitlementWarning(message);
        } else {
          setError(message);
          setLicense(buildUnavailableLicense(message));
        }
      } finally {
        setLoading(false);
      }
    };

    void bootstrap();
  }, []);

  useEffect(() => {
    if (!session) return;

    const pollEntitlement = async () => {
      try {
        await hydrateEntitlement(session, apiBaseUrl);
        setEntitlementWarning(null);
        setError(null);
      } catch (error) {
        const message = formatError(error);
        if (isTransientEntitlementError(message)) {
          setEntitlementWarning(message);
          return;
        }
        setError(message);
        setLicense(buildUnavailableLicense(message));
      }
    };

    const id = window.setInterval(() => {
      void pollEntitlement();
    }, ENTITLEMENT_POLL_MS);

    return () => window.clearInterval(id);
  }, [apiBaseUrl, hydrateEntitlement, session]);

  useEffect(() => {
    const limits = readDesktopLicenseLimits(license);
    void setLicenseEntitlements({
      ...limits,
      apiBaseUrl,
      accessToken: session?.accessToken ?? "",
      deviceFingerprint: getDeviceFingerprint(),
    }).catch(() => undefined);
  }, [apiBaseUrl, license, session?.accessToken]);

  const value = useMemo(
    () => ({
      apiBaseUrl,
      session,
      device,
      subscription,
      license,
      loading,
      error,
      entitlementWarning,
      login,
      refreshEntitlement,
      unbindCurrentDevice,
      logout,
    }),
    [
      apiBaseUrl,
      device,
      entitlementWarning,
      error,
      license,
      loading,
      login,
      logout,
      refreshEntitlement,
      session,
      subscription,
      unbindCurrentDevice,
    ],
  );

  return (
    <DesktopAuthContext.Provider value={value}>
      {children}
    </DesktopAuthContext.Provider>
  );
}

export function DesktopAuthGate({ children }: { children: React.ReactNode }) {
  const auth = useDesktopAuth();

  if (auth.loading && !auth.session) {
    return (
      <div className="desktop-auth-loading">
        <Spin tip="正在检查授权..." />
      </div>
    );
  }

  if (!auth.session) {
    return (
      <DesktopLoginPage
        apiBaseUrl={auth.apiBaseUrl}
        error={auth.error}
        onLogin={auth.login}
      />
    );
  }

  if (auth.loading && (!auth.subscription || !auth.license)) {
    return (
      <div className="desktop-auth-loading">
        <Spin tip="正在检查订阅和授权..." />
      </div>
    );
  }

  if (auth.license?.status !== "active") {
    return (
      <div className="desktop-auth-result">
        <Result
          status="warning"
          title="当前账号暂无可用授权"
          subTitle={formatEntitlementDetail(
            auth.subscription?.status,
            auth.license?.status,
            auth.error,
          )}
          extra={[
            <Button
              key="refresh"
              type="primary"
              loading={auth.loading}
              onClick={() => void auth.refreshEntitlement()}
            >
              重新检查
            </Button>,
            <Button key="logout" onClick={auth.logout}>
              退出登录
            </Button>,
          ]}
        />
        {auth.error ? (
          <Alert type="error" showIcon message={auth.error} />
        ) : null}
      </div>
    );
  }

  return <>{children}</>;
}

export function useDesktopAuth() {
  const context = useContext(DesktopAuthContext);
  if (!context) {
    throw new Error("useDesktopAuth must be used inside DesktopAuthProvider");
  }
  return context;
}

function formatEntitlementDetail(
  subscriptionStatus?: DesktopSubscriptionCurrentResponse["status"],
  licenseStatus?: DesktopLicenseCurrentResponse["status"],
  error?: string | null,
) {
  if (error) return error;
  if (subscriptionStatus && subscriptionStatus !== "active") {
    return `订阅状态：${subscriptionStatus}`;
  }
  if (licenseStatus) {
    return `License 状态：${licenseStatus}`;
  }
  return "请确认该产品用户已创建有效订阅、当前设备已激活，并且 License 未过期。";
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}

function buildUnavailableLicense(
  reason: string,
): DesktopLicenseCurrentResponse {
  return {
    licenseId: null,
    status: "not_configured",
    claims: { reason },
    signature: null,
    algorithm: null,
    signedPayload: null,
    source: "configured",
  };
}

function isTransientEntitlementError(message: string) {
  return (
    message.includes("无法连接服务端") ||
    message.includes("网络") ||
    message.includes("请求失败：HTTP 5") ||
    message.includes("服务开了点小差") ||
    message.includes("请稍后")
  );
}
