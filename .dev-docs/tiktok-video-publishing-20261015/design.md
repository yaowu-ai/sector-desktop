# TikTok 视频作品发布与发布记录设计

## Terminal State

PASS

这是 code-plan 设计就绪结论，不是实现完成、真实发帖成功或三浏览器已验收结论。仅新增本目录合约；不修改应用代码。日期：2026-10-15（Asia/Shanghai）。Proof Profile: mixed-system。

## Intent & Scope

运营在桌面端选择一次本地视频绝对路径，输入或导入一次文案，选单个、多个或全部启用 TikTok 账号，系统分别用账号已有浏览器自动上传、发布并进入本人主页核验。所有账号使用启动时同一份不可变素材与文案。发布记录逐账号持久化。

范围：一级“发布作品”及两个子页；原生视频单选器；可编辑文案框；UTF-8 TXT、DOCX 正文导入；三 provider；既有登录保障；Upload → Select video → Uploaded → 条件弹窗 Turn on/Got it → Description → Post → 本人主页；进度、停止、失败隔离；历史筛选、详情、作品链接及待确认重新核验。

非目标：图片/原生纯文字作品、视频复制托管、云素材库、视频剪辑/转码/音乐/封面编辑/地点、定时发布、每账号分配不同素材、自动重发、历史删除/导出、服务端套餐新增权益、旧版 .doc、Word 表格转文案、移动端自动化。页面没有这些入口；API 对未知字段/类型明确拒绝而非退化到养号。

容易误读：文案文件只用于导入纯文本，最终以输入框内容为准；文件导入不是每账号执行时重新读 Word/TXT。视频路径不是远程URL，也不是系统文件窗口的屏幕坐标操作。主页可见不等于审核通过或他人公开可见。应用现有登录凭据只沿用安全读取与环境脱敏，不写入发布快照。

## Evidence Basis

以下是经挑战后的 Evidence Cards。路径以 account-matrix/ 为根；兄弟项目证据仅只读，实施不修改 h-sector。截图文字来自用户在本聊天提供的五张图片；不把截图当作 DOM 或已运行证明。

