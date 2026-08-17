# h-sector 后台与后端整合设计文档

## 0. 文档状态

本文已在 2026-08-12 更新为 `h-sector/` 权威实现方案。

- `h-sector-website/` 现在只作为官网历史来源和迁移记录，不再作为后台、PC API 或支付能力的后续宿主。
- 产品官网已迁入 `h-sector/`。
- 管理后台、后台 API、PC 桌面端 API、支付、License、用量、支持包、审计和数据库模型后续均以 `h-sector/` 为实现项目。
- 具体实现变更应优先落到 `h-sector/openspec/changes/**`，并遵守 `h-sector/openspec/specs/**` 中的底座规范。

## 1. 概述

`h-sector/` 是公司通用 Next.js 全栈底座。整合完成后，它将同时承载：

- 公开官网。
- 管理后台。
- 后台 API。
- PC 桌面端 API。
- 支付 checkout 和 webhook。
- License、用量、支持包和审计。
- 数据库访问和领域服务。

`account-matrix-server/` 不再作为独立服务端项目保留。`h-sector-website/` 不再作为运行时宿主保留，只作为历史来源和迁移记录。

## 2. 设计原则

- 官网路由默认公开。
- 真实后台路由默认受保护，推荐放在 `h-sector` 现有 `/dashboard/**` 命名空间。
- `/admin` 已作为公开占位入口迁入 `h-sector`，不承载真实后台数据。
- 后台 API、PC API、billing API 默认受保护或校验签名。
- 所有敏感逻辑只能存在 `backend/` 服务端模块。
- API route 只能调用 Facade，Facade 再调度领域 Service。
- 后台、PC API、支付、License 和用量共用同一套领域模型。
- 官网组件和后台组件分离，避免样式和依赖互相污染。
- 完成后项目不能依赖 `account-matrix-server/` 或 `h-sector-website/` 中的任何运行时代码。

## 3. 技术栈

```text
语言：TypeScript
包管理：npm
框架：Next.js 15 App Router + Pages Router API
官网 UI：已迁入的 Tailwind CSS 官网组件
后台 UI：优先沿用 h-sector 现有组件体系；如需 Ant Design，需另开 OpenSpec 变更评估
认证：沿用 h-sector 现有账号密码认证、middleware 和 createApiRouter 能力
数据库：MySQL，沿用当前 `h-sector/backend/prisma/schema.prisma` 的 datasource 和现有 MySQL 迁移 SQL 口径
ORM：Prisma
支付：Paddle/Stripe/微信支付/支付宝，按市场确认
缓存/队列：Redis，仅在明确需要时引入
```

## 4. 目标目录结构

```text
h-sector/
  src/
    app/
      page.tsx
      features/
      pricing/
      download/
      docs/
      contact/
      admin/
        page.tsx             # 公开占位入口
      dashboard/
        page.tsx
        users/
        subscriptions/
        plans/
        orders/
        devices/
        licenses/
        usage/
        support-bundles/
        audit-logs/
    pages/
      api/
        public/
        admin/
        desktop/
        billing/
    components/
      website/
    config/
      site.ts
    lib/
      apiRouter.ts
      request.ts
  backend/
    services/
      public-site/
      admin/
      desktop/
      billing/
      devices/
      licenses/
      usage/
      support/
      audit/
    lib/
    prisma/
      schema.prisma
      migrations/
      seed.ts
  shared/
    types/
      api/
```

## 5. 路由设计

### 5.1 公开官网

```text
/                         产品首页
/features                 功能页
/pricing                  价格页
/download                 下载页
/docs                     文档页
/contact                  联系页
/admin                    公开占位入口
/api/public/*             官网公开只读 API
```

公开官网不得依赖用户登录状态。公开 API 只能返回适合匿名访客访问的数据，并使用 `h-sector` 统一 `{ success, data, code, desc }` 响应结构。

### 5.2 管理后台

```text
/dashboard
/dashboard/users
/dashboard/subscriptions
/dashboard/plans
/dashboard/orders
/dashboard/devices
/dashboard/licenses
/dashboard/usage
/dashboard/support-bundles
/dashboard/audit-logs
```

访问规则：

- `/login` 允许未登录访问。
- 登录方式仅支持邮箱/手机号/用户名 + 密码，不接入飞书、短信验证码或其它 SSO。
- `/dashboard/*` 默认需要登录和后台角色。
- 已登录但无后台角色显示 403 或无权限状态。
- 后台 layout 不复用官网 navbar/footer。

### 5.3 后台 API

```text
/api/admin/*
```

访问规则：

- 未认证返回 `401`。
- 已认证但无权限返回 `403`。
- 写操作必须记录审计日志。
- API 文件放在 `src/pages/api/admin/**`，只调用 `backend/services/**/[module].facade.ts`。

### 5.4 PC 桌面端 API

