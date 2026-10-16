Feature: S1 准备视频发布任务技术证明
  # Profile: mixed-system
  # 每条证明仅对 # Surface 声明的边界负责；模拟外站不能证明真实发布成功。

  Scenario: S1 T1 一级菜单展开证明
    # Proof: UI
    # Surface: AppShell/routes
    # Entry: buildSiderMenuItems
    # Covers: S1 P1
    # Uses: Visual Contract VC1
    # Decisions: D1
    # Evidence: EV1, EV2
    Given 运营当前位于首页，平台为 TikTok
    When 经 buildSiderMenuItems 触发 S1 P1 的同一业务事件
    Then 校验分组 key=publishing，children 为 publish、publish-records，点击分组默认进入 publish，直接 hash 定位子页后父菜单展开
    And 验证 S1 P1 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T2 发布页入口证明
    # Proof: UI
    # Surface: PublishPage
    # Entry: publish route
    # Covers: S1 P2
    # Uses: Visual Contract VC1
    # Decisions: D1
    # Evidence: EV1, EV2
    Given 运营当前处于 TikTok 平台
    When 经 publish route 触发 S1 P2 的同一业务事件
    Then 以普通客户和技术员角色分别访问 publish，确认两者沿用养号角色可见性，RouteScopeFrame 使用 videoPublishing 能力
    And 验证 S1 P2 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T3 选择本地路径证明
    # Proof: Server
    # Surface: commands/files.rs
    # Entry: select_publish_video
    # Covers: S1 P3
    # Uses: External Dependency ED1
    # Decisions: D2
    # Evidence: EV1, EV5, EV8
    Given 运营发布表单尚未选择视频，文案为“海边日常”
    When 经 select_publish_video 触发 S1 P3 的同一业务事件
    Then 调用 Windows GetOpenFileNameW 单选，返回规范绝对路径、sizeBytes 十进制字符串和 modifiedNs 十进制字符串；取消返回 null 且原选择不变；中文空格路径往返无损
    And 验证 S1 P3 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T4 直接输入文案证明
    # Proof: UI
    # Surface: PublishPage
    # Entry: caption editor
    # Covers: S1 P4
    # Uses: Visual Contract VC1
    # Decisions: D2
    # Evidence: EV1, EV5
    Given 运营文案输入框原值为空，已选择海边.mp4
    When 经 caption editor 触发 S1 P4 的同一业务事件
    Then 受控 TextArea 保留换行、emoji 和话题，按 JS UTF-16 长度显示计数，不使用代理导入的行拆分清洗
    And 验证 S1 P4 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T5 TXT文案导入证明
    # Proof: UI
    # Surface: captionImport.ts
    # Entry: importCaptionFile
    # Covers: S1 P5
    # Uses: External Dependency ED1
    # Decisions: D2
    # Evidence: EV1, EV5, EV9
    Given 运营已选择海边.mp4，文案为空，caption.txt 为 UTF-8 含两行“海边日常\n#旅行”
    When 经 importCaptionFile 触发 S1 P5 的同一业务事件
    Then 支持 UTF-8 BOM，用 fatal TextDecoder 检测损坏；仅统一 CRLF/CR 为 LF，禁止 trim 或丢空行
    And 验证 S1 P5 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T6 Word文案导入证明
    # Proof: UI
    # Surface: captionImport.ts
    # Entry: importCaptionFile
    # Covers: S1 P6
    # Uses: External Dependency ED1
    # Decisions: D2
    # Evidence: EV1, EV5, EV9
    Given 运营文案为空，caption.docx 正文含“海边”、一个空段和“#旅行”
    When 经 importCaptionFile 触发 S1 P6 的同一业务事件
    Then 从 ZIP 中仅解压 word/document.xml，以命名空间 DOM 读取正文顶层段落及 w:t、w:br、w:tab；保留空段，拒绝表格而非悄悄省略，忽略格式和图片；XML 失败不替换原文
    And 验证 S1 P6 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T7 覆盖确认证明
    # Proof: UI
    # Surface: PublishPage
    # Entry: caption replace confirmation
    # Covers: S1 P7
    # Uses: Visual Contract VC1
    # Decisions: D2
    # Evidence: EV1, EV5
    Given 运营文案原值为“人工修改稿”，新 caption.txt 内容为“文件稿”
    When 经 caption replace confirmation 触发 S1 P7 的同一业务事件
    Then 仅解析成功后提示替换；确认则整体替换，取消不改值；解析期间禁用重复导入和开始，防止异步旧结果覆盖新编辑
    And 验证 S1 P7 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T8 无效文案文件证明
    # Proof: UI
    # Surface: captionImport.ts
    # Entry: importCaptionFile
    # Covers: S1 P8
    # Uses: External Dependency ED1
    # Decisions: D2
    # Evidence: EV1, EV5, EV9
    Given 运营文案为“人工修改稿”，选择旧版 caption.doc
    When 经 importCaptionFile 触发 S1 P8 的同一业务事件
    Then .doc、损坏 ZIP/XML、无正文、超限、无法解码或不支持解压均原子失败；不得执行宏或向网络上传文案文件
    And 验证 S1 P8 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T9 单账号证明
    # Proof: Server
    # Surface: commands/process.rs
    # Entry: run_tiktok_publish
    # Covers: S1 P9
    # Uses: SD1, DB1
    # Decisions: D3, D4
    # Evidence: EV1, EV3, EV6
    Given 运营已选海边.mp4及文案“海边日常”，tiktok_1 和 tiktok_2 均已启用
    When 经 run_tiktok_publish 触发 S1 P9 的同一业务事件
    Then 验证 mode=single 仅一 ID、所属 TikTok、enabled、videoPublishing、provider 绑定；在同一事务创建 batch 及唯一 account row
    And 验证 S1 P9 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T10 多账号证明
    # Proof: Server
    # Surface: commands/process.rs
    # Entry: run_tiktok_publish
    # Covers: S1 P10
    # Uses: SD1, DB1
    # Decisions: D3, D4
    # Evidence: EV1, EV3
    Given 运营已选同一视频和文案，tiktok_1、tiktok_2、tiktok_3 均已启用
    When 经 run_tiktok_publish 触发 S1 P10 的同一业务事件
    Then selected 模式去重保序，RunState.publish_batch_id 持续到队列耗尽，每次 spawn 均传 AM_PUBLISH_BATCH_ID；不重读表单作为输入
    And 验证 S1 P10 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T11 全部账号证明
    # Proof: Server
    # Surface: commands/process.rs
    # Entry: run_tiktok_publish
    # Covers: S1 P11
    # Uses: SD1, DB1
    # Decisions: D1, D3
    # Evidence: EV1, EV2, EV3
    Given 运营有启用的 tiktok_1、tiktok_2，停用的 tiktok_3 及启用的 instagram_1
    When 经 run_tiktok_publish 触发 S1 P11 的同一业务事件
    Then all 模式由后端解析账号；按配置顺序固定去重列表；新增能力 TikTok supported、其他平台 not_supported；复用账号上限和授权预检
    And 验证 S1 P11 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T12 启动后固定内容证明
    # Proof: Server
    # Surface: publishing database
    # Entry: batch snapshot
    # Covers: S1 P12
    # Uses: DB1, SD1
    # Decisions: D3, D4
    # Evidence: EV1, EV3, EV6
    Given 批次 B1 已用海边.mp4及文案“海边日常”为 tiktok_1、tiktok_2 启动，tiktok_2 尚未开始
    When 经 batch snapshot 触发 S1 P12 的同一业务事件
    Then 批次输入只从 publish_batches 读取；前端编辑不更新批次；队列账号由 publish_records 的 ordinal 及 RunState 队列锁定
    And 验证 S1 P12 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T13 失效视频证明
    # Proof: Server
    # Surface: commands/process.rs
    # Entry: run_tiktok_publish
    # Covers: S1 P13
    # Uses: SD1
    # Decisions: D2, D3
    # Evidence: EV1, EV3, EV8
    Given 运营已选 D:\Videos\海边.mp4，但该文件在开始前被删除
    When 经 run_tiktok_publish 触发 S1 P13 的同一业务事件
    Then 拒绝相对路径、目录、不可读、空文件及非 mp4/webm/mov；开始前获取权威 stat，执行前再次比较路径大小时间；每账号不匹配即失败，禁止换文件继续
    And 验证 S1 P13 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T14 无可用账号证明
    # Proof: Server
    # Surface: commands/process.rs
    # Entry: run_tiktok_publish
    # Covers: S1 P14
    # Uses: SD1
    # Decisions: D3
    # Evidence: EV1, EV3
    Given 运营账号列表中没有已启用 TikTok 账号，视频路径有效
    When 经 run_tiktok_publish 触发 S1 P14 的同一业务事件
    Then 选择为空、disabled、跨平台或缺绑定均启动前拒绝，验证先于 reserve_daily_task_quota；没有静默跳过选中非法账号
    And 验证 S1 P14 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T15 互斥与授权证明
    # Proof: Server
    # Surface: commands/process.rs
    # Entry: run_tiktok_publish
    # Covers: S1 P15
    # Uses: SD1
    # Decisions: D3
    # Evidence: EV1, EV3, EV10
    Given 运营的养号任务仍在执行，发布表单视频及文案有效
    When 经 run_tiktok_publish 触发 S1 P15 的同一业务事件
    Then 启动预留在 current_run mutex 下串行；授权缺失或额度拒绝不运行；启动成功批次只占一次额度，沿用现有 reserve-task 计费，不逐账号重复计数
    And 验证 S1 P15 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T16 确认覆盖文案证明
    # Proof: UI
    # Surface: PublishPage
    # Entry: caption replace confirmation
    # Covers: S1 P16
    # Uses: Visual Contract VC1
    # Decisions: D2
    # Evidence: EV1, EV5
    Given 运营文案原值为“人工修改稿”，新 caption.txt 内容为“文件稿”
    When 经 caption replace confirmation 触发 S1 P16 的同一业务事件
    Then 解析成功后确认一次整体替换；与取消分支独立证明，文件解析失败不弹替换成功
    And 验证 S1 P16 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T17 文案过长证明
    # Proof: Server
    # Surface: commands/process.rs
    # Entry: run_tiktok_publish
    # Covers: S1 P17
    # Uses: External Dependency ED1
    # Decisions: D2, D5
    # Evidence: EV1, EV7
    Given 运营已选择有效视频，输入框文案长度超过页面显示的4000上限
    When 经 run_tiktok_publish 触发 S1 P17 的同一业务事件
    Then 前后端一致使用 UTF-16 单元计数 <=4000，空串允许；外站更低限制以实际错误失败，不自动截断；忽略 filename 自动文案并覆盖为最终编辑框值
    And 验证 S1 P17 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T18 非TikTok入口拒绝证明
    # Proof: UI
    # Surface: RouteScopeFrame
    # Entry: publish route guard
    # Covers: S1 P18
    # Uses: Visual Contract VC1
    # Decisions: D1
    # Evidence: EV1, EV2
    Given 技术员当前选择 Instagram 平台
    When 经 publish route guard 触发 S1 P18 的同一业务事件
    Then videoPublishing 在非TikTok为not_supported，直接hash与invoke同样拒绝，发布记录也按平台scope隔离；无需改其他平台可执行状态
    And 验证 S1 P18 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T19 重复启动同一请求证明
    # Proof: Server
    # Surface: publishing runtime
    # Entry: run_tiktok_publish
    # Covers: S1 P19
    # Uses: SD1, DB1
    # Decisions: D3, D4, D5
    # Evidence: EV1, EV3, EV10
    Given 已接受B1使用海边.mp4、文案“海边日常”
    When 经 run_tiktok_publish 触发 S1 P19 的同一业务事件
    Then 同requestId先查RunState starting摘要和DB；同输入返回原状态；仅承诺SD1的幂等范围
    And 验证 S1 P19 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T20 冲突启动请求证明
    # Proof: Server
    # Surface: publishing runtime
    # Entry: run_tiktok_publish
    # Covers: S1 P20
    # Uses: SD1, DB1
    # Decisions: D3, D4, D5
    # Evidence: EV1, EV3, EV10
    Given B1原文案为“海边日常”
    When 经 run_tiktok_publish 触发 S1 P20 的同一业务事件
    Then canonical路径/文案/非all账号列表冲突报request_conflict；all重放保留原名单；不得先扣额度再拒绝
    And 验证 S1 P20 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T21 额度结果不明证明
    # Proof: Server
    # Surface: publishing runtime
    # Entry: run_tiktok_publish
    # Covers: S1 P21
    # Uses: SD1, DB1
    # Decisions: D3, D4, D5
    # Evidence: EV1, EV3, EV10
    Given 视频与账号有效，但额度请求网络超时，任务尚未接受
    When 经 run_tiktok_publish 触发 S1 P21 的同一业务事件
    Then reserve-task15秒超时，只请求一次且释放starting；跨远程成功到本地建批崩溃窗口限制按SD1明示
    And 验证 S1 P21 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T22 DOCX环境不可用证明
    # Proof: UI
    # Surface: captionImport.ts
    # Entry: importCaptionFile
    # Covers: S1 P22
    # Uses: Visual Contract VC1, External Dependency ED1
    # Decisions: D2
    # Evidence: EV1, EV5, EV9
    Given 原文案为“人工稿”，当前WebView无法解压DOCX
    When 经 importCaptionFile 触发 S1 P22 的同一业务事件
    Then deflate-raw不可用时不覆盖原稿，目标安装版DOCX正常成功另需真实证据
    And 验证 S1 P22 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S1 T23 超长文件保留原文证明
    # Proof: UI
    # Surface: captionImport.ts
    # Entry: importCaptionFile
    # Covers: S1 P23
    # Uses: Visual Contract VC1, External Dependency ED1
    # Decisions: D2
    # Evidence: EV1, EV5, EV7
    Given caption.txt有4001个英文字符，输入框原值为空
    When 经 importCaptionFile 触发 S1 P23 的同一业务事件
    Then 不使用TextArea硬maxLength，showCount/validator按UTF16，后端独立拒绝超限；保留输入原值
    And 验证 S1 P23 的可见结果及不变量，证据绑定同一批次和账号

