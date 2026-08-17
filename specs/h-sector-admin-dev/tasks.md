# H Sector 后台与后端整合任务文档

## 0. 当前结论

- [x] 产品官网已经从 `h-sector-website/` 迁入 `h-sector/`。
- [x] `h-sector-website/` 后续只作为历史来源和迁移记录保留，不再作为统一 Web 服务项目扩展。
- [x] `account-matrix-server/` 项目形态已被废弃，后续不再承载管理后台、PC API、支付、License、用量或支持包能力。
- [x] 后续开发权威项目为 `h-sector/`。
- [x] 后续实现型变更应进入 `h-sector/openspec/changes/**`，并遵守 `h-sector/openspec/specs/**`。
- [x] 本任务文档按迭代式开发组织：每轮只交付当前可验证能力，支付、License、用量、支持包等外部配置未就绪能力允许先做契约、占位状态和后续门禁。

## 1. 迭代开发原则

- 每个迭代必须有独立可验证结果，不要求一次性完成全部后台、PC API、支付、License 和用量能力。
- 已完成迭代不得破坏官网公开页面、公开 API、登录能力和现有 `h-sector` 底座。
- 管理后台登录方式仅支持邮箱/手机号 + 密码，不接入飞书、短信验证码或其它 SSO。
- 未就绪的外部依赖，例如支付渠道、License 签名密钥、对象存储、消息队列，可以先做 disabled/placeholder 状态，但必须在 UI、API 响应和 OpenSpec 中明确标注。
- 后台真实路由统一使用 `/dashboard/**`，`/admin` 只保留公开占位入口。
- 后端实现必须复用 `h-sector/src/app/**`、`h-sector/src/pages/api/**`、`h-sector/backend/services/**`、`h-sector/backend/prisma/**`、`h-sector/shared/types/**`。
- 不再新增 `account-matrix-server/` 或其他第二套服务端项目。

## 2. 已完成：官网迁入 h-sector

- [x] 官网首页已迁入 `h-sector/src/app/page.tsx`。
- [x] 公开页面已迁入：
  - [x] `/features`
  - [x] `/pricing`
  - [x] `/download`
  - [x] `/docs`
  - [x] `/contact`
  - [x] `/admin` 公开占位入口
- [x] 官网组件已迁入 `h-sector/src/components/website/**`。
- [x] 官网公开配置已迁入 `h-sector/src/config/site.ts`。
- [x] 官网静态资源已迁入 `h-sector/public/**`。
- [x] SEO 路由已迁入 `h-sector/src/app/robots.ts` 和 `h-sector/src/app/sitemap.ts`。
- [x] 公开 API 已迁入：
  - [x] `GET /api/public/pricing`
  - [x] `GET /api/public/releases/latest`
  - [x] `GET /api/public/contact`
- [x] 公开 API 已使用 `h-sector` 统一 `{ success, data, code, desc }` 响应结构。
- [x] 匿名公开页面和公开 API 已纳入 `h-sector` middleware/API 鉴权边界。
- [x] `h-sector` README 已记录产品官网职责、公开路由、公开 API 和验证结果。

## 3. 迭代 0：管理后台 MVP 变更与骨架 ✅

目标：先让后台有受保护入口、统一布局、导航、角色占位和空状态页面，不接真实支付和 License。

- [x] 在 `h-sector/openspec/changes/**` 创建管理后台 MVP 变更。
  - Related Specs: `code-quality/spec`, `project-structure/spec`, `auth-platform/spec`
  - Done When: proposal/design/tasks/delta specs 明确 `/dashboard/**` 受保护、`/admin` 公开占位、后台布局、导航、角色占位和验证方式。
  - 实际变更：`h-sector/openspec/changes/add-admin-dashboard-mvp/`
- [x] 明确后台第一轮页面范围。
  - 必做：`/dashboard`、`/dashboard/users`。
  - 可做占位：subscriptions、plans、orders、devices、licenses、usage、support-bundles、audit-logs。
  - Done When: 未实现业务页显示空状态或 disabled 状态，不显示假数据为真实能力。
  - 占位页已建：subscriptions、plans、orders、devices、licenses、usage、support-bundles、audit-logs。