```text
POST /api/desktop/auth/login
POST /api/desktop/auth/refresh
POST /api/desktop/devices/activate
POST /api/desktop/devices/deactivate
GET  /api/desktop/license/current
POST /api/desktop/license/refresh
GET  /api/desktop/subscription/current
GET  /api/desktop/plans
POST /api/desktop/usage/report
POST /api/desktop/support-bundles
```

访问规则：

- 登录接口校验用户身份。
- 设备、License、订阅、用量和支持包接口必须校验用户上下文。
- 敏感能力必须校验设备激活、订阅状态、License 和套餐额度。
- 桌面端 API base URL 指向 `h-sector/` 的部署地址。

### 5.5 支付 API

```text
POST /api/billing/checkout
POST /api/billing/webhook
```

访问规则：

- checkout 必须校验用户和套餐上下文。
- webhook 必须校验支付渠道签名。
- webhook 必须幂等处理。

## 6. 服务端分层设计

所有敏感服务放在 `backend/` 下。API 路由只能调用 Facade，Facade 负责参数校验、权限检查、日志记录和事务调度，复杂业务逻辑下沉到 Domain Service。

建议模块：

```text
backend/services/auth/
backend/services/permissions/
backend/services/audit/
backend/services/users/
backend/services/plans/
backend/services/subscriptions/
backend/services/orders/
backend/services/billing/
backend/services/devices/
backend/services/licenses/
backend/services/usage/
backend/services/support/
backend/lib/errors/
backend/lib/contracts/
backend/prisma/
```

必须提供的 helper：

```text
requireUser()
requireAdminRole()
requireAdminPermission(permission)
requireDesktopSession()
requireActivatedDevice()
requireValidLicense()
writeAuditLog(action, resource, metadata)
```

## 7. 数据模型设计

第一版数据库表：

- `users`
- `plans`
- `subscriptions`
- `orders`
- `payment_events`
- `devices`
- `licenses`
- `usage_daily`
- `feature_flags`
- `support_bundles`
- `audit_logs`

这些模型同时服务管理后台、PC 桌面端 API、License 签发和刷新、用量统计、支付状态流转、支持包和排障。

## 8. 鉴权与权限设计

后台角色：

```ts
type AdminRole = "admin" | "ops" | "developer";
```

PC 端角色：

```ts
type DesktopRole = "normal" | "advanced" | "developer";
```

权限原则：

- 角色决定用户类型。
- 功能开关和额度决定付费能力。
- 前端菜单隐藏只改善体验，不能作为安全边界。
- 后台 API、PC API 和 billing API 都必须在服务端校验。

## 9. 与桌面端集成

桌面端契约必须保持：

- 登录。
- 刷新。
- 设备激活。
- License 获取和刷新。
- 订阅查询。
- 套餐查询。
- 用量上报。
- 支持包上传。

如果接口路径从旧设计迁移到 `/api/desktop/*`，需要为桌面端提供清晰的配置项或兼容层。

## 10. 删除旧项目设计

删除 `account-matrix-server/` 前必须完成：

1. `h-sector/` 不导入 `account-matrix-server/` 或 `h-sector-website/` 的任何运行时代码。
2. 桌面端不再调用 `account-matrix-server/` 的地址。
3. 后台、PC API、billing、License、usage、support、audit 均已在 `h-sector/` 中实现或替代。
4. 数据库迁移、环境变量和部署文档已转移。
5. `specs/account-matrix-server/` 不再被当前 spec 引用，可作为旧方案归档目录删除。

删除方式应在最终验收后单独执行，不和业务迁移混在同一次不受控变更中。

## 11. 安全设计

- 使用服务端环境变量保存数据库、支付、License 签名等密钥。
- 使用 `backend/` 模块隔离数据库和密钥访问。
- `src/` 前端页面和组件不得直接导入 `backend/*`；只有 `src/pages/api/**` 可以导入 Facade。
- `/dashboard/*` 和 `/api/admin/*` 默认 deny。
- `/api/desktop/*` 校验用户、设备和 License。
- `/api/billing/webhook` 校验签名和事件幂等性。
- 支持包默认脱敏。

## 12. 验证方案

必须验证：

- 官网六个公开页面。
- `/api/public/*`。
- `/login`。
- `/dashboard/*` 未登录保护。
- `/api/admin/*` 401/403。
- `/api/desktop/*` 认证、设备、License 和额度校验。
- `/api/billing/webhook` 签名和幂等。
- `h-sector` 构建或类型验证。
- 客户端 bundle 不包含后端密钥或服务端代码。

## 13. 风险与取舍

- 整合后不能再按纯静态官网部署。
- 官网和后台共享同一个 Next.js 项目，依赖和样式必须隔离。
- 如果一次性迁移所有后端能力，风险高；建议按阶段迁移并保持每阶段可验证。
- 删除 `account-matrix-server/` 前必须完成桌面端 API 地址切换和所有 spec 修订。
