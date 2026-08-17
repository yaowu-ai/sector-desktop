# Account Matrix 官网视觉改版设计文档

## 1. 设计原则

本次官网改版采用以下原则：

- 产品先行：首屏和主要页面必须展示产品场景。
- 信息清晰：每个页面先回答用户为什么需要、能解决什么、下一步做什么。
- 科技克制：使用深色、青绿色、任务流和控制台视觉，但避免过度游戏化。
- 全站一致：导航、按钮、卡片、表格、CTA、页面 hero 和底部统一。
- 可实现优先：基于现有 Next.js、Tailwind CSS 和 `motion` 实现，不引入重型 UI 库。

## 2. 视觉系统

### 2.1 色彩

建议建立官网专用色彩语义：

```text
background/base       #020617
background/elevated   #0f172a
background/panel      #111827
border/subtle         rgba(148, 163, 184, 0.18)
border/active         rgba(45, 212, 191, 0.42)
text/primary          #f8fafc
text/secondary        #cbd5e1
text/muted            #94a3b8
brand/primary         #10b981
brand/bright          #2dd4bf
accent/purple         #8b5cf6
status/success        #22c55e
status/warning        #f59e0b
status/danger         #ef4444
```

设计要求：

- 青绿色作为品牌主色，主要用于 CTA、状态成功、执行进度、关键数字。
- 紫蓝只作为辅助，不作为全站主色。
- 深色背景必须通过面板层级、边框和轻微光效建立空间感。
- 正文文字使用浅灰，不使用纯白长段文本。

### 2.2 字体

继续使用系统字体栈。

标题要求：

- 首页 H1 可以使用较强视觉表现，但不能使用游戏化、像素化或过度压缩字体。
- 中文标题需要保证字形清晰。
- 不使用负字距。
- 不按 viewport width 缩放字体。

### 2.3 背景

可使用：

- 深色径向光。
- 细网格。
- 轻微扫描线。
- 面板阴影。
- 低透明度数据轨迹。

避免：

- 大面积纯紫蓝渐变。
- 随机装饰光球。
- 与产品无关的抽象 3D 物体。
- 干扰文字阅读的高亮背景。

## 3. 组件设计

### 3.1 Navbar

导航应保持紧凑、专业、产品导向。

结构：

- 左侧：Account Matrix 标识。
- 中间：功能、价格、下载、文档。
- 右侧：联系咨询、下载或开始使用。

样式：

- 深色半透明背景。
- `backdrop-blur`。
- 下边框低透明度。
- 当前页面可以使用青绿色高亮。
- 移动端需要可展开菜单。

### 3.2 Footer

Footer 应统一深色底部风格。

内容：

- 产品简介。
- 产品导航。
- 资源入口。
- 联系入口。
- 版权信息。

样式：

- 不使用浅色 footer。
- 与页面背景自然衔接。
- 链接 hover 使用青绿色。

### 3.3 Button

按钮层级：

- Primary：青绿色渐变或高亮实色，用于主要 CTA。
- Secondary：深色透明面板 + 边框，用于次要 CTA。
- Ghost：导航或低优先级操作。

按钮要求：

- 文案短。
- 移动端不溢出。
- hover 有轻微亮度或边框变化。
- focus 状态清晰。

### 3.4 Card

官网卡片分为：

- Feature Card：功能说明。
- Metric Card：指标。
- Console Panel：产品面板。
- Pricing Card：套餐。
- Doc Card：文档入口。
- Contact Card：联系入口。

通用样式：

- 深色或半透明面板。
- 细边框。
- 轻阴影。
- 8px 到 14px 圆角。
- hover 只做轻微边框、阴影或位移。

### 3.5 Product Console

产品预览是本次改版的核心视觉。

建议抽象为一组可复用展示组件：

- `AccountMatrixPreview`
- `TaskQueuePreview`
- `EnvironmentProfilePreview`
- `AutomationFlowPreview`
- `MetricsPreview`

组件展示内容：

- 账号昵称或编号。
- Profile / 代理 / 环境状态。
- 任务类型。
- 执行进度。
- 成功、排队、异常状态。
- 互动数据或增长趋势。

注意：

- 预览数据必须像真实业务，不使用无意义 lorem ipsum。
- 不展示敏感真实账号。
- 视觉面板可以是伪数据。

## 4. 页面设计

### 4.1 首页 `/`

首页建议结构：

```text
Hero
  产品名
  核心价值主张
  主 CTA：下载 / 开始使用
  次 CTA：查看功能 / 联系咨询
  产品控制台预览

Operational Metrics
  账号规模、任务执行、环境隔离、复盘效率

Core Capabilities
  环境隔离、自动养号、目标互动、素材池、数据复盘、风控提示

Workflow
  导入账号 -> 配置环境 -> 创建任务 -> 自动执行 -> 查看结果

Use Cases
  新号冷启动、矩阵内容互动、评论素材管理、批量执行

CTA
  下载客户端 / 查看套餐 / 联系顾问
```

Hero 视觉：

- 左侧文案，右侧或背景叠加产品控制台。
- 首屏需露出下一段内容的一部分。
- 控制台应包含账号矩阵、任务队列、进度条和状态标签。

### 4.2 功能页 `/features`

按工作流组织功能：