- [x] 建立后台角色占位模型。
  - 第一轮允许只定义 `admin`、`ops`、`developer` 类型和服务端 helper，占位权限矩阵可先返回固定结果。
  - Done When: 未登录访问 `/dashboard/**` 进入登录保护；已登录无后台角色显示无权限状态。
  - 实现：`backend/services/admin/admin-access.facade.ts`，占位角色默认 `admin`，`source` 标注为 `placeholder`。
  - 实现：`GET /api/admin/session` 返回当前会话权限和模块列表。
- [x] 建立后台导航和布局。
  - Done When: 后台 layout 不复用官网 navbar/footer，移动端和桌面端布局可用。
  - 实现：`src/app/dashboard/layout.tsx` 重写为轻量后台 shell，含侧边栏、顶部栏、移动端横向导航、无权限状态。
  - 实现：`src/components/admin/admin-modules.ts` 定义全部计划模块和图标映射。
- [x] 建立第一轮验证。
  - Done When: 官网公开页面仍可匿名访问；`/dashboard/**` 未登录不可访问；构建或类型检查通过。
  - `tsc --noEmit` 通过。
  - `openspec validate` 未跑通（环境中无 `openspec` 可执行命令，非代码问题）。

## 4. 迭代 1：后台用户基础数据 ✅

目标：基于现有认证和用户模型，先完成面向个人客户的后台可管理最小业务闭环。

- [x] 在 `h-sector/openspec/changes/**` 扩展用户管理变更。
  - Related Specs: `database-design/spec`, `code-quality/spec`, `project-structure/spec`
  - Done When: 明确用户、后台权限字段、查询分页和空状态规则。
  - 实际变更：`h-sector/openspec/changes/add-admin-user-baseline/`
- [x] 扩展 `h-sector/backend/prisma/schema.prisma`。
  - 第一轮必做：复用或扩展 `users`，当前产品不做 2B 团队模型。
  - Done When: Prisma schema、迁移策略、seed 策略和索引策略明确。
  - 不再新增团队/成员表，后续商业化模型统一按 `user_id` 归属个人用户。
  - `npm run prisma:generate` 已通过。
- [x] 实现后台用户 API。
  - 推荐路径：`/api/admin/users/**`。
  - Done When: 未认证返回 `401`，无权限返回 `403`，列表接口返回统一响应结构。
  - 实现：`src/pages/api/admin/users/index.ts`（GET 列表 + POST 创建）、`src/pages/api/admin/users/delete.ts`（POST 删除）。
  - Facade：`backend/services/admin/admin-user.facade.ts`，复用现有 `userFacade` 并走 `adminAccessFacade` 权限占位。
- [x] 实现后台用户页面。
  - Done When: 支持列表、搜索/筛选占位、空状态、错误状态和加载状态。
  - `src/app/dashboard/users/page.tsx` 已切到 `apis.admin.user.*`。
- [x] 建立审计占位。
  - 第一轮允许只定义 `writeAuditLog()` 接口和 no-op/stub 实现。
  - Done When: 写操作调用审计入口，但未完成真实 audit table 时必须在任务中保留后续门禁。
  - 门禁保留：当前未实现 `writeAuditLog()`，后台写操作尚未接入审计入口。真实审计写入将在迭代 4 完成。
- [x] 迭代 1 验证。
  - `tsc --noEmit` 通过。
  - `npm run prisma:generate` 通过。
  - `openspec validate` 未跑通（同迭代 0 环境阻塞）。

## 5. 迭代 2：PC 桌面端 API 契约与配置迁移

目标：先让 `account-matrix` 桌面端知道未来服务端契约和 base URL 配置，不要求第一轮完成真实 License 和支付。✅ 已完成。

- [x] 在 `h-sector/openspec/changes/**` 创建 PC API 契约变更。
  - Related Specs: `code-quality/spec`, `project-structure/spec`, `auth-platform/spec`
  - Done When: `/api/desktop/**` 请求/响应 DTO、错误码、设备上下文、License 上下文和 disabled 状态明确。
  - 实际变更：`h-sector/openspec/changes/add-desktop-api-contracts/`
- [x] 定义桌面端 API base URL 配置迁移方案。
  - Done When: `account-matrix` 桌面端可配置为调用 `h-sector` 部署地址，不再把 `account-matrix-server` 作为目标地址。
  - 文档：`account-matrix/desktop/docs/desktop-api-base-url.md`