| ID | QID / Class | Answer / Evidence | Proves | Does Not Prove / Challenge | Contract Impact / Consumer |
| --- | --- | --- | --- | --- | --- |
| EV1 | U1 Requirement | 本聊天从“第一版先只支持上传视频”至菜单优化：单视频、本地路径、输入或文件导入文案、single/selected/all、三浏览器、每账号主页核验；用户截图流程明确自动点击 Turn on、Got it | 产品范围与发布动作由用户确定 | 不是授权在设计阶段真实发布，也未要求视频转码、平台API或新套餐 | C1；S1、S2、S3 |
| EV2 | U2 Local Pattern | desktop/src/app/routes.tsx:48,66；components/AppShell.tsx:220,300,470；app/routePermissions.ts:11；platforms/types.ts:5；platforms/common/capabilities.ts:7；src-tauri/src/commands/config.rs:5197 | 现有 menuGroup、父组展开、客户白名单和两端平台能力检查可延伸 | 现有组标题只展开，不自动导航，必须补组标题默认进入发布页；不能只改一个前端数组 | C2；D1；S1 T1/T2/T11/T18、S3 T1 |
| EV3 | U3 Local Pattern | commands/process.rs:576,646,694,745,1121,1159,1169,1841,1852；state.rs:29；TaskPage.tsx:190,250 | Rust 队列逐账号开子进程；未知类型默认 fyp；下一账号预检失败会终止余队列；已有互斥、强停及完成当前后停止 | 当前代码没有发布请求/快照，也没有发布成功含义；必须显式映射并为发布分支补失败推进 | C3；D3；S1 T9-T15、S2 T12-T15 |
| EV4 | U4 Local Pattern | src/browser_providers.py:25,110；platforms/tiktok/runner.py:75,298,308,337；profile_stats.py:94,182,208,216 | BitBrowser/ixBrowser/builtin_chromium 均提供 CDP；Profile 链接识别真实 handle并前后校验；可复用会话、auth和临时页 | collect_current_account 同时读 Liked/activity，不适合作为每次发布核验；账号配置ID不等于用户名；未证明新发布兼容 | C4；D5/D6；S2 |
| EV5 | U5 Local Pattern | commands/files.rs:319 已用 Win32 保存对话框；Cargo.toml:29 包含 windows-sys 对话框；BrowserProfilePage.tsx:2007,2025,2091,2159,2214已有TXT/DOCX/ZIP解析 | 原生选择绝对路径有仓库基础；DOCX不必引入新服务；旧.doc当前拒绝 | HTML File不提供可靠绝对路径；原DOCX解析会丢空段且依赖deflate-raw；不能原样照搬 | C5；D2；S1 T3-T8/T16 |
| EV6 | U6 Local Pattern | core/runtime.py:138,146,214,825；commands/stats.rs:541,564；paths actions_db_path；sqlite查询使用参数和缺表空结果 | actions.db 是现有本机运行事实存储，专属结构可加法迁移，Rust读记录、Python写执行事实符合现有边界 | action_log.detail不足以表达唯一尝试及提交不确定性；不能用日志文本恢复状态 | C6；D4/D7；DB1 |
| EV7 | U7 Official Practice / Requirement | 用户五图：Upload、/tiktokstudio/upload、Select video、Uploaded、两种弹窗、Description及4000计数；[Playwright Actions](https://playwright.dev/python/docs/input#upload-files) 支持文件控件、file chooser 和contenteditable；[CDP](https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp) 限Chromium且保真度较低 | 从本地路径传文件无需操控系统窗口；编辑后必须回读；三浏览器需实际兼容验证 | 截图不提供准确DOM，Post在图外；不会伪造selector或私有接口。官方Playwright行为需在实际Patchright中验收 | C7；D5/D6；ED1；S2 T1-T6/T8-T11 |
| EV8 | U8 Official Practice | [GetOpenFileNameW](https://learn.microsoft.com/en-us/windows/win32/api/commdlg/nf-commdlg-getopenfilenamew) 与现有Win32保存实现互证；[SQLite事务](https://www.sqlite.org/transactional.html) 保证本地事务，不包含外站点击 | 用已有windows-sys做单选；本地提交标记必须先落盘再点击外部Post | SQLite不能提供TikTok exactly-once；不能将超时判断为未发布 | C8；D2/D4；SD1 |
| EV9 | U9 Official Practice | [DOMParser](https://developer.mozilla.org/en-US/docs/Web/API/DOMParser/parseFromString)、[TextDecoder](https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder)、[DecompressionStream](https://developer.mozilla.org/en-US/docs/Web/API/DecompressionStream) 与现有导入实现互证 | 用XML DOM和严格UTF-8解析，解压能力必须检测；解析错误不能覆盖草稿 | 不证明本机WebView2版本、DOCX所有格式语义；表格拒绝，旧版.doc拒绝，缺解压需提示环境不支持 | C5；D2；S1 T5/T6/T8 |
| EV10 | U10 Local Pattern | process.rs:884,899,915；h-sector/shared/types/api/usage.dto.ts:53；backend/services/usage/usage.service.ts:134；usage.facade.ts:147 | taskType是普通字符串，已有按批次一次task额度；仅scheduler/target额外套餐门控；publish无服务端白名单障碍 | 不擅自增加套餐权益或免额度；远程扣额与本地创建不能组成事务 | C9；D3；S1 T15 |
| EV11 | U11 Local Pattern / Design Style | desktop/src/app/App.tsx:27-51：既有蓝色明暗token、36px控件、10px圆角；PageHeader/EmptyState/StatusTag/ProcessOutputPanel现成；yaowu-design-style当前产品系统优先 | 新页复用既有Antd与主题，采用AI/YAOWU配置，不平行造组件 | 截图是TikTok外站操作证据，不是account-matrix视觉稿；不照搬其红色品牌 | C2；VC1；S1 T1/T2、S3 T1/T7/T8 |

Unknown Graph 已关闭：

| ID | Question / Qualified Closure |
| --- | --- |
| U1 | 需求范围是什么：EV1，C1，三Story |
| U2 | 菜单与访问如何接线：EV2，C2，D1 |
| U3 | 任务如何不误跑养号且跨账号传递：EV3，C3，D3 |
| U4 | 三浏览器与本人主页复用边界：EV4，C4，D5/D6 |
| U5 | 视频路径与文案导入归属：EV5，C5，D2 |
| U6 | 本机历史与状态如何落库：EV6，C6，D4 |
| U7 | 外站动作和成功证据是什么：EV7，C7，D5/D6 |
| U8 | 外部提交不确定如何处理：EV8，C8，D4 |
| U9 | 文案解析运行限制如何处理：EV9，C5，D2 |
| U10 | 授权与批次额度如何接入：EV10，C9，D3 |
| U11 | 新页使用哪套视觉规范：EV11，C2，VC1 |
- U1→EV1→C1：本轮业务范围已从会话锁定，不增加图片/文字或额外发布设置。
- U2→EV2/EV11→C2：菜单、角色、平台隔离有明确接线；权限沿用养号的已登录用户角色。
- U3→EV3→C3：队列、映射、进度和停止不靠默认行为。
- U4→EV4→C4：共用浏览器与主页导航，但作品核验单独负责。
- U5→EV5/EV9→C5：本地路径、TXT/DOCX语义与失败规则确定。
- U6→EV6/EV8→C6：状态与所有者、事务、迁移确定。
- U7→EV1/EV7→C7：外站动作契约与证据标准确定；具体DOM定位属于ED1约束下的实施工作。
- U8→EV8→C8：外站无法事务化，选择保守待确认而非重复Post。
- U9→EV9→C5：DOCX运行依赖有探测、明确失败和发行验收；不假定任何WebView天然兼容。
- U10→EV10→C9：沿用现有通用额度，不涉及新计费政策。
- U11→EV11→C2：本机桌面WebView布局风格确定。

## Product Examples

下面每行同时是 Example Map 和原子来源去向：Rule Branch带闭合形态，Decisive Example给出可审阅数值；技术证明一一对应。用户来源EV1和防误发、记录恢复等最小设计约束共同决定这些分支。

| Source Behavior | Destination | Rule Branch | Decisive Example | Technical Proof | Support | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| S1-1 一级菜单展开 | consumed | S1 R1 entry 菜单分组 | S1 P1：看到“发布作品”和“发布记录”两个子菜单 | S1 T1 | Visual Contract VC1 | 没有第三个同名一级入口 |
| S1-2 发布页入口 | consumed | S1 R2 entry 发布表单 | S1 P2：看到本地视频选择、可编辑文案和执行账号选择 | S1 T2 | Visual Contract VC1 | 原有养号入口仍可访问 |
| S1-3 选择本地路径 | consumed | S1 R3 state 视频来源 | S1 P3：表单显示该视频的绝对路径、文件名和大小 | S1 T3 | External Dependency ED1 | 文案仍为“海边日常”，不要求复制视频到应用素材库 |
| S1-4 直接输入文案 | consumed | S1 R4 state 文案输入 | S1 P4：输入框完整显示两行文字 | S1 T4 | Visual Contract VC1 | 所选视频保持不变 |
| S1-5 TXT文案导入 | consumed | S1 R5 state 文案导入 | S1 P5：同一文案输入框显示“海边日常\n#旅行” | S1 T5 | External Dependency ED1 | 视频保持不变，文字仍可编辑 |
| S1-6 Word文案导入 | consumed | S1 R6 state Word正文 | S1 P6：文案框显示“海边\n\n#旅行” | S1 T6 | External Dependency ED1 | 不包含图片、页眉页脚或 Word 格式代码 |
| S1-7 覆盖确认 | consumed | S1 R7 rejection 取消覆盖 | S1 P7：输入框仍为“人工修改稿” | S1 T7 | Visual Contract VC1 | 新文件内容未覆盖原文 |
| S1-8 无效文案文件 | consumed | S1 R8 rejection 格式错误 | S1 P8：看到“请另存为 .docx 或 UTF-8 .txt”的提示 | S1 T8 | External Dependency ED1 | 原文案保持不变 |
| S1-9 单账号 | consumed | S1 R9 state 单账号范围 | S1 P9：任务账号列表仅含 tiktok_1 | S1 T9 | SD1, DB1 | tiktok_2 不产生本次发布记录 |
| S1-10 多账号 | consumed | S1 R10 state 多账号范围 | S1 P10：任务仅按选定顺序包含 tiktok_1 和 tiktok_3 | S1 T10 | SD1, DB1 | 两账号共用同一视频路径和文案，tiktok_2 不参与 |
| S1-11 全部账号 | consumed | S1 R11 state 全部启用TikTok | S1 P11：本次任务包含 tiktok_1 和 tiktok_2 | S1 T11 | SD1, DB1 | 不包含 tiktok_3 和 instagram_1 |
| S1-12 启动后固定内容 | consumed | S1 R12 state 内容快照 | S1 P12：B1 中 tiktok_2 的待发文案仍为“海边日常” | S1 T12 | DB1, SD1 | 表单新文案只影响下次任务 |
| S1-13 失效视频 | consumed | S1 R13 rejection 无效素材 | S1 P13：看到视频不存在的错误 | S1 T13 | SD1 | 不打开浏览器且不创建可执行批次 |
| S1-14 无可用账号 | consumed | S1 R14 rejection 无目标账号 | S1 P14：看到“没有可执行的启用账号” | S1 T14 | SD1 | 不打开浏览器、不占用每日任务额度 |
| S1-15 互斥与授权 | consumed | S1 R15 rejection 运行受限 | S1 P15：看到“已有任务正在执行” | S1 T15 | SD1 | 原养号任务保持运行，本次不打开新浏览器 |
| S1-16 确认覆盖文案 | consumed | S1 R16 state 替换文案 | S1 P16：文案框从“人工修改稿”变为“文件稿” | S1 T16 | Visual Contract VC1 | 视频选择保持不变，仍可继续编辑文件稿 |
| S1-17 文案过长 | consumed | S1 R17 rejection 文案长度 | S1 P17：看到文案超长提示 | S1 T17 | External Dependency ED1 | 不截断文案、不打开浏览器 |
| S1-18 非TikTok入口拒绝 | consumed | S1 R18 rejection 平台边界 | S1 P18：看到当前平台不支持视频发布的说明 | S1 T18 | Visual Contract VC1 | 不能启动 TikTok 或 Instagram 发布任务 |
| S2-1 BitBrowser发布 | consumed | S2 R1 state 浏览器兼容 | S2 P1：该账号在 TikTok 上传页自动提交海边.mp4和“海边日常” | S2 T1 | SD1, External Dependency ED1 | 不要求人工再选视频或填写文案，不执行养号动作 |
| S2-2 ixBrowser发布 | consumed | S2 R2 state 浏览器兼容 | S2 P2：该账号在 TikTok 上传页自动提交海边.mp4和“海边日常” | S2 T2 | SD1, External Dependency ED1 | 不要求人工再选视频或填写文案，不执行养号动作 |
| S2-3 内置浏览器发布 | consumed | S2 R3 state 浏览器兼容 | S2 P3：该账号在 TikTok 上传页自动提交海边.mp4和“海边日常” | S2 T3 | SD1, External Dependency ED1 | 不要求人工再选视频或填写文案，不执行养号动作 |
| S2-4 开启内容检查 | consumed | S2 R4 state 可选内容检查 | S2 P4：自动点击该弹窗的 Turn on 后继续填写文案 | S2 T4 | SD1, External Dependency ED1 | 没有改选 Cancel 或取消已选检查项 |
| S2-5 关闭编辑引导 | consumed | S2 R5 state 可选编辑引导 | S2 P5：自动点击该引导的 Got it 后继续填写文案 | S2 T5 | SD1, External Dependency ED1 | 没有进入 Edit、Sounds 或 Text 编辑流程 |
| S2-6 上传未完成 | consumed | S2 R6 rejection 上传失败 | S2 P6：结果显示“发布失败：视频上传失败” | S2 T6 | SD1 | 没有点击 Post，也不显示发布成功 |
| S2-7 登录接管 | consumed | S2 R7 state 登录验证 | S2 P7：任务显示“需要人工处理”并保持账号浏览器可操作 | S2 T7 | SD1 | 验证码完成前不提交视频作品 |
| S2-8 确认本次作品 | consumed | S2 R8 state 成功核验 | S2 P8：结果由“正在核验”变为“已确认成功”，展示 V101 的作品链接 | S2 T8 | SD1, DB1, External Dependency ED1 | 不将 V100 当作本次作品，原视频和文案快照保持不变 |
| S2-9 不确定发布结果 | consumed | S2 R9 state 待确认 | S2 P9：结果为“待确认”并说明主页尚未确认本次作品 | S2 T9 | SD1, DB1, External Dependency ED1 | 不显示已确认成功，不自动再次点击 Post |
| S2-10 旧作品不误判 | consumed | S2 R10 rejection 旧作品证据 | S2 P10：结果仍为“待确认” | S2 T10 | SD1, DB1 | 不把 V100 的链接记录为本次成功作品 |
| S2-11 账号身份变化 | consumed | S2 R11 rejection 身份不一致 | S2 P11：结果显示“发布失败：当前登录账号发生变化” | S2 T11 | SD1 | 不向 @bob 点击 Post |
| S2-12 账号失败后继续 | consumed | S2 R12 state 批量隔离 | S2 P12：tiktok_2 仍按 B1 的视频和文案开始执行 | S2 T12 | SD1, DB1 | tiktok_1 的失败结果保持不变 |
| S2-13 立即停止前置阶段 | consumed | S2 R13 state 取消未提交 | S2 P13：tiktok_1 和 tiktok_2 均显示“已取消” | S2 T13 | SD1, DB1 | 没有继续点击 Post，既有历史成功记录保持不变 |
| S2-14 提交后中断 | consumed | S2 R14 state 不重复提交 | S2 P14：该记录显示“待确认：提交阶段中断” | S2 T14 | SD1, DB1 | 不自动恢复上传或再次点击 Post |
| S2-15 完成当前账号后停止 | consumed | S2 R15 state 停止排队 | S2 P15：tiktok_1 完成核验后 tiktok_2 显示“已取消” | S2 T15 | SD1, DB1 | tiktok_1 的核验结果不被取消覆盖 |
| S2-16 上传前文件变化 | consumed | S2 R16 rejection 素材变动 | S2 P16：tiktok_2 显示“发布失败：视频文件已变化” | S2 T16 | SD1, DB1 | 不为 tiktok_2 上传变化后的视频，tiktok_1 结果不变 |
| S2-17 提交后身份变化 | consumed | S2 R17 state 核验身份异常 | S2 P17：记录显示“待确认：核验账号不一致” | S2 T17 | SD1, DB1 | 不声称提交失败，也不将 @bob 的作品记为成功 |
| S3-1 记录入口 | consumed | S3 R1 entry 发布历史 | S3 P1：看到逐账号发布记录列表 | S3 T1 | Visual Contract VC1 | 原有通用执行记录菜单仍存在 |
| S3-2 批量独立记录 | consumed | S3 R2 display 逐账号结果 | S3 P2：分别看到两行对应账号、视频文件名、提交时间和各自结果 | S3 T2 | DB1 | 不能只显示一条“批次完成”代替两个账号的事实 |
| S3-3 账号筛选 | consumed | S3 R3 display 账号条件 | S3 P3：列表仅显示 tiktok_1 的记录 | S3 T3 | DB1 | 其他账号记录仍保留且不显示在本次结果中 |
| S3-4 状态筛选 | consumed | S3 R4 display 状态条件 | S3 P4：列表仅显示待确认记录 | S3 T4 | DB1 | 成功和失败记录不混入本次列表 |
| S3-5 时间筛选 | consumed | S3 R5 display 时间范围 | S3 P5：列表包含 A，不包含 B | S3 T5 | DB1 | 记录本身的时间保持不变 |
| S3-6 成功作品链接 | consumed | S3 R6 entry 作品链接 | S3 P6：浏览器打开该条记录的 TikTok 作品 | S3 T6 | DB1 | 不打开其他账号作品或任意非TikTok地址 |
| S3-7 失败原因与文案 | consumed | S3 R7 display 记录详情 | S3 P7：看到完整文案、原视频路径、执行阶段和“视频上传失败”原因 | S3 T7 | DB1, Visual Contract VC1 | 没有伪造作品链接，长文案不挤坏列表 |
| S3-8 无记录 | consumed | S3 R8 empty 初始历史 | S3 P8：看到“暂无发布记录”或“没有符合条件的发布记录” | S3 T8 | DB1, Visual Contract VC1 | 页面可用，允许返回发布页或清空筛选 |
| S3-9 待确认重新核验 | consumed | S3 R9 state 重新核验成功 | S3 P9：原记录从“待确认”变为“已确认成功”，链接为 V101 | S3 T9 | SD1, DB1 | 原视频和文案快照保持不变，没有重新上传或再次发布 |
| S3-10 重新核验仍不确定 | consumed | S3 R10 state 保留待确认 | S3 P10：记录仍为“待确认”，展示本次核验未找到匹配作品 | S3 T10 | SD1, DB1 | 不自动重发，也不新增一条发布尝试 |

| S1-19 重复启动同一请求 | consumed | S1 R19 state 启动重放 | S1 P19：返回B1原进度 | S1 T19 | SD1, DB1 | 不重建批次、不重复发布、已接受B1不重复扣额 |
| S1-20 冲突启动请求 | consumed | S1 R20 rejection 不可变请求 | S1 P20：提示请求内容与原任务不一致 | S1 T20 | SD1, DB1 | B1原文案仍为“海边日常”，不重复扣额 |
| S1-21 额度结果不明 | consumed | S1 R21 rejection 额度不确定 | S1 P21：提示额度结果无法确认、任务未启动 | S1 T21 | SD1, DB1 | 不自动重试额度、不打开浏览器，不声称额度未扣 |
| S1-22 DOCX环境不可用 | consumed | S1 R22 rejection 导入环境 | S1 P22：提示更新WebView2或另存TXT | S1 T22 | Visual Contract VC1, External Dependency ED1 | 原文案仍为“人工稿”，直接输入和TXT仍可使用 |
| S1-23 超长文件保留原文 | consumed | S1 R23 rejection 导入文案超限 | S1 P23：完整显示4001字符并提示上限4000，开始发布禁用 | S1 T23 | Visual Contract VC1, External Dependency ED1 | 不截断文案、不打开浏览器 |
| S2-18 没有上传提示 | consumed | S2 R18 state 无可选弹窗 | S2 P18：自动填写文案“海边日常”并提交一次 | S2 T18 | SD1, DB1 | 不要求人工寻找Turn on或Got it |
| S2-19 弹窗顺序变化 | consumed | S2 R19 state 反序弹窗 | S2 P19：依次处理Got it、Turn on后填写文案 | S2 T19 | SD1, DB1 | 不要求人工处理，不进入视频编辑 |
| S2-20 浏览器启动失败仍继续 | consumed | S2 R20 state 账号启动隔离 | S2 P20：tiktok_1显示启动失败，tiktok_2仍开始发布 | S2 T20 | SD1, DB1 | B1视频和文案保持不变，不把tiktok_1记成功 |
| S3-11 隔天同文案不误确认 | consumed | S3 R11 rejection 非本次作品 | S3 P11：B1仍为待确认 | S3 T11 | SD1, DB1 | 不把V202记作B1成功链接、不再次发布 |
| 图片作品 | out | - | - | - | - | 用户明确第一版无入口 |
| 原生纯文字作品 | out | - | - | - | - | 用户明确第一版无入口 |
| 定时发布 | out | - | - | - | - | 本期仅立即发布，无定时发布入口 |
| 每账号不同素材 | deferred | - | - | - | - | 当前要求是一份视频文案分发；本期无该入口 |
| 旧版Word二进制 .doc | consumed | S1 R8 rejection 格式错误 | S1 P8：保留人工修改稿并提示另存 | S1 T8 | External Dependency ED1 | 与损坏/不可解析文件同形失败，不能静默丢草稿 |

## Committed Claims

| ID | Unknown | Claim | Evidence | Consumer |
| --- | --- | --- | --- | --- |
| C1 | U1 | 一份视频路径及输入框最终文案供一个固定账号批次使用；人工不再干预外站文件选择与文案填写 | EV1 | S1、S2、S3 |
| C2 | U2/U11 | publishing组下publish与publish-records，两角色同养号；仅TikTok有videoPublishing；既有主题和组件优先 | EV2, EV11 | D1、VC1、S1 T1/T2/T18、S3 T1 |
| C3 | U3 | Rust独占现有运行槽；队列继承publish_batch_id；明确tiktok_publish/publish以及tiktok_publish_verify/publish_verify映射；启动失败也推进后续账号 | EV3 | D3、SD1、S1 T9-T15、S2 T12-T15 |
| C4 | U4 | 复用三provider和auth，提取本人handle导航，不把完整成果采集当核验；原handle贯穿提交前与核验后 | EV4 | D5/D6、S2 T1-T3/T7-T11/T17 |
| C5 | U5/U9 | 视频原生单选返回路径；文案共用输入框；TXT/DOCX解析成功才替换；不支持.doc和表格转换 | EV5, EV9 | D2、S1 T3-T8/T16 |
| C6 | U6 | actions.db新增batch快照及account record；每batch/account唯一；提交前committing先持久化；历史与核验同一事实源 | EV6, EV8 | D4、DB1、S2 T8-T17、S3 |
| C7 | U7 | 严格用户截图流程；可选弹窗有限处理；Description整体替换与回读；单次Post；真实发布需三浏览器证据 | EV1, EV7 | D5、ED1、S2 T1-T6 |
| C8 | U8 | 提交之后不确定一律pending_confirmation；恢复及重新核验无上传和Post；不声称exactly-once | EV8 | D4/D6、SD1、S2 T9/T14、S3 T9/T10 |
| C9 | U10 | 同现有任务一次批次一次额度；人工重新核验作为新运行任务沿用一次额度；无新套餐或服务端改动 | EV10 | D3、S1 T15、S3 T9 |

## Story Slices

| ID | Actor | Value Change / Acceptance Boundary | Release Mode | Depends On | Product Contract | Technical Contract | Slice Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | 已登录运营 | 通过菜单准备唯一的视频/文案/账号批次，失败不发帖 | ship | 现有登录/配置 | contracts/S1-prepare-publication.feature | contracts/S1-prepare-publication.tech.feature | 业务准备与输入拒绝独立审阅 |
| S2 | 已登录运营 | 自动逐账号发布，并区分主页确认、待确认、失败及取消 | ship | S1 | contracts/S2-publish-and-verify.feature | contracts/S2-publish-and-verify.tech.feature | 外部写入和同作品核验形成完整价值 |
| S3 | 已登录运营 | 查询每账号历史事实，待确认仅重新核验 | ship | S2 | contracts/S3-publication-records.feature | contracts/S3-publication-records.tech.feature | 历史查询与受限恢复不承担重发 |

三个Story共同发行；ship仅指实施完成并通过证明后可发布，不表示本轮已上线。

## Design Decisions

| ID | Design Question | Evidence Route | Decision | Rejected Underfit | Rejected Overfit | Minimal Sufficiency | Proof Target |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | 菜单和访问边界放哪里 | Repo EV2/EV11；官方/生态 N/A: repo-authoritative，角色及路由结构为本应用既定事实 | 扩展menuGroup与videoPublishing能力，发布组标题展开并默认导航publish；两页当前平台作用域 | 只加菜单但客户白名单/后端能力遗漏 | 为两个子页引入新路由框架或全局菜单重构 | 当前需求只需两route和一个capability；复用既有壳，停止于局部布局 | S1 T1/T2/T11/T18；S3 T1 |
| D2 | 路径与文案如何输入 | Repo EV5；EV8原生文件API；EV9严格解码/XML/解压能力挑战 | 新增原生单选命令，保留本地视频；抽取ZIP读取供DOCX文案解析，单一caption TextArea | 依赖HTML File.path；把代理清洗直接复用导致空段丢失 | 视频复制服务、Office进程或云Word转换 | 当前需要路径和纯文本，保留现有栈；只加最小共享解析，停止于排版不进入Word渲染 | S1 T3-T8/T16/T17 |
| D3 | 批量发布如何接入运行器 | Repo EV3/EV10；EV7挑战CDP与上传；授权含义以仓库为准无需外部替代 | 新增run_tiktok_publish/recheck_tiktok_publish入口，共用RunState运行槽及队列，显式任务映射、固定batch引用；发布分支失败继续 | 仅首进程传路径、任务类型落入fyp、每账号重复扣额 | 第二套调度器、并发worker和远程队列 | 当前逐账号需求只加强现有队列；不改其他任务的语义，停止于发布专属接线 | S1 T9-T15；S2 T1-T3/T12-T15 |
| D4 | 如何保存发布事实并防重复 | Repo EV6；EV8 SQLite事务挑战外部不可事务化 | 新增publish_batches和publish_records；本地事务/条件更新，先committing落盘再单次Post；中断保守pending_confirmation | action_log文本恢复、把进程退出0当成功、自动重试Post | 分布式事务、outbox、全站永久素材去重 | 当前历史与不确定外部写入分别要求批次快照和逐账号记录；二表一事实源，不引入后台重发，停止于最小字段 | DB1；S1 T9-T12；S2 T8-T17；S3 T2 |
| D5 | 外站上传和弹窗怎样处理 | Repo EV4/EV5；EV7 Playwright官方动作与用户截图挑战 | 新增platforms/tiktok/publish.py；单一CDP动作链，已知弹窗按标题限定处理，等待Uploaded，Description回读，Post单次提交 | 屏幕固定坐标、盲点按钮、固定sleep后认成功 | 官方API授权体系、移动端模拟、私有签名接口重放 | 当前截图动作足以定义状态契约；实际DOM由实现读取可回退locators，未知页面不误发；停止于不加编辑能力 | S2 T1-T7/T11；ED1 |
| D6 | 怎样证明是本次本人作品 | Repo EV4的handle识别；EV7响应/页面观察；EV8外部不确定性挑战 | 抽取当前账号主页导航；新增基线与唯一作品匹配、有限轮询及verify-only恢复 | 置顶第一条、同文案、计数变动或toast即成功 | 强求不可获得的文件hash与TikTok媒体二进制相同、私有接口重放 | 当前要求本人主页可证，拿不到唯一证据就待确认；同一核验器被发布及重新核验共用，不加第二权威 | S2 T8-T11/T17；S3 T9/T10 |
| D7 | 记录查询和恢复放哪里 | Repo EV6/EV2；安全范围官方/生态 N/A: repo-authoritative，本机已登录用户的actions.db并非服务端多租户模型 | 新增发布记录查询命令/页面，参数筛选、分页、详情和仅待确认重新核验 | 泛日志无法按作品关联，错误当空数据 | 跨设备历史同步、新导出权限、记录删除和自动重发入口 | 当前两页只共用DB1；路径/文案属于本机历史，凭据不存，保留现有桌面授权；停止于当前筛选与恢复 | S3 T1-T10 |

## Design Supports

### Visual Contract VC1 桌面发布与记录

平台为Windows桌面WebView，品牌采用现有AI/YAOWU蓝色主题；沿用App.tsx明暗token（浅色主色#3662ec，深色主色#76a9ff）、controlHeight=36、controlHeightSM=32、borderRadius=10及已有字体。新页复用PageHeader、Antd Card/Form/Input.TextArea/Select/Table/Drawer、StatusTag、AccountBrowserEnvironment和ProcessOutputPanel，不复制TikTok的红色视觉。

一级菜单 publishing（发布作品），子项 publish（发布作品）、publish-records（发布记录）。组标题点击时导航publish并展开；对子项的选择不被组标题事件覆盖；键盘展开/收起不强行导航。路由hash、面包屑/页标题与选中项一致。加入CUSTOMER_ROUTE_KEYS，技术员沿用现有访问；非TikTok不显示可执行发布组，直接入口显示UnsupportedCapabilityState而不是启动任务。

发布页从上到下：标题；视频选择卡（文件名、绝对路径可换行/复制、大小、重新选择）；文案卡（TextArea、计数、导入TXT/DOCX）；账号卡（single/selected/all和provider信息）；唯一主操作“开始发布”；运行进度区。文案无需模式开关，文件成功解析后才进入替换确认。空文案可发布；4000 UTF-16单元为业务校验上限，不设置会截断输入的maxLength属性。输入/导入的超长原文完整保留，计数报错并禁用开始，后端独立拒绝超限请求。视频无内嵌播放要求，不引入本地媒体服务。确认启动弹窗沿用养号模式，显示内容与账号摘要；确认后才启动浏览器。

记录页首屏筛选账号、状态、创建日期范围及重置；表格每账号一行：创建时间、账号、视频名、文案摘要、状态、提交时间、作品链接/详情；文案全文和路径在Drawer，提交前失败的提交时间为“—”；待确认提供“重新核验”，运行中禁用。状态以文字及图标表达，不只颜色。不得展示cookie、密码或token。

1440/1280/1024px实测：桌面主容器沿用壳内距，卡片内部16-20px、区块24px，标题20/28、正文14/22、辅助12/18；样式与现有相邻页一致优先。1024px表单单列、表格横滚，长路径/中文/emoji不遮主按钮。覆盖默认、hover/focus、禁用、导入加载、上传/核验中、空、失败和超长内容；明暗主题各检查。移动端原生应用不在范围，不新增390px交付承诺。

### External Dependency ED1 TikTok与本地文件契约

1. 视频选择：Windows GetOpenFileNameW单选，OFN_FILEMUSTEXIST/OFN_PATHMUSTEXIST/OFN_NOCHANGEDIR；取消null，错误明确。返回canonical absolute path、sizeBytes/modifiedNs字符串（避免JS大整数精度丢失），支持中文、空格和合法长路径。筛选mp4/webm/mov，空文件拒绝。截图显示的30GB/60分钟不是所有账号固定平台上限，不编造统一硬编码。最终格式/时长/容量不合格由TikTok页面可见错误终止本账号，不自动转码。
2. 视频不复制：启动前Rust取得size/mtime快照，每账号Python上传前/上传后比对；这些只是文件元数据指纹，不声称内容hash或防恶意同大小同mtime替换。业务使用约定为执行期间不修改原文件；不存在/变化/不可读直接失败，不改用同名其他文件。
3. 文案：TXT严格UTF-8（允许BOM），仅统一行尾，保留空行。DOCX仅读word/document.xml；从正文段落依次提取w:t，w:br/w:cr为换行、w:tab为tab，空段保留；段落末尾加换行，去掉算法自身最后一个分隔符但不trim内容。超链接保留显示文字；图片、样式、页眉页脚忽略；表格、修订或嵌套内容无法无歧义提取时拒绝并提示另存TXT，不能悄悄漏正文。XML DTD/外部实体不解析，DOM不插入页面。旧.doc拒绝。文件上限2MiB、目标XML解压上限8MiB、条目上限10000，ZIP偏移/长度校验，仅读目标条目并流式限量；超限原子失败。ZIP共享低层抽取不改变既有代理导入的清洗含义；保留既有调用兼容。
4. DOCX运行前提：WebView2支持DecompressionStream('deflate-raw')；探测失败提供“当前运行环境无法解析DOCX，请更新WebView2或另存TXT”，保留原稿。发行验收必须用目标安装版验证正常DOCX成功，不能把该提示当DOCX支持的成功证据。初版不增加压缩依赖或Office安装要求。
5. Upload：登录后优先点击TikTok左侧导航Upload，并验证目标为https://www.tiktok.com/tiktokstudio/upload（允许本域重定向的同类上传页）。监听同页或新标签，复用原context，禁止创建新的无登录context。Select video用expect_file_chooser→set_files；若控件已可定位，可直接set_input_files同一绝对路径，两者都不操控Windows资源管理器。只对唯一且属于视频上传区域的控件赋值；找不到或多义则失败并保存截图。
6. 已知弹窗：Turn on automatic content checks? → Turn on；New editing features added → Got it。两者可无、有、先后互换，上传/填写/提交前均检测遮罩；仅匹配标题容器，最多6轮、总30秒，处理后等待容器消失；未知阻挡提示明确失败/人工处理，不点任意“确认”。Turn on会按用户明确要求开启截图所示内容检查，不代选Cancel。
7. 等待：导航60秒；上传/处理各最多20分钟；每250-1000ms检查状态且响应停止，已知上传错误立即失败。这些是可调代码常量的等待上限，不是外站成功SLA。Uploaded标记、视频预览/Details可编辑、Post可用共同约束就绪；无Uploaded明确证据不Post。外站检查若出现版权/限制错误按原文记录失败，不自动绕过。Description可能为contenteditable，优先语义定位，清空文件名自动描述后填入最终caption，规范CRLF后回读一致；空caption也要清空默认文件名。超外站限制或内容不一致不Post。When to post确保Now；其他封面/地点/可见范围/评论设置保留当前页面默认，不加入配置页。
8. 提交：Post滚入视区，唯一可用，先持久化committing和提交尝试时间，事务commit确认后执行一次非force click（timeout30秒），不得让调用方自动重试；点击超时也可能已触发，保持待确认。可观察该正常页面请求/响应获取post_id、发布状态、作者和作品链接；不构造、签名或重放私有接口。即使页面提示成功也必须进入本人主页。
9. 本人主页：抽取logged_in_handle + open_current_account_profile，保留成果展示现有行为；从当前登录Profile链接识别handle，用临时标签打开本人主页，不使用配置ID推用户名，不读取Liked/activity。任务起始handle为本次身份锚点，提交前再次匹配，核验前后继续匹配。
10. 发布前基线：保存本人主页Videos所加载的去重作品ID及采集时间、完整性标记；仅记录“已看到”不能声称完整全量。基线无法读取或账号不唯一时不执行Post，避免无证据发送。发布后轮询总180秒，间隔5秒，逐次刷新页面，读取候选及详情。
11. 成功证据：必须获取与同一次Post正常响应/跳转明确关联的post_id，并在相同handle主页Videos中发现该ID，点开详情校验作者和文案，才verified。响应关联取不到时，新增ID、相同作者/文案、发布时间只作为辅助候选，保持pending_confirmation，不能独立确认本次作品。候选时间窗口固定为原submitted_at前2分钟至其后5分钟；重新核验不扩大窗口，隔天人工发布的同文案视频绝不能被算作本次。仅部分基线缺失的新卡片、置顶位置、数量变化、toast均不够；不猜测或生成post_id。
12. 接口/DOM实测边界：用户截图并非完整DOM，不能预写虚构data-e2e选择器。实现时通过目标浏览器读取实际role/label/text/input/contenteditable和响应结构，集中到publish模块的locators和标准化观察结果中。语义已由上述契约封闭；外站页面没有对应元素则明确失败，不另换业务流程。三provider真实发布及本人主页同对象核验是发行门槛，离线fixture只能证明分支，不能冒充线上验收。

### Sequence Diagram SD1 批次与外部提交边界

~~~text
运营/发布页       Rust运行器             actions.db            Python/CDP             TikTok
   |                  |                      |                    |                     |
   | run_tiktok_publish(request) ----------->|                    |                     |
   |                  | 校验路径/账号/互斥/授权                    |                     |
   |                  | 预留运行槽；沿用远程task quota一次          |                     |
   |                  | BEGIN: INSERT batch及全部account rows --->|                     |
   |                  | COMMIT <-------------|                    |                     |
   |                  | 首账号及后续账号均携batch_id ------------->|                     |
   |                  |                      | CAS queued→running |                     |
   |                  |                      |<-------------------|                     |
   |                  |                      |                    | provider/auth/Profile基线 -->|
   |                  |                      | 保存handle/基线 <---|                     |
   |                  |                      |                    | Upload/Select video/弹窗/Description -->|
   |                  |                      | BEGIN CAS running→committing              |
   |                  |                      |<-------------------|                     |
   |                  |                      | COMMIT ----------->|                     |
   |                  |                      |                    | Post（一次） ------->|
   |                  |                      |                    |<-- 正常响应或超时    |
   |                  |                      |                    | 本人主页轮询 ------->|
   |                  |                      | verified / pending_confirmation <--------|
   |<-----------------| 单账号结果，继续下一账号                  |                     |
   |                  |                      |                    |                     |
   | 强停/崩溃        | 提交前→cancelled；committing后→pending_confirmation                |
   | 重新核验 -------->| 同运行槽与一次quota；以record_id执行verify-only ------------------>|
   |                  |                      | 仅更新原记录核验证据，绝不重新上传/Post    |
~~~

SQLite短事务只覆盖本地写入；事务内不等待网络/浏览器。提交标记的写入失败就不允许Post。precommit故障明确failed；committing后没有明确外站拒绝且未见作品一律pending_confirmation。若外站明确拒绝该次Post，记录failed及原文，不依据超时推断失败。

启动顺序：在current_run互斥锁下完成运行槽预留，再释放锁做额度请求；其他任务看到starting而拒绝。本地验证与空账号拒绝先于额度。结构性账号错误（跨平台、disabled、缺profile绑定）启动前拒绝；实际provider连接、CDP、登录等可用性必须逐账号判定，不能用批量provider可用性检查提前终止整个队列。额度拒绝释放预留且不创建可执行批次。额度请求设15秒超时，未知结果不自动重试、不启动浏览器，提示“额度结果无法确认，任务未启动”。额度已扣但DB创建前崩溃不能被本地requestId完全去重，重新创建任务可能再次扣额，这是沿用现有远程额度接口无幂等键的已知边界，本期不承诺跨该窗口额度exactly-once或自动退款。已接受批次只扣一次，队列与重新读取既有批次不重复扣。首次子进程启动失败也写该账号failed并继续后续账号；全部启动失败才批次failed。普通单账号问题不能清空整个发布队列。

发布与核验的task映射：desktop tiktok_publish → AM_TASK_TYPE=publish；desktop tiktok_publish_verify → AM_TASK_TYPE=publish_verify。Python requested_tiktok_task显式识别两者，并在run_session鉴权后分发；无AM_PUBLISH_BATCH_ID/record_id不允许执行。未知非空任务类型显式报错，空环境维持已有full兼容；Rust未知task映射不能落入fyp。发布分支不运行FYP/target/完整成果采集。

任务队列本次由Rust持有，Python每账号只执行一次；不再调用Python批量路径。RunState增加publish_batch_id及可选publish_record_id，reset清理；spawn_account_process为每一个子进程传这些ID，长文案/视频数据不放命令行或shell插值。运行时沿用src/main.py --account与打包runtime run --account入口，config/data路径不另造；Python通过batch_id加载DB权威快照。

批次结果汇总：所有记录verified才completed；有verified又有failed/skipped/cancelled/pending_confirmation则partial_failed；无verified且有failed/skipped/pending_confirmation则failed并在页面明确“存在待确认”；用户停止保留stopped。单账号committing后pending_confirmation不能转成确定失败。运行进程状态与逐账号业务状态分开，不将child exit=0等同发布成功。新增发布进度通过AM_PUBLISH_EVENT单行JSON（batch_id,record_id,account_id,phase,status,error）关联到现有输出读取与轮询，DB是最终事实源，stdout事件不得直接授权状态倒退。

Data Claim DC1: 不可变本地发布内容由publish_batches持有，逐账号尝试与主页证据由publish_records持有，batch/account唯一；Rust创建/取消/协调与查询、Python条件推进执行阶段，共用actions.db状态协议；生命周期仅追加批次、推进原记录、不删历史；加法建表不回填旧日志，不改变旧表；证明目标为S1 T9-T12、S2 T8-T17、S3 T2-T10。

### Database Diagram DB1 本地发布任务与逐账号事实

~~~text
+--------------------------------------------------------------------------------+
| [新增表] publish_batches（发布批次）                                              |
+--------------------------------------------------------------------------------+
| id TEXT NOT NULL COMMENT '批次唯一标识'                                         |
| platform TEXT NOT NULL DEFAULT 'tiktok' COMMENT '发布平台固定TikTok'              |
| video_path TEXT NOT NULL COMMENT '本地视频规范绝对路径'                           |
| video_size_bytes INTEGER NOT NULL COMMENT '启动时视频字节数'                      |
| video_modified_ns TEXT NOT NULL COMMENT '启动时文件修改时间纳秒字符串'             |
| caption TEXT NOT NULL DEFAULT '' COMMENT '启动时输入框最终文案'                   |
| created_at TEXT NOT NULL COMMENT '本次任务创建时间UTC'                            |
| PRIMARY KEY (id)                                                               |
+--------------------------------------------------------------------------------+
publish_batches.id
       (1)
        |
        | 包含
        |
      (1..*)
publish_records.batch_id
+--------------------------------------------------------------------------------+
| [新增表] publish_records（逐账号发布记录）                                        |
+--------------------------------------------------------------------------------+
| id TEXT NOT NULL COMMENT '记录唯一标识'                                         |
| batch_id TEXT NOT NULL COMMENT '所属发布批次'                                   |
| account_id TEXT NOT NULL COMMENT '执行账号标识保留历史'                           |
| provider TEXT NOT NULL COMMENT '启动时浏览器类型'                               |
| profile_binding_json TEXT NOT NULL COMMENT '非敏感浏览器绑定快照'                 |
| ordinal INTEGER NOT NULL COMMENT '批次中账号执行顺序'                            |
| status TEXT NOT NULL DEFAULT 'queued' COMMENT '业务执行状态'                     |
| phase TEXT NOT NULL DEFAULT 'queued' COMMENT '最近执行阶段'                      |
| handle TEXT NULL COMMENT '任务开始识别的登录用户名'                              |
| baseline_json TEXT NULL COMMENT '发布前已观察作品及采集范围'                      |
| submitted_at TEXT NULL COMMENT '进入提交尝试时间UTC并非确认成功时间'              |
| post_id TEXT NULL COMMENT '本次关联作品标识'                                     |
| post_url TEXT NULL COMMENT '主页确认后的作品链接'                               |
| error_code TEXT NULL COMMENT '稳定原因代码'                                     |
| error_detail TEXT NULL COMMENT '已脱敏中文原因及外站提示'                         |
| evidence_json TEXT NULL COMMENT '最近核验依据候选和截图引用'                     |
| verified_at TEXT NULL COMMENT '最后确认成功时间UTC'                              |
| updated_at TEXT NOT NULL COMMENT '最近阶段或重新核验时间UTC'                     |
| PRIMARY KEY (id)                                                               |
| UNIQUE KEY uq_publish_batch_account (batch_id, account_id)                       |
| UNIQUE KEY uq_publish_batch_ordinal (batch_id, ordinal)                          |
| KEY idx_publish_record_account (account_id, batch_id)                           |
+--------------------------------------------------------------------------------+
~~~

图中COMMENT为评审注释，SQLite实际DDL用SQL注释表达；UNIQUE KEY/KEY投影为SQLite UNIQUE与CREATE INDEX IF NOT EXISTS。id为前端生成的唯一requestId并直接作为batch id；不以文件路径/文案作唯一键，用户可以主动创建新批次再次发布同素材。同一桌面进程中的starting请求在RunState暂存requestId及规范输入摘要，重复点击返回starting而不再次扣额；已创建批次的同requestId重放先查原记录，输入一致返回原状态，不插入/排队/扣额；不同规范视频路径、文案或非all账号列表则拒绝request_conflict，不可修改原快照。all重放以原账号名单为准，不重新展开当前配置。首次调用额度完成但本地DB尚无记录时崩溃的去重限制见SD1，不声称跨该窗口额度幂等。重新核验沿用record_id，不创建新批次。

profile_binding_json只允许provider对应profile_id或builtin用户数据目录，不存代理密码/登录凭据；每账号启动时验证当前绑定与快照一致，变化则failed/binding_changed且继续下一账号，凭据仍由安全存储实时读取。caption原文只在batch一次保存；文件名由video_path派生，账号显示按历史account_id，不因配置删除级联删记录；batch状态由records汇总，不另存一份可漂移字段。

status枚举：queued、running、intervention_required、committing、verifying、verified、pending_confirmation、failed、skipped、cancelled。phase只记录最近步骤：queued/opening/authenticating/baseline/uploading/uploaded/prompts/caption/submitting/verifying/finished；它不是第二套结果。intervention_required只发生提交前登录阶段，继续回running或跳过为skipped；对未知发布页阻挡先保存截图并以failed/unsupported_page退出，用户未授权的未知动作不猜。

允许转换：queued→running；running↔intervention_required；running→committing；committing→verifying；verifying→verified/pending_confirmation；running/queued→failed/skipped/cancelled；明确外站Post拒绝允许committing→failed；committing/verifying在异常、中断时→pending_confirmation；pending_confirmation经verify-only→verified或保持pending_confirmation。终态verified不得回退；失败/取消不能经重新核验变成一次新发布。执行前CAS queued→running，提交前CAS running→committing，只有affected_rows=1才拥有本次动作权；重复进程不能重做。提交信息与基线写入失败则禁止Post。重新核验用同一RunState运行槽，不将status改回running而丢失提交不确定事实。

Rust commands/publishing.rs为建表、批次创建、查询、恢复协调的所有者；Python platforms/tiktok/publish_store.py为读取不可变batch及条件推进record的所有者。两端共享以上状态定义和契约测试，禁止直接随意UPDATE。SQLite连接busy_timeout=5000，短事务，任何写失败禁止外站写动作；不为本功能强改全库journal模式。migration用一个事务CREATE TABLE/INDEX IF NOT EXISTS，重复执行安全，旧actions.db原表不动，旧版应用可继续读取旧表；没有历史发布数据可回填。仅query时DB/表不存在返回空；DB损坏或读权限错误返回错误，不当空。

立即停止的裁决以DB条件更新而不是先读phase决定：Rust先在短事务将本批queued/running/intervention_required行条件置cancelled；Python只有CAS running→committing成功才可提交。取消CAS先赢则Python提交CAS失败、Post次数为0；提交CAS先赢则该行不能被取消覆盖，Rust终止并确认子进程已退出后将尚未有终态的committing/verifying置pending_confirmation。若进程尚未确认退出，显示“正在停止”，不能清掉提交标记或宣告取消。正常完成的verified不得被停止覆盖。完成当前账号后停止不取消当前行，只取消剩余queued。

恢复前确认current_run无活跃子进程、data/run.lock所指PID确实已退出；PID查询异常不能沿用旧pid_alive“异常即死亡”的结论，保持记录并提示无法确认运行状态。存在活进程不协调。重启后queued取消为“应用中断，未执行”，running/intervention_required在提交前标记failed/interrupted_before_submit，committing/verifying标记pending_confirmation；不自动恢复发帖。Python实际执行前仍复用原runtime锁和CAS。不同桌面进程争用已有记录由CAS防双发；不扩展为多实例分布式调度。

evidence_json为有界结构：{version:1, reason, observed_at, author_handle, correlated_post_id, candidate_ids:[最多30], match_basis, baseline_complete, screenshot_path?}；baseline_json {captured_at, handle, ids:[最多100], complete:false或明确完整证据}。截图存data/publish-evidence/{record_id}/最近一次PNG，应用仅显示已存在的本机受控路径，不嵌入凭据；重核验覆盖最近证据文件而不无限累积。没有截图也保存结构化原因，不捏造成功证据。文件删除不删除记录。

### Command Contract CC1 接线与查询

- select_publish_video() → null 或 {path,fileName,sizeBytes,modifiedNs}。仅Windows桌面命令，非桌面预览清晰提示不可用；不以HTML File.path冒充。
- run_tiktok_publish({requestId,platform:'tiktok',mode:'single'/'selected'/'all',accountIds,videoPath,caption}) → ProcessStartResult追加batchId。canonical元数据由后端重新读取，不能信任前端size。未知platform/mode拒绝；single精确1，selected非空去重保序，all后端解析配置顺序并固定enabled名单；backend重新校验，无可执行账号/非法选择不运行。caption保留换行、允许空串、最多4000 UTF-16单元；拒绝NUL但不沿用禁止换行的validate_safe_text。
- recheck_tiktok_publish({recordId}) → ProcessStartResult，taskType=tiktok_publish_verify；仅pending_confirmation且非其他运行中；只登录/本人主页核验，不读取原视频文件也不要求其仍存在，不重新上传/填写/Post；原绑定变化时保持待确认并报原因。复用原handle、baseline、submitted_at及correlated_post_id证据。
- query_publish_records({platform:'tiktok',accountId?,status?,from?,to?,page:1,pageSize:20}) → {items,total,page,pageSize}。时间为创建时间from含/to不含的UTC RFC3339。状态白名单，page>=1，pageSize 1..100，组合AND；账号精确匹配；排序batch.created_at DESC, record.id DESC；含完整文案/详情字段，UI列表摘要详情全文。SQL全部参数绑定；删除账号不丢历史。
- 复用stop_current_process/stop_after_current_account、continue_auth_intervention/skip_auth_intervention、get_current_run_status和open_external_link；新增命令统一注册main.rs，并由api.ts发布PROCESS_STARTED_EVENT。外链仅https TikTok精确域的作品路径，禁止任意协议。
- 后端videoPublishing能力仅TikTok supported；videoPublishing进入PlatformCapability union、所有平台capability map与Rust supported矩阵；publish-records用同一平台隔离。沿用登录用户能访问养号的角色范围，无服务端新权限或表变更。

### Design Part Closure

| Part | Kind | Owner | Consumer | Fitness Force | Delete/Merge Failure | Proof Target |
| --- | --- | --- | --- | --- | --- | --- |
| publishing菜单/两route/videoPublishing | routes/capability | 既有routes与config能力矩阵 | S1/S3入口 | Product Force: 两子页及TikTok范围 | 删除会缺入口；漏客户白名单无法进入 | S1 T1/T2/T18、S3 T1 |
| select_publish_video | command | commands/files.rs | 路径选择 | Platform Force: 原生绝对路径 | 合并成HTML File将无法可靠提供完整路径 | S1 T3 |
| captionImport共享ZIP/XML读取 | module | desktop/src/services/captionImport.ts及officeImport.ts | TXT/DOCX填入同一输入框 | Product Force: 文件导入且不损文案 | 删除无法导入；照搬代理清洗会丢空行 | S1 T5-T8/T16 |
| publish_batches | table/fields | commands/publishing.rs | 队列共享输入及历史 | Data-State Force: 不可变输入 | 合并进RunState重启后无法恢复原内容；逐账号重复存快照易漂移 | S1 T9-T12；S3 T2/T7 |
| publish_records及唯一/账号索引 | table/fields | Rust与Python状态协议 | 执行/筛选/恢复 | Data-State Force: 账号结果不同 | 合并为一条batch状态无法区分账号；删除唯一键允许同批账号重复 | S2 T8-T17；S3 T2-T10 |
| committing/pending_confirmation状态及CAS | state | publish_store.py / 恢复协调 | 外部提交与中断 | Operational Force: Post不可事务化 | 合并为failed会诱导重发；合并success会伪造确认 | S2 T9/T14；S3 T9/T10 |
| RunState批次引用与显式publish映射 | state/task | commands/process.rs | 每个队列子进程 | Repo Force: 每账号spawn | 删除会只首账号有素材或误跑fyp | S1 T10/T12；S2 T1-T3/T12 |
| publish与verify模块/共享本人导航 | module | platforms/tiktok + profile_stats | 外站动作与复核 | Proof Force: 本次本人作品 | 删除核验无法证明新作品；每Story另建核验会产生双事实标准 | S2 T8-T11/T17；S3 T9/T10 |
| AM_PUBLISH_EVENT | event | Python输出与Rust读取 | 两页运行进度 | Repo Force: 已有stdout运行面板 | 只本地页面状态无法在切页后关联同批进度 | S2 T1-T3/T12 |
| query_publish_records/记录页 | command/page | commands/publishing.rs与PublishRecordsPage | 历史筛选详情 | Product Force: 独立发布记录 | 删除只剩通用日志，无法给出逐账号历史 | S3 T1-T8 |
| recheck_tiktok_publish | command/task | 现有运行器verify-only分支 | 待确认恢复 | Operational Force: 中断后须先核验 | 合并到发布入口会可能重新点击Post | S3 T9/T10 |
| evidence_json/最近PNG | fields/artifact | 核验器 | 作品关联与错误解释 | Proof Force: 同对象证据 | 删除后历史只剩无法审阅的成功字样 | S2 T8-T11；S3 T7 |

当前与仓库适配：三Story共用DB1、SD1、一个队列和一个核验器；没有第二素材服务/调度器/事实所有者。边界演进仅保留平台能力与module分支，图片/文字没有字段/任务实现；后续若真实要求另行设计。设计停止于可逆定位器命名/组件拆分，不把业务语义交给实施猜。

## Implementation Iterations

| Iteration | Consumer / Work | Required Proof / Stop Boundary |
| --- | --- | --- |
| I1 输入与数据边界 | S1；VC1；原生选择、文案导入；DB1创建、唯一与快照、菜单/角色/能力 | 中文路径真实Windows选择；UTF8 BOM/换行/emoji、DOCX空段/软换行/表格拒绝；旧库迁移两次和失败回滚；未知publish任务绝不FYP |
| I2 单账号上传与确认 | S2；先BitBrowser贯通；当前handle、基线、Upload、弹窗、Description、Post、主页核验 | 浏览器fixture证明已知/无弹窗/反序/失败/误判；真实账号完成上传→Post→主页同作品关联；没有证据只待确认 |
| I3 批量与三provider | S1 T9-T15/T19-T21、S2 T1-T3/T12-T17；每进程继承batch，预检失败推进、停止、恢复 | 单/多/全部名单固定；首/中账号失败继续；committing前后注入中断；在SD1承诺范围内重复invoke无重复队列/扣额，额度不确定无自动重试；ixBrowser和builtin真实链 |
| I4 历史与重新核验 | S3；筛选分页、详情、外链、verify-only | 原始batch文案不漂移；已删账号仍可查；北京时间边界；无表空态vs错误；原视频已删除仍能verify-only且Post调用为0 |
| I5 发行证据与回归 | 3Story共同验收；source/bundled运行时 | 真实三provider+中文空格路径；目标WebView2 DOCX；source/bundled任务映射一致；原养号/注册/成果采集不回归；无授权或运行环境则如实UNTESTED，不宣称完成 |

落点清单（拟修改或新增，均在account-matrix）：
- desktop/src/app/routes.tsx、routePermissions.ts、components/AppShell.tsx、platforms/types.ts、platforms/common/capabilities.ts及各平台能力；新增platforms/tiktok/pages/PublishPage.tsx、PublishRecordsPage.tsx并从pages/index导出。
- desktop/src/services/api.ts/types.ts；新增captionImport.ts、按最小范围抽取officeImport.ts共享ZIP；BrowserProfilePage保留原代理格式规则；ProcessOutputPanel支持发布阶段而不改已有auth按钮语义。
- desktop/src-tauri/src/commands/files.rs（原生打开），新增commands/publishing.rs，commands/mod.rs/main.rs注册；state.rs发布引用；process.rs启动/映射/队列推进/stop/恢复与事件；commands/config.rs能力。
- src/platforms/tiktok/runner.py显式publish/publish_verify分支；新增publish.py与publish_store.py；src/profile_stats.py抽取本人主页导航并让旧采集复用；不得把新导航误改为当前被浏览的他人主页。
- src/main.py/core.runner/runtime_cli沿用现有run协议，检查task事件/结果汇总与exit code；runtime/pyinstaller/account-matrix-runtime.spec现有collect_submodules('platforms')包含新模块，新增动态import时同步hiddenimports并验证安装版，不能只跑开发态。
- 生产测试只在实施阶段新增：Python unittest浏览器夹具/SQLite迁移状态；Rust单元/集成命令/队列测试；前端纯导入与菜单交互测试；三provider实机验收。此计划不创建生产测试或环境特定Acceptance BDD。

验证命令约定：Python用python -m unittest discover -s src -p "test_*_unit.py"（先跑新增聚焦用例，再跑受影响existing）；Rust用cargo test --manifest-path desktop/src-tauri/Cargo.toml；前端pnpm --dir desktop build及既有test:platform-boundary/test:platform-final（被新增能力影响的静态枚举同步，不以静态检查替代交互）；安装版通过既有runtime构建脚本生成并运行run协议。实际发帖验证使用可发布测试账号和可用浏览器，按用户提供动作执行，记录账号/作品ID/阶段/截图，不把模拟TikTok当真实站点。

## Contract Index

- S1：contracts/S1-prepare-publication.feature；contracts/S1-prepare-publication.tech.feature（23组Product/Technical场景）。
- S2：contracts/S2-publish-and-verify.feature；contracts/S2-publish-and-verify.tech.feature（20组Product/Technical场景）。
- S3：contracts/S3-publication-records.feature；contracts/S3-publication-records.tech.feature（11组Product/Technical场景）。

## Trace & Readiness

Scope Closure: EV1每个可验收动作在Product Examples逐项consumed；无入口的延后范围明确列出。
Question Closure: U1-U11均由合格来源闭合；没有须用户决定的新业务策略；实施中的DOM探测有ED1的停止/失败语义。
Evidence Closure: EV1-EV11均有来源、证明边界和下游消费者；未将截图、静态代码或官方CDP支持误当真实发布成功。
Design Closure: D1-D7从repo基线出发，逐项用官方证据挑战或精确的repo-authoritative理由闭合。
Design Fitness Closure: 当前三Story共享队列、快照和核验标准；Part Closure说明每个新部分的当前消费者与删合并后果；不引入远程架构。
Contract Closure: Product P与Technical T逐项对应；SD1/DB1/VC1/ED1消除顺序、存储、UI与外站边界猜测。
Guess Closure: 输入、角色/平台、任务类型、快照传递、提交状态、恢复、唯一作品判据、迁移、查询及证明责任已确定；具体locator只在明确ED1契约内实施，不改变产品含义。
Closure Gate: pass
Closure Claim: PASS

C1-C9 → S1/S2/S3 → 各Rule/场景 → 同编号Technical证明；# Evidence/# Decisions/# Uses绑定到以上卡片、D1-D7和实际支持。此结论须以当前包的validate_source_destinations、validate_product_bdd_shape、validate_evidence_references及validate_closure_gate全部成功为准；主代理另做语义遗漏审阅。

## Open Items

无影响实施选择的未决项。真实TikTok登录、目标provider运行环境和安装版WebView2为实施/验收输入，并非本轮已经验证；未运行任何发帖或创建云资源。截图中未显示的Post具体DOM必须实机读取并按ED1记录；找不到就明确失败，不允许猜按钮或跳过本人主页核验。

