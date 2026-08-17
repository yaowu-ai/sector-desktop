# H Sector 后台与后端整合需求文档

## 0. 文档状态

本文已在 2026-08-12 更新为 `h-sector/` 权威实现方案。

- `h-sector-website/` 已不再作为统一 Web 服务项目继续扩展；它现在只保留为产品官网迁移前的历史来源和迁移记录。
- 产品官网已迁入 `h-sector/`，后续主维护入口为 `h-sector/src/app/**`、`h-sector/src/components/website/**`、`h-sector/src/config/site.ts` 和 `h-sector/public/**`。
- 管理后台、后台 API、PC 桌面端 API、支付、License、用量、支持包、审计和数据库模型后续均应在 `h-sector/` 中设计和实现。
- 具体实现变更应优先落到 `h-sector/openspec/changes/**`，并遵守 `h-sector/openspec/specs/**` 中的底座规范。

## 1. 背景

当前 `h-sector/` 是公司通用全栈项目底座，已经接收从 `h-sector-website/` 迁入的产品官网页面、公开 API、SEO、组件、配置和静态资源。现在需要将原规划在 `account-matrix-server/`、后续阶段曾临时指向 `h-sector-website/` 的管理后台和后端服务能力，统一纳入 `h-sector/`。

完成本需求后，`h-sector/` 将成为 Account Matrix 的统一 Web 服务项目：

- 官网继续对所有访客公开可见。
- 管理后台使用 `h-sector` 现有账号密码认证能力，并需要后台角色权限。
- 后台 API、PC 端 API、支付 webhook、License、用量、支持包和数据库访问都在 `h-sector/` 中实现。
- `account-matrix-server/` 不再保留任何职责，验收完成后可以删除该目录。

## 2. 范围

### 2.1 本次目标

在 `h-sector/` 中承载以下能力：

- 公开官网页面。
- 官网公开只读 API。
- 管理后台页面。
- 管理后台 API。
- PC 桌面端 API。
- 支付 checkout 和 webhook。
- 用户、套餐、订阅、订单、设备、License、用量、支持包、审计日志等领域模型。
- 后台登录、角色权限和服务端鉴权。

目标结构应遵守 `h-sector` 的三层结构规范：

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
      dashboard/
        ...
      admin/
        page.tsx              # 可保留公开占位入口
    pages/
      api/
      public/
      admin/
      desktop/
      billing/
    components/
    config/
  backend/
    services/
      public-site/
      admin/
      desktop/
      billing/
      licenses/
      usage/
      support/
    prisma/
  shared/
    types/