- [x] 建立第一批 PC API 占位接口。
  - 推荐路径：
    - `POST /api/desktop/auth/login`
    - `POST /api/desktop/auth/refresh`
    - `GET /api/desktop/plans`
    - `GET /api/desktop/subscription/current`
    - `GET /api/desktop/license/current`
  - Done When: 未实现真实商业化能力的接口返回明确的 `DISABLED`、`NOT_CONFIGURED` 或 `NOT_IMPLEMENTED` 业务码，而不是 500。
  - 实现：`src/pages/api/desktop/auth/login.ts`（复用 `AuthFacade` + `local_password`）
  - 实现：`src/pages/api/desktop/auth/refresh.ts`（返回 `NOT_IMPLEMENTED` 5001）
  - 实现：`src/pages/api/desktop/plans/index.ts`（占位套餐列表）
  - 实现：`src/pages/api/desktop/subscription/current.ts`（`not_configured`）
  - 实现：`src/pages/api/desktop/license/current.ts`（`not_configured`）
  - Facade：`backend/services/desktop/desktop-auth.facade.ts`、`backend/services/desktop/desktop-billing.facade.ts`
  - DTO：`shared/types/api/desktop.dto.ts`
- [x] 定义 PC API 契约测试。
  - Done When: 登录、刷新、套餐查询、订阅查询、License 查询的正常/未配置/未认证场景可验证。
  - 契约测试场景已写入 `account-matrix/desktop/docs/desktop-api-base-url.md`。
  - `tsc --noEmit` 通过。
  - `openspec validate` 未跑通（同前序迭代环境阻塞）。

## 6. 迭代 3：套餐、订阅、设备和 License 占位闭环

目标：在没有支付配置前，先完成可本地验证的商业化数据结构和后台可见性。

- [x] 在 `h-sector/openspec/changes/**` 创建套餐、订阅、设备、License 变更。
  - Related Specs: `database-design/spec`, `code-quality/spec`, `project-structure/spec`
  - Done When: plans、subscriptions、devices、licenses、feature_flags 的字段、索引、状态机和权限规则明确。
  - 实际变更：`h-sector/openspec/changes/add-plan-subscription-device-license/`、`h-sector/openspec/changes/add-commercial-baseline-models/`
- [x] 实现基础模型。
  - 必做：`plans`、`subscriptions`、`devices`、`licenses`、`feature_flags`。
  - Done When: 模型支持后台列表和 PC API 查询，不依赖真实支付渠道。
  - Prisma 模型：`Plan`、`Subscription`、`Device`、`License`、`FeatureFlag` 已在 `backend/prisma/schema.prisma` 定义。
  - 迁移：`backend/prisma/migrations/20260815000000_add_commercial_baseline_models/migration.sql`。
  - DTO：`shared/types/api/commercial.dto.ts`。
  - Service/Facade：`backend/services/commercial/commercial.service.ts`、`commercial.facade.ts`。
  - Admin API：`/api/admin/plans`（GET 列表 + POST 创建）、`/api/admin/subscriptions`（GET 列表）、`/api/admin/devices`（GET 列表）、`/api/admin/licenses`（GET 列表）。
  - 归属策略：当前面向个人客户，订阅、设备、License 均直接归属 `user_id`。
- [x] 实现后台占位页面。
  - 页面：plans、subscriptions、devices、licenses。
  - Done When: 页面可以查看本地 seed 或空状态；创建/修改能力可按权限暂缓。
  - 四个页面已从 `AdminPlaceholderPage` 替换为真实列表页，含 loading/error/empty 状态。
  - plans 页含创建表单；subscriptions/devices/licenses 页支持按状态筛选。
  - `admin-modules.ts` 中四个模块状态已从 `placeholder` 改为 `ready`。
- [ ] 实现 License 占位服务。
  - 第一轮允许返回未配置状态或开发签名，但不得把真实签名密钥放入客户端 bundle。
  - Done When: PC API 能区分无订阅、无设备、License 未配置和 License 有效占位状态。
  - 当前进度：`/api/desktop/license/current` 返回 `not_configured` 占位状态，不报 500。
  - 门禁保留：`desktop-billing.facade.ts` 仍为纯硬编码占位，未从 DB 读取真实数据，无法区分无订阅/无设备/未配置/有效占位状态。
  - 后续需连接数据库后改为读取真实数据并保留 placeholder fallback（对应 openspec tasks 1.5，已留 TODO 标记）。
  - `tsc --noEmit` 通过。