```text
Hero：从账号环境到自动执行的一体化矩阵运营系统

Section 1：账号与环境管理
  Profile、代理、分组、状态、标签

Section 2：自动化任务
  养号、浏览、互动、调度、失败重试

Section 3：目标号互动
  目标列表、策略、频率、执行记录

Section 4：素材与评论池
  通用池、品牌池、随机化、使用记录

Section 5：数据复盘
  任务结果、失败率、账号健康、趋势

Section 6：安全与排障
  环境隔离、日志、支持包、风控提示
```

每个 section 配一个小型产品面板，不使用纯文字卡片堆叠。

### 4.3 价格页 `/pricing`

价格页建议结构：

```text
Hero：按账号规模选择套餐
Pricing Cards
Comparison Table
Enterprise CTA
FAQ
```

设计细节：

- 推荐套餐突出但不能压迫其他套餐。
- 额度类信息使用数据标签展示。
- 对比表采用深色表格或深色外壳 + 高对比单元格。
- 移动端价格卡纵向排列。
- 对比表移动端可横向滚动。

### 4.4 下载页 `/download`

下载页建议结构：

```text
Hero：下载 Account Matrix 客户端
Latest Release Panel
System Requirements
Install Steps
Release Notes
Security Notice
CTA
```

视觉重点：

- 最新版本卡片需要像发布控制台。
- 下载按钮清晰。
- 安装步骤使用编号流程。
- 更新日志使用 timeline 或 release card。

### 4.5 文档页 `/docs`

文档页建议结构：

```text
Hero：快速上手和常见问题
Quick Start
Concept Cards
FAQ / Details
Troubleshooting
Contact CTA
```

设计细节：

- 文档页以可读性优先，减少重光效。
- 可保留深色背景，但内容块需要高对比。
- FAQ 展开项需要清晰边界。

### 4.6 联系页 `/contact`

联系页建议结构：

```text
Hero：联系 Account Matrix
Contact Channels
Use Case Form / Inquiry Panel
Support Expectations
FAQ
CTA
```

设计细节：

- 联系入口按售前、技术支持、企业合作、反馈分类。
- 联系表单如果只是静态展示，需要明确提交状态或接入已有 API。
- 页面应降低炫光，突出可达性和可信度。

## 5. 信息架构与文案

### 5.1 核心价值主张

建议首页主文案方向：

```text
Account Matrix
TikTok 矩阵账号运营自动化平台
统一管理账号环境、自动任务、目标互动和数据复盘，让团队用更可控的流程运营更多账号。
```

### 5.2 推荐关键词

- TikTok 矩阵运营。
- 多账号管理。
- 浏览器环境隔离。
- 自动养号。
- 批量任务。
- 目标号互动。
- 评论素材池。
- 运行记录。
- 账号健康。
- 数据复盘。

### 5.3 避免文案

- 避免“颠覆式”“革命性”“一键暴涨”等夸张表达。
- 避免暗示绕过平台规则或规避风控。
- 避免泛 SaaS 模板词堆叠。

## 6. 技术设计

### 6.1 文件影响范围

预计涉及：

```text
website/app/globals.css
website/app/layout.tsx
website/app/page.tsx
website/app/features/page.tsx
website/app/pricing/page.tsx
website/app/download/page.tsx
website/app/docs/page.tsx
website/app/contact/page.tsx
website/src/components/navbar.tsx
website/src/components/footer.tsx
website/src/components/hero-spotlight.tsx
website/src/components/reveal.tsx
website/src/config/site.ts
```

可新增：

```text
website/src/components/product-preview.tsx
website/src/components/page-shell.tsx
website/src/components/section-heading.tsx
website/src/components/cta-band.tsx
```

是否新增文件以实现时保持简洁为准。

### 6.2 Tailwind 策略

- 保留 Tailwind CSS 3。
- 在 `tailwind.config.js` 中扩展品牌色、背景色和阴影。
- 在 `globals.css` 中保留少量全局组件类。
- 页面内主要仍使用 Tailwind 工具类。
- 避免把大量页面专用样式堆进全局 CSS。

### 6.3 动效策略

使用已有 `motion` 或 CSS 动画：

- Hero 控制台轻微进入动画。
- 任务行轻微上浮。
- 进度条流动。
- 卡片 hover。
- CTA 光扫效果。

限制：

- 不做复杂 3D。
- 不做长时间强闪烁。
- 不影响 `prefers-reduced-motion` 用户。

### 6.4 响应式策略

断点：

- Mobile：单列，导航折叠。
- Tablet：两列局部布局。
- Desktop：左右布局或 3 列卡片。

关键处理：

- Hero 产品面板在移动端放到文案下方。
- 价格卡移动端纵向排列。
- 对比表移动端横向滚动。
- 文档侧边栏移动端变为顶部目录或隐藏为列表。

## 7. 验证方案

实现后需要检查：

- `pnpm typecheck`
- `pnpm build` 或至少 `pnpm dev` 启动成功
- 桌面首页截图检查
- 移动首页截图检查
- `/features`、`/pricing`、`/download`、`/docs`、`/contact` 页面人工检查
- 文本无明显溢出
- CTA 链接可点击
- `robots.ts` 和 `sitemap.ts` 未误收录 `/admin/*` 或 `/api/*`

## 8. 风险与取舍

- 深色视觉如果对比不足，会影响可读性；文档和价格页需要更克制。
- 过多视觉面板可能增加维护成本；建议抽象少量复用组件。
- 太像图 1 会显得游戏化；字体和光效要控制。
- 太像图 2 会变成通用 SaaS 模板；首屏和产品场景必须增强辨识度。
- 暂不引入 UI 库可以减少依赖，但需要自己维护视觉组件一致性。
