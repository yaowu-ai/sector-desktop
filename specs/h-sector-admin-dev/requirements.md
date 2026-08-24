# H Sector 后台与后端整合需求文档

## 0. 文档状态

本文已在 2026-08-18 更新为 `h-sector/` 权威实现方案。

- `h-sector-website/` 已不再作为统一 Web 服务项目继续扩展；它现在只保留为产品官网迁移前的历史来源和迁移记录。
- 产品官网已迁入 `h-sector/`，后续主维护入口为 `h-sector/src/app/**`、`h-sector/src/components/website/**`、`h-sector/src/config/site.ts` 和 `h-sector/public/**`。
- 管理后台、后台 API、PC 桌面端 API、支付、License、用量、审计和数据库模型后续均应在 `h-sector/` 中设计和实现。
- 当前产品没有售后服务包、工单包、人工支持套餐或支持包上传业务；后续不得默认新增 `support_bundles` 或 `/support-bundles` 能力。
- 当前产品用户和后台管理员已分表：`users` 是产品客户，`admin_users` 是后台管理人员，产品用户不能登录管理后台。
- 当前后台已接入真实数据的模块包括：系统总览、用户管理、订阅管理、会员套餐、设备管理、授权管理、用量记录和审计日志。
- `account-matrix` 桌面端已接入 `h-sector` 基础接口闭环：登录、刷新、设备激活/解绑、套餐查询、订阅查询、授权查询和用量上报。
- 支付渠道已确定为支付宝；支付宝应用配置、密钥、网关、回调域名、商品金额和续费模式仍待提供。支付宝环境变量和 webhook 路由契约已确定。真实 checkout、webhook、订单/支付事件、支付商品映射、签名 License、离线验签和额度强校验仍是后续范围。
- License 签名方案已确认使用 Ed25519 非对称签名；服务端持有私钥签发，桌面端内置公钥验签。
- License Claims 字段和免费/月度/年度套餐默认额度已确认，后续实现不得再使用硬编码角色或前端本地判断替代服务端签发的 Claims。
- 具体实现变更应优先落到 `h-sector/openspec/changes/**`，并遵守 `h-sector/openspec/specs/**` 中的底座规范。

## 1. 背景

当前 `h-sector/` 是公司通用全栈项目底座，已经接收从 `h-sector-website/` 迁入的产品官网页面、公开 API、SEO、组件、配置和静态资源。现在需要将原规划在 `account-matrix-server/`、后续阶段曾临时指向 `h-sector-website/` 的管理后台和后端服务能力，统一纳入 `h-sector/`。

完成本需求后，`h-sector/` 将成为 Account Matrix 的统一 Web 服务项目：

- 官网继续对所有访客公开可见。
- 管理后台使用 `h-sector` 现有账号密码认证能力，并需要后台角色权限。
- 后台 API、PC 端 API、支付 webhook、License、用量、审计和数据库访问都在 `h-sector/` 中实现。
- `account-matrix-server/` 不再保留任何职责，验收完成后可以删除该目录。

## 2. 范围

### 2.1 本次目标

在 `h-sector/` 中承载以下能力：