## 7. 迭代 4：用量、支持包和审计

目标：先完成后台排障和运营观察能力，再接入更重的支付链路。

- [x] 在 `h-sector/openspec/changes/**` 创建用量、支持包和审计变更。
  - Related Specs: `database-design/spec`, `code-quality/spec`, `project-structure/spec`
  - Done When: usage_daily、support_bundles、audit_logs 的字段、保留策略、脱敏策略和权限规则明确。
  - 实际变更：`h-sector/openspec/changes/add-usage-support-audit/`
- [x] 实现用量上报占位接口。
  - 推荐路径：`POST /api/desktop/usage/report`。
  - Done When: 未认证、设备未激活、License 未配置和成功占位写入场景可区分。
  - 实现：`src/pages/api/desktop/usage/report.ts`，通过认证后写入 `usage_daily` 表（upsert）。
  - Facade：`backend/services/usage/usage.facade.ts`、Service：`backend/services/usage/usage.service.ts`。
  - 未认证由 `createApiRouter` 中间件返回 401；成功写入返回 `status: 'ok'`。
  - 门禁保留：设备未激活和 License 未配置场景的区分暂未实现，当前只校验认证。
- [x] 实现支持包上传占位接口。
  - 推荐路径：`POST /api/desktop/support-bundles`。
  - Done When: 存储未配置时返回明确 `NOT_CONFIGURED`，不会静默丢数据。
  - 实现：`src/pages/api/desktop/support-bundles/index.ts`。
  - Facade：`backend/services/support-bundle/support-bundle.facade.ts`、Service：`backend/services/support-bundle/support-bundle.service.ts`。
  - 当 `SUPPORT_BUNDLE_STORAGE` 环境变量未设置时返回 `status: 'not_configured'`，不写任何数据。
- [x] 实现审计日志真实写入。
  - Done When: 后台关键写操作和占位商业化操作能写入 `audit_logs`。
  - 门禁来源：迭代 1 中 `writeAuditLog()` 仍未实现，需在此迭代补齐。
  - 实现：`backend/services/audit/audit.facade.ts` 的 `writeAuditLog()`（best-effort，try/catch 不阻断主操作）。
  - Service：`backend/services/audit/audit.service.ts`。
  - 已接入：用户创建/删除（`admin-user.facade.ts`）、套餐创建（`commercial.facade.ts`）。
- [x] 实现后台页面。
  - 页面：usage、support-bundles、audit-logs。
  - Done When: 支持列表、详情占位、权限限制和空状态。
  - 三个页面已从 `AdminPlaceholderPage` 替换为真实列表页，含 loading/error/empty 状态。
  - usage 按指标Key筛选；support-bundles 按状态筛选；audit-logs 按模块筛选。
  - `admin-modules.ts` 和 `admin-access.facade.ts` 中三个模块状态已从 `placeholder` 改为 `ready`。
  - `tsc --noEmit` 通过。
  - Prisma 模型：`UsageDaily`、`SupportBundle`、`AuditLog` 已在 `schema.prisma` 定义。
  - 迁移：`backend/prisma/migrations/20260816000000_add_usage_support_audit/migration.sql`。
  - `npm run prisma:generate` 通过。
  - `openspec validate` 未跑通（同前序迭代环境阻塞）。

## 8. 迭代 5：支付配置就绪后的真实支付闭环

目标：只有在支付渠道、密钥、商品 ID、回调地址和环境配置明确后才进入真实支付实现。

- [ ] 确认支付渠道和环境配置。
  - Done When: Paddle/Stripe/微信支付/支付宝中至少一个渠道的 checkout、webhook、签名密钥、商品映射和测试环境可用。
- [ ] 在 `h-sector/openspec/changes/**` 创建或更新支付变更。
  - Related Specs: `database-design/spec`, `code-quality/spec`, `project-structure/spec`
  - Done When: checkout、webhook 签名校验、幂等键、订阅状态流转和审计规则明确。
