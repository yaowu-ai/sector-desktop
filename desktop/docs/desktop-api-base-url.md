# 桌面端 API Base URL 配置

## 背景

从阶段 2 开始，桌面端应将服务端 API 指向 `h-sector` 部署地址，不再引用 `account-matrix-server`。

## 配置方式

桌面端通过环境变量或本地配置文件读取 `h-sector` 的部署地址：

| 环境 | 变量名 | 示例值 |
 | --- | --- | --- |
 | 开发 | `DESKTOP_API_BASE_URL` | `http://localhost:3000/api/desktop` |
 | 测试 | `DESKTOP_API_BASE_URL` | `https://test.example.com/api/desktop` |
 | 生产 | `DESKTOP_API_BASE_URL` | `https://app.example.com/api/desktop` |

## 可用接口（阶段 2 占位）

| 方法 | 路径 | 认证 | 状态 |
 | --- | --- | --- | --- |
 | POST | `/api/desktop/auth/login` | 否 | 可用，复用 `local_password` 策略 |
 | POST | `/api/desktop/auth/refresh` | 否 | `NOT_IMPLEMENTED`（5001） |
 | GET | `/api/desktop/plans` | 是 | 占位数据 |
 | GET | `/api/desktop/subscription/current` | 是 | `not_configured` |
 | GET | `/api/desktop/license/current` | 是 | `not_configured` |

## 契约测试场景

每个接口需覆盖以下场景：

1. **正常**：已认证且有数据时返回 `success: true`。
2. **未配置**：无数据时返回 `success: true` 且 `source: 'placeholder'` / `status: 'not_configured'`。
3. **未认证**：非 login 接口未携带 token 时返回 `401`。
4. **未实现**：refresh 接口返回 `code: 5001`，`desc: 'NOT_IMPLEMENTED'`。

## 迁移步骤

1. 在桌面端配置中新增 `DESKTOP_API_BASE_URL`。
2. 将登录流程从 Tauri 本地调用切到 `POST /api/desktop/auth/login`。
3. 在设置页展示套餐、订阅、License 的占位状态。
4. 后续迭代接入真实数据后移除占位标记。
