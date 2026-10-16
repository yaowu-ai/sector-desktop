Feature: S2 自动发布并核验本人作品
  # Actor: 已登录的桌面端运营用户
  # Source: 本聊天中已确认需求，design.md 的 Product Examples

  Rule: R1 state 浏览器兼容

    Scenario: P1 BitBrowser发布
      Given tiktok_1 绑定 BitBrowser，已登录，待发海边.mp4和文案“海边日常”
      When 执行该账号的发布任务
      Then 该账号在 TikTok 上传页自动提交海边.mp4和“海边日常”
      And 不要求人工再选视频或填写文案，不执行养号动作

  Rule: R2 state 浏览器兼容

    Scenario: P2 ixBrowser发布
      Given tiktok_2 绑定 ixBrowser，已登录，待发海边.mp4和文案“海边日常”
      When 执行该账号的发布任务
      Then 该账号在 TikTok 上传页自动提交海边.mp4和“海边日常”
      And 不要求人工再选视频或填写文案，不执行养号动作

  Rule: R3 state 浏览器兼容

    Scenario: P3 内置浏览器发布
      Given tiktok_3 使用内置 Chromium 独立用户目录，已登录，待发海边.mp4和文案“海边日常”
      When 执行该账号的发布任务
      Then 该账号在 TikTok 上传页自动提交海边.mp4和“海边日常”
      And 不要求人工再选视频或填写文案，不执行养号动作

  Rule: R4 state 可选内容检查

    Scenario: P4 开启内容检查
      Given tiktok_1 上传海边.mp4后出现“Turn on automatic content checks?”
      When 该账号继续自动发布
      Then 自动点击该弹窗的 Turn on 后继续填写文案
      And 没有改选 Cancel 或取消已选检查项

  Rule: R5 state 可选编辑引导

    Scenario: P5 关闭编辑引导
      Given tiktok_1 上传海边.mp4后出现“New editing features added”
      When 该账号继续自动发布
      Then 自动点击该引导的 Got it 后继续填写文案
      And 没有进入 Edit、Sounds 或 Text 编辑流程

  Rule: R6 rejection 上传失败

    Scenario: P6 上传未完成
      Given tiktok_1 正在上传海边.mp4，页面明确提示上传失败
      When 该账号完成本次尝试
      Then 结果显示“发布失败：视频上传失败”
      And 没有点击 Post，也不显示发布成功

  Rule: R7 state 登录验证

    Scenario: P7 登录接管
      Given tiktok_1 当前未登录且遇到需要人工完成的验证码
      When 执行该账号的发布任务
      Then 任务显示“需要人工处理”并保持账号浏览器可操作
      And 验证码完成前不提交视频作品

  Rule: R8 state 成功核验

    Scenario: P8 确认本次作品
      Given tiktok_1 已提交海边.mp4，其主页原有旧视频 V100，本次提交关联视频 V101
      When 完成本人主页核验
      Then 结果由“正在核验”变为“已确认成功”，展示 V101 的作品链接
      And 不将 V100 当作本次作品，原视频和文案快照保持不变

  Rule: R9 state 待确认

    Scenario: P9 不确定发布结果
      Given tiktok_1 已点击 Post，只有成功提示，但本人主页尚未出现可唯一关联的新视频
      When 核验等待到期
      Then 结果为“待确认”并说明主页尚未确认本次作品
      And 不显示已确认成功，不自动再次点击 Post

  Rule: R10 rejection 旧作品证据

    Scenario: P10 旧作品不误判
      Given tiktok_1 已提交海边.mp4，主页第一张卡片是旧置顶视频 V100且文案也为“海边日常”
      When 完成本次作品核验
      Then 结果仍为“待确认”
      And 不把 V100 的链接记录为本次成功作品

  Rule: R11 rejection 身份不一致

    Scenario: P11 账号身份变化
      Given 任务开始识别到当前账号为 @alice，提交前检测到账号已变为 @bob
      When 继续该账号的发布任务
      Then 结果显示“发布失败：当前登录账号发生变化”
      And 不向 @bob 点击 Post

  Rule: R12 state 批量隔离

    Scenario: P12 账号失败后继续
      Given 批次 B1 含 tiktok_1、tiktok_2，tiktok_1 在提交前上传失败
      When 继续执行 B1
      Then tiktok_2 仍按 B1 的视频和文案开始执行
      And tiktok_1 的失败结果保持不变

  Rule: R13 state 取消未提交

    Scenario: P13 立即停止前置阶段
      Given B1 中 tiktok_1 正在上传且尚未进入提交阶段，tiktok_2 还在队列
      When 运营立即停止 B1
      Then tiktok_1 和 tiktok_2 均显示“已取消”
      And 没有继续点击 Post，既有历史成功记录保持不变

  Rule: R14 state 不重复提交

    Scenario: P14 提交后中断
      Given tiktok_1 已进入提交阶段，程序随后中断，尚无主页核验结果
      When 重新打开应用
      Then 该记录显示“待确认：提交阶段中断”
      And 不自动恢复上传或再次点击 Post

  Rule: R15 state 停止排队

    Scenario: P15 完成当前账号后停止
      Given B1 中 tiktok_1 正在核验，tiktok_2 尚未执行
      When 运营选择完成当前账号后停止
      Then tiktok_1 完成核验后 tiktok_2 显示“已取消”
      And tiktok_1 的核验结果不被取消覆盖

  Rule: R16 rejection 素材变动

    Scenario: P16 上传前文件变化
      Given B1 的 tiktok_1 已完成，tiktok_2 尚未上传；海边.mp4 的大小或修改时间相对启动时发生变化
      When 执行 tiktok_2
      Then tiktok_2 显示“发布失败：视频文件已变化”
      And 不为 tiktok_2 上传变化后的视频，tiktok_1 结果不变

  Rule: R17 state 核验身份异常

    Scenario: P17 提交后身份变化
      Given tiktok_1 已提交作品，核验时主页显示另一个登录账号 @bob
      When 完成本次核验
      Then 记录显示“待确认：核验账号不一致”
      And 不声称提交失败，也不将 @bob 的作品记为成功

  Rule: R18 state 无可选弹窗

    Scenario: P18 没有上传提示
      Given 海边.mp4已Uploaded且没有内容检查或编辑引导提示
      When 继续tiktok_1自动发布
      Then 自动填写文案“海边日常”并提交一次
      And 不要求人工寻找Turn on或Got it

  Rule: R19 state 反序弹窗

    Scenario: P19 弹窗顺序变化
      Given tiktok_1上传后先出现编辑引导，再出现内容检查
      When 继续该账号自动发布
      Then 依次处理Got it、Turn on后填写文案
      And 不要求人工处理，不进入视频编辑

  Rule: R20 state 账号启动隔离

    Scenario: P20 浏览器启动失败仍继续
      Given B1包含tiktok_1及tiktok_2，第一个BitBrowser窗口无法打开，第二个环境正常
      When 继续执行B1
      Then tiktok_1显示启动失败，tiktok_2仍开始发布
      And B1视频和文案保持不变，不把tiktok_1记成功