```

### 2.2 公开官网范围

以下路由保持公开访问，不需要登录：

- `/`
- `/features`
- `/pricing`
- `/download`
- `/docs`
- `/contact`
- `/api/public/*`
- `robots.txt`
- `sitemap.xml`
- 静态资源

### 2.3 管理后台范围

以下后台路由必须受保护，默认推荐使用 `h-sector` 现有控制台命名空间：

- `/dashboard/*`
- `/api/admin/*`

`/admin` 已作为公开占位入口迁入 `h-sector`；真实后台能力不应继续放在公开 `/admin` 页面下，除非后续 OpenSpec 变更明确批准新的后台路由策略。

后台能力：

- 登录页，仅支持邮箱/手机号/用户名 + 密码登录。
- 后台首页。
- 用户管理。
- 订阅管理。
- 套餐管理。
- 订单/支付记录。
- 设备管理。
- License 管理。
- 用量记录。
- 封禁/解封。
- 支持包查看。
- 操作审计日志。

### 2.4 PC 端 API 范围

PC 桌面端必须通过 `h-sector/` 暴露的服务端 API 完成：

- 登录。
- token/session 刷新。
- 设备激活和解绑。
- License 获取和刷新。
- 订阅状态查询。
- 套餐查询。
- 用量上报。
- 支持包上传。
- 支付 checkout。

推荐命名空间：

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

### 2.5 支付范围

支付相关接口放在：

```text
POST /api/billing/checkout
POST /api/billing/webhook
```

支付 webhook 必须验证签名并保证幂等。

## 3. 不在本次范围

- 不重做官网视觉或公开页面内容。
- 不改变官网公开访问策略。
- 不迁移桌面端 UI 代码。
- 不降低后台权限、审计、License、支付和用量校验要求。
- 不保留 `account-matrix-server/` 作为第二个服务端项目。

## 4. 用户与角色

### 4.1 官网访客

官网访客不需要登录即可访问公开官网页面和公开只读 API。

官网访客不得访问：

- `/dashboard/*`
- `/api/admin/*`
- `/api/desktop/*`
- `/api/billing/*`
- 后台数据
- 用户数据
- 订阅、订单、设备、License、用量和支持包数据

### 4.2 PC 端用户

PC 端用户通过登录或 License 激活后使用桌面应用。

PC 端角色：

- `normal`
- `advanced`
- `developer`

PC 端功能和额度由套餐、功能开关和 License Claims 决定，不能只依赖硬编码角色。

### 4.3 管理后台用户

后台角色：

- `admin`：全部管理权限。
- `ops`：用户、订阅、订单、设备、用量、封禁和问题处理管理。
- `developer`：查看排障数据、诊断信息、支持包、错误详情、版本和功能开关；默认不应拥有退款、套餐修改等运营写权限。

## 5. 鉴权与访问控制需求

系统必须保护：

- `/dashboard/*`
- `/api/admin/*`
- `/api/desktop/*`
- `/api/billing/*`

要求：

- `/login` 允许未登录访问。
- 未登录访问 `/dashboard/*` 必须进入 `h-sector` 现有登录保护流程。
- 未登录访问 `/api/admin/*` 必须返回 `401`。
- 已登录但没有后台角色时，访问后台页面必须显示无权限或跳转到无权限页。
- 已登录但没有对应 API 权限时，`/api/admin/*` 必须返回 `403`。
- PC 端 API 必须校验用户、设备和 License 上下文。
- 支付 webhook 必须验证渠道签名。
- 前端隐藏菜单不能作为权限边界。

## 6. 数据与领域模型需求

`h-sector/` 必须承载或直接管理以下领域模型：

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

后台、PC 端 API、支付和 License 必须共用同一套用户、套餐、订阅和设备模型，避免重复定义。

## 7. License 与用量需求

License 必须支持在线校验和本地签名缓存。

License Claims 至少包含：

- 用户 ID。
- 套餐 ID。
- 订阅状态。
- 角色。
- 功能开关。
- 限制额度。
- 过期时间。
- 离线宽限截止时间。
- 设备 ID。
- 签发时间。
- 签名。

用量必须支持：

- 启用账号数。
- 激活设备数。
- 每日任务启动次数。
- 每日执行账号数。
- 每日目标互动次数。
- 每日初始化/注册次数。
- 调度触发次数。
- CSV 导出次数。
- 失败次数和失败率。

## 8. 安全需求

- 数据库连接只允许出现在 server-only 模块。
- 后端密钥只允许来自服务端环境变量。
- License 签名密钥不得进入客户端 bundle。
- 支付 webhook 签名密钥不得进入客户端 bundle。
- 后台 API 不得返回超出角色权限的数据。
- PC 端 API 不得绕过订阅、设备、License 和用量校验。
- 官网公开页面不得导入后台、数据库、支付或 License server-only 模块。

## 9. 部署需求

`h-sector/` 部署环境必须支持 Next.js server runtime，因为项目需要：

- 服务端鉴权。
- API route handlers。
- 数据库访问。
- 环境变量密钥。
- License 签名。
- 支付 webhook。
- 后台写操作审计。

不得将整合后的 `h-sector/` 部署到纯静态托管环境。

## 10. account-matrix-server 删除条件

完成本 spec 后，只有满足以下条件才可以删除 `account-matrix-server/`：

- `h-sector/` 已实现或接收 `account-matrix-server/` 规划的全部服务端职责。
- `/dashboard/*` 和 `/api/admin/*` 在 `h-sector/` 中可用并受保护。
- `/api/desktop/*` 在 `h-sector/` 中可用，且桌面端可以切换到新地址。
- `/api/billing/*` 在 `h-sector/` 中可用。
- License、用量、支付、支持包和审计逻辑已迁入或重建。
- 相关环境变量、数据库迁移和部署文档已更新。
- specs 中不再要求 `account-matrix-server/` 承载任何能力。
- `h-sector` 的构建、类型检查和关键冒烟验证通过。

## 11. 文档修订需求

实现前后必须同步修订：

- `h-sector/README.md`
- `h-sector/openspec/changes/**`

修订重点：

- 标注 `account-matrix-server/` 和 `h-sector-website/` 均不再作为后续统一 Web 服务实现项目。
- 移除后续开发对 `account-matrix-server/` 的依赖。
- 明确产品官网、管理后台、PC API、支付、License、用量和支持包统一由 `h-sector/` 承载。
- `specs/account-matrix-server/` 属于旧方案归档 spec，后续不再作为修订对象；确认无引用后可以删除。

## 12. 验收标准

- 官网公开页面不需要登录即可访问。
- `/dashboard/*` 未登录时不能访问。
- `/api/admin/*` 未登录时返回 `401`。
- `/api/desktop/*` 按登录、设备、License 和订阅状态校验。
- `/api/billing/webhook` 验证签名并幂等处理。
- 无后台角色用户访问后台返回无权限状态。
- 后台 API 在服务端执行角色权限校验。
- 后台布局、登录页、后台首页和至少一个占位业务页可访问。
- 官网页面、SEO 和公开 API 不因整合而回退。
- 管理后台、PC API、支付、License、用量和支持包相关密钥不进入客户端 bundle。
- `h-sector` 构建或类型验证通过。
- 相关 specs 已同步更新。
- `account-matrix-server/` 可以被删除且不影响官网、后台、PC API、支付或 License。