- 公开官网页面。
- 官网公开只读 API。
- 管理后台页面。
- 管理后台 API。
- PC 桌面端 API。
- 用户、套餐、订阅、设备、License、用量、审计日志等当前已实现领域模型。
- 支付宝 checkout、webhook、订单、支付事件和支付商品映射，待支付宝配置提供后进入真实闭环实现。
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
- 支付宝 checkout，待支付宝配置提供后接入。

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
```

### 2.5 支付范围

支付宝支付相关接口放在：

```text
POST /api/billing/alipay/checkout
POST /api/billing/alipay/webhook
GET  /billing/alipay/return
```

支付宝 webhook 必须验证支付宝签名并保证幂等。同步返回页只用于用户支付完成后的页面跳转和状态提示，不能作为支付成功的可信依据。

支付宝相关服务端环境变量：

```text
ALIPAY_APP_ID
ALIPAY_APP_PRIVATE_KEY
ALIPAY_PUBLIC_KEY
ALIPAY_GATEWAY_URL
ALIPAY_SIGN_TYPE
ALIPAY_NOTIFY_URL
ALIPAY_RETURN_URL
ALIPAY_CHARSET
ALIPAY_TIMEOUT_EXPRESS
```

配置要求：

- `ALIPAY_APP_PRIVATE_KEY` 只能放在服务端环境变量或 K8s Secret，不得进入客户端 bundle。
- `ALIPAY_PUBLIC_KEY` 用于服务端验签，不得由前端直接参与支付可信判断。
- `ALIPAY_GATEWAY_URL` 必须区分沙箱和生产。
- `ALIPAY_SIGN_TYPE` 默认使用 `RSA2`。
- `ALIPAY_NOTIFY_URL` 指向 `/api/billing/alipay/webhook`。
- `ALIPAY_RETURN_URL` 指向 `/billing/alipay/return`。
- 缺少任一必要配置时，checkout 和 webhook 相关接口必须返回明确 `NOT_CONFIGURED`，不得伪造支付成功。

## 3. 不在本次范围

- 不重做官网视觉或公开页面内容。
- 不改变官网公开访问策略。
- 不重做桌面端核心业务 UI；只为登录、授权、设备、订阅和用量联调做必要客户端改造。
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
- 订阅、订单、设备、License 和用量数据

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
- `developer`：查看排障数据、诊断信息、错误详情、版本和功能开关；默认不应拥有退款、套餐修改等运营写权限。

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

`h-sector/` 当前必须承载或直接管理以下已实现领域模型：

- `users`
- `plans`
- `subscriptions`
- `devices`
- `licenses`
- `usage_daily`
- `feature_flags`
- `audit_logs`

后台、PC 端 API、支付和 License 必须共用同一套用户、套餐、订阅和设备模型，避免重复定义。

支付宝配置提供后再补齐以下支付阶段模型：

- `orders`
- `payment_events`

## 7. License 与用量需求

License 必须支持在线校验和本地签名缓存。License 签名方案使用 Ed25519 非对称签名：

- `h-sector` 服务端持有私钥并签发 License。
- `account-matrix` 桌面端只内置公钥并验签。
- 私钥通过服务端环境变量 `LICENSE_PRIVATE_KEY` 注入。
- 公钥通过桌面端构建配置或环境变量 `LICENSE_PUBLIC_KEY` 注入。
- License 使用 JSON Claims + Ed25519 signature + base64url 封装。

License Claims 至少包含：

- `version`：Claims 版本号，当前为 `1`。
- `licenseId`：License ID。
- `userId`：产品用户 ID。
- `subscriptionId`：订阅 ID。
- `planId`：套餐 ID。
- `planCode`：套餐编码，例如 `free`、`monthly`、`yearly`。
- `subscriptionStatus`：订阅状态，例如 `active`、`expired`、`canceled`。
- `licenseStatus`：License 状态，例如 `active`、`expired`、`revoked`。
- `deviceId`：设备 ID。
- `deviceFingerprint`：设备指纹。
- `features`：可用功能列表。
- `limits`：套餐额度。
- `issuedAt`：签发时间。
- `expiresAt`：License 过期时间。
- `offlineGraceUntil`：离线宽限截止时间。
- `signature`：Ed25519 签名。

`limits` 至少包含：

- `maxDevices`：最多激活设备数。
- `dailyTaskRuns`：每日任务启动次数。
- `dailyAccountRuns`：每日执行账号数。
- `dailyTargetActions`：每日目标互动次数。
- `dailyCsvExports`：每日 CSV 导出次数。
- `offlineGraceDays`：离线宽限天数。

默认套餐额度：

| 套餐 | maxDevices | dailyTaskRuns | dailyAccountRuns | dailyTargetActions | dailyCsvExports | offlineGraceDays | features |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 免费用户 | 1 | 3 | 10 | 30 | 0 | 0 | `tiktok` |
| 月度会员 | 1 | 200 | 1000 | 5000 | 20 | 3 | `tiktok`, `scheduler`, `csv_export` |
| 年度会员 | 2 | 500 | 3000 | 15000 | 100 | 7 | `tiktok`, `scheduler`, `csv_export` |

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
- `/api/billing/*` 在 `h-sector/` 中可用，或支付能力已被明确延期且旧服务端不再承载该能力。
- License、用量、支付和审计逻辑已迁入、重建或被明确拆分为后续 `h-sector` 迭代。
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
- 明确产品官网、管理后台、PC API、支付、License、用量和审计统一由 `h-sector/` 承载。
- `specs/account-matrix-server/` 属于旧方案归档 spec，后续不再作为修订对象；确认无引用后可以删除。

## 12. 验收标准

- 官网公开页面不需要登录即可访问。
- `/dashboard/*` 未登录时不能访问。
- `/api/admin/*` 未登录时返回 `401`。
- `/api/desktop/*` 按登录、设备、License 和订阅状态校验。
- 支付宝配置提供后，`/api/billing/alipay/webhook` 验证签名并幂等处理。
- 无后台角色用户访问后台返回无权限状态。
- 后台 API 在服务端执行角色权限校验。
- 后台布局、登录页、后台首页和至少一个占位业务页可访问。
- 官网页面、SEO 和公开 API 不因整合而回退。
- 管理后台、PC API、支付、License 和用量相关密钥不进入客户端 bundle。
- `h-sector` 构建或类型验证通过。
- 相关 specs 已同步更新。
- `account-matrix-server/` 可以被删除且不影响官网、后台、PC API；支付和签名 License 如未完成，必须明确由 `h-sector` 后续迭代承接，不能回退到旧服务端。