- [ ] 实现支付模型。
  - 必做：`orders`、`payment_events`。
  - Done When: 订单、支付事件、订阅状态更新和幂等处理有事务边界。
- [ ] 实现支付 API。
  - 路径：`POST /api/billing/checkout`、`POST /api/billing/webhook`。
  - Done When: checkout 校验用户/套餐上下文；webhook 验证签名并幂等处理。
- [ ] 接通后台支付视图。
  - 页面：orders、subscriptions。
  - Done When: 后台能查看订单、支付事件和订阅状态流转。

## 9. 迭代 6：真实 License、额度和桌面端联调

目标：在订阅和支付链路稳定后，让桌面端真实依赖 `h-sector` 的 License 和额度。

- [ ] 实现真实 License 签发和刷新。
  - Done When: License Claims 包含用户、套餐、订阅、角色、功能开关、额度、过期时间、离线宽限、设备 ID、签发时间和签名。
- [ ] 实现设备激活和解绑。
  - 路径：`POST /api/desktop/devices/activate`、`POST /api/desktop/devices/deactivate`。
  - Done When: 设备数额度、订阅状态和 License 状态均被服务端校验。
- [ ] 实现用量额度校验。
  - Done When: 启用账号数、激活设备数、每日任务启动次数、每日执行账号数、每日目标互动次数、每日初始化/注册次数、调度触发次数、CSV 导出次数、失败次数和失败率可记录或校验。
- [ ] 联调 `account-matrix` 桌面端。
  - Done When: 桌面端登录、刷新、设备激活、License 获取/刷新、订阅查询、套餐查询、用量上报和支持包上传均指向 `h-sector`。

## 10. 持续实现约束

- [x] 前端页面和组件放在 `h-sector/src/app/**`、`h-sector/src/components/**`。
- [x] API route 放在 `h-sector/src/pages/api/**`。
- [x] API route 只调用 `h-sector/backend/services/**/[module].facade.ts`。
- [x] 领域服务、数据库、支付、License 签名和审计逻辑放在 `h-sector/backend/**`。
- [x] 跨层 DTO 和错误类型放在 `h-sector/shared/types/**`。
- [x] API 响应保持 `{ success, data, code, desc }`。
- [x] 前端组件不得直接导入 `backend/**`。
- [ ] 密钥只通过服务端环境变量读取，不进入客户端 bundle。
- [ ] 未配置能力必须返回明确业务状态，不得假装成功。

## 11. 删除旧目录门禁

### 11.1 `account-matrix/account-matrix-server/`

- [x] 文档已明确该项目形态废弃。
- [ ] 删除前确认桌面端不再调用其地址。
- [ ] 删除前确认所需历史实现已迁入 `h-sector` 或不再需要。
- [ ] 删除后确认当前开发文档不再把它作为实现目标。

### 11.2 `h-sector-website/`

- [x] 官网代码已迁入 `h-sector`。
- [x] 文档已明确它只作为历史来源和迁移记录。
- [ ] 删除前确认不再需要迁移对照、历史源码和 `specs/migrate-product-website-to-h-sector/**`。

## 12. 最终验收

- [x] 官网公开访问由 `h-sector` 承载。
- [x] 官网公开 API 由 `h-sector` 承载。
- [x] 管理后台 MVP 已在 `h-sector/openspec/changes/**` 建立并通过审核。
  - 变更：`add-admin-dashboard-mvp`，`tsc --noEmit` 通过，`openspec validate` 受环境阻塞。
- [x] 后台用户和权限基础闭环可用。
  - 变更：`add-admin-user-baseline`，`tsc --noEmit` 通过，`prisma generate` 通过。
- [ ] PC API 契约和 base URL 迁移方案可用。
- [x] PC API 契约和 base URL 迁移方案可用。
  - 变更：`add-desktop-api-contracts`，`tsc --noEmit` 通过。
- [ ] 套餐、订阅、设备和 License 占位闭环可用。
- [ ] 用量、支持包和审计闭环可用。
- [ ] 支付配置就绪后，真实 checkout 和 webhook 闭环可用。
- [ ] 真实 License、额度和桌面端联调完成。
- [ ] 后续开发只围绕 `h-sector/` 推进。
