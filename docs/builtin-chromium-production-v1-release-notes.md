# 内置 Chromium 生产可选方案 V1 发布说明

## 产品状态

- 内置 Chromium 已从实验状态晋级为生产可选浏览器提供方。
- BitBrowser 仍是 TikTok 自动化的默认推荐方案。
- 内置 Chromium 使用本机 Chromium、账号独立用户数据目录和临时 CDP 端口运行。
- 内置 Chromium 不等价替代 BitBrowser 的指纹环境能力；需要强指纹隔离能力的账号仍应优先使用 BitBrowser。

## UI 与诊断

- 浏览器环境页面已升级为双 Provider 控制台，顶部展示 BitBrowser 状态卡（生产默认推荐）、内置 Chromium 状态卡（生产可选）和账号环境概览卡。
- 页面 Tab 结构为：BitBrowser Profile、内置 Chromium、账号绑定、批量工具。
- 内置 Chromium Tab 展示可执行文件状态、数据根目录、账号级 user data dir，支持检测、复制路径和清理数据操作。
- 账号绑定 Tab 统一展示所有账号的浏览器提供方和环境标识，操作按钮按 provider 分流。
- 批量工具 Tab 集中 BitBrowser 单个创建、批量创建和账号环境同步。
- BitBrowser API 离线时，仅影响 BitBrowser Profile Tab，其他 Tab 不受影响。
- 账号列表、任务执行账号区域和启动确认框会显示账号浏览器环境。
- 诊断页支持按账号检查内置 Chromium 可执行文件、代理、用户数据目录、运行记录和 CDP endpoint。
- Session 日志和执行记录会写入启动时使用的 provider，便于排查混合队列。
