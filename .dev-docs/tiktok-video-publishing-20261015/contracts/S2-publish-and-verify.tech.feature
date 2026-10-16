Feature: S2 自动发布并核验本人作品技术证明
  # Profile: mixed-system
  # 每条证明仅对 # Surface 声明的边界负责；模拟外站不能证明真实发布成功。

  Scenario: S2 T1 BitBrowser发布证明
    # Proof: Acceptance
    # Surface: TikTok Studio / BitBrowser
    # Entry: run_tiktok_publish
    # Covers: S2 P1
    # Uses: SD1, External Dependency ED1
    # Decisions: D3, D5
    # Evidence: EV1, EV4, EV7
    Given tiktok_1 绑定 BitBrowser，已登录，待发海边.mp4和文案“海边日常”
    When 经 run_tiktok_publish 触发 S2 P1 的同一业务事件
    Then 真实 CDP 会话点击 Upload；接住同页跳转或新标签；expect_file_chooser 配合 Select video 后 set_files，或对唯一视频 input set_input_files；检查 Uploaded、Description 回读、Post 可用后只点击一次；记录真实请求和页面证据
    And 验证 S2 P1 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T2 ixBrowser发布证明
    # Proof: Acceptance
    # Surface: TikTok Studio / ixBrowser
    # Entry: run_tiktok_publish
    # Covers: S2 P2
    # Uses: SD1, External Dependency ED1
    # Decisions: D3, D5
    # Evidence: EV1, EV4, EV7
    Given tiktok_2 绑定 ixBrowser，已登录，待发海边.mp4和文案“海边日常”
    When 经 run_tiktok_publish 触发 S2 P2 的同一业务事件
    Then 对 ixBrowser 数字 profile_id 的真实 CDP 会话执行与 BitBrowser 同一上传链；不能用 provider 类型检查替代实际发布证据
    And 验证 S2 P2 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T3 内置浏览器发布证明
    # Proof: Acceptance
    # Surface: TikTok Studio / builtin_chromium
    # Entry: run_tiktok_publish
    # Covers: S2 P3
    # Uses: SD1, External Dependency ED1
    # Decisions: D3, D5
    # Evidence: EV1, EV4, EV7
    Given tiktok_3 使用内置 Chromium 独立用户目录，已登录，待发海边.mp4和文案“海边日常”
    When 经 run_tiktok_publish 触发 S2 P3 的同一业务事件
    Then 真实本地 CDP 上传中文空格绝对路径；新建标签仍使用该账号 context，覆盖本地 Chrome/Edge 的文件选择事件
    And 验证 S2 P3 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T4 开启内容检查证明
    # Proof: Acceptance
    # Surface: TikTok Studio dialogs
    # Entry: handle_known_upload_prompts
    # Covers: S2 P4
    # Uses: SD1, External Dependency ED1
    # Decisions: D5
    # Evidence: EV1, EV7
    Given tiktok_1 上传海边.mp4后出现“Turn on automatic content checks?”
    When 经 handle_known_upload_prompts 触发 S2 P4 的同一业务事件
    Then 在匹配标题的对话框内部精确定位 Turn on；仅弹窗可见时处理，重新检查遮罩已消失；不同出现顺序用有界循环，不全局点击同名按钮
    And 验证 S2 P4 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T5 关闭编辑引导证明
    # Proof: Acceptance
    # Surface: TikTok Studio dialogs
    # Entry: handle_known_upload_prompts
    # Covers: S2 P5
    # Uses: SD1, External Dependency ED1
    # Decisions: D5
    # Evidence: EV1, EV7
    Given tiktok_1 上传海边.mp4后出现“New editing features added”
    When 经 handle_known_upload_prompts 触发 S2 P5 的同一业务事件
    Then 限定匹配引导容器处理 Got it，覆盖仅此弹窗、两个弹窗顺序互换、均不出现；无弹窗不能等待到超时才继续
    And 验证 S2 P5 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T6 上传未完成证明
    # Proof: Server
    # Surface: platforms/tiktok/publish.py
    # Entry: run_tiktok_publish
    # Covers: S2 P6
    # Uses: SD1
    # Decisions: D5
    # Evidence: EV1, EV7
    Given tiktok_1 正在上传海边.mp4，页面明确提示上传失败
    When 经 run_tiktok_publish 触发 S2 P6 的同一业务事件
    Then 用浏览器夹具模拟上传失败和持续进度，分别验证 failed/upload_failed 与 failed/upload_timeout，Post 调用数为0；真实验收记录截图
    And 验证 S2 P6 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T7 登录接管证明
    # Proof: Server
    # Surface: platforms/tiktok/runner.py
    # Entry: ensure_tiktok_authenticated
    # Covers: S2 P7
    # Uses: SD1
    # Decisions: D3, D5
    # Evidence: EV1, EV4
    Given tiktok_1 当前未登录且遇到需要人工完成的验证码
    When 经 ensure_tiktok_authenticated 触发 S2 P7 的同一业务事件
    Then 复用 auth 事件和 continue/skip；继续后重验 identity 才上传，skip 标记 skipped；不得生成或绕过验证码；provider 清理遵循现有关闭配置
    And 验证 S2 P7 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T8 确认本次作品证明
    # Proof: Acceptance
    # Surface: TikTok profile
    # Entry: verify_published_video
    # Covers: S2 P8
    # Uses: SD1, DB1, External Dependency ED1
    # Decisions: D4, D6
    # Evidence: EV1, EV4, EV7
    Given tiktok_1 已提交海边.mp4，其主页原有旧视频 V100，本次提交关联视频 V101
    When 经 verify_published_video 触发 S2 P8 的同一业务事件
    Then 登录导航识别handle，临时页进入本人主页Videos；必须作者一致且精确匹配同一次Post正常响应或跳转关联的post_id；无关联ID只保存候选并保持待确认；保存基线、核验依据和截图，不调用Liked/activity
    And 验证 S2 P8 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T9 不确定发布结果证明
    # Proof: Server
    # Surface: platforms/tiktok/publish.py
    # Entry: verify_published_video
    # Covers: S2 P9
    # Uses: SD1, DB1, External Dependency ED1
    # Decisions: D4, D6
    # Evidence: EV1, EV6, EV7
    Given tiktok_1 已点击 Post，只有成功提示，但本人主页尚未出现可唯一关联的新视频
    When 经 verify_published_video 触发 S2 P9 的同一业务事件
    Then 提交前 committing commit 成功后才允许点击；等待策略到期后 pending_confirmation，preserve submitted_at/candidates；伪造toast或作品数变化不足以成功
    And 验证 S2 P9 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T10 旧作品不误判证明
    # Proof: Server
    # Surface: platforms/tiktok/publish.py
    # Entry: verify_published_video
    # Covers: S2 P10
    # Uses: SD1, DB1
    # Decisions: D6
    # Evidence: EV1, EV4
    Given tiktok_1 已提交海边.mp4，主页第一张卡片是旧置顶视频 V100且文案也为“海边日常”
    When 经 verify_published_video 触发 S2 P10 的同一业务事件
    Then fixture 中固定旧置顶、相同文案、多个新候选、缺时间证据，均不能 verified；只有唯一正确同对象证据才成功
    And 验证 S2 P10 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T11 账号身份变化证明
    # Proof: Server
    # Surface: platforms/tiktok/publish.py
    # Entry: assert_current_identity
    # Covers: S2 P11
    # Uses: SD1
    # Decisions: D5, D6
    # Evidence: EV1, EV4
    Given 任务开始识别到当前账号为 @alice，提交前检测到账号已变为 @bob
    When 经 assert_current_identity 触发 S2 P11 的同一业务事件
    Then 上传前及 committing 前核对最初 handle；主页核验身份不一致时仅 pending_confirmation/identity_mismatch，不声称提交前失败；不凭账号配置 id 推算用户名
    And 验证 S2 P11 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T12 账号失败后继续证明
    # Proof: Server
    # Surface: commands/process.rs
    # Entry: spawn_exit_monitor
    # Covers: S2 P12
    # Uses: SD1, DB1
    # Decisions: D3, D4
    # Evidence: EV1, EV3
    Given 批次 B1 含 tiktok_1、tiktok_2，tiktok_1 在提交前上传失败
    When 经 spawn_exit_monitor 触发 S2 P12 的同一业务事件
    Then 发布任务专属启动失败处理继续推进剩余有效队列，禁止首个 provider 不可用清空全部；批次结果由记录汇总，Python 返回明确 exit code，不以退出0替代 verified
    And 验证 S2 P12 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T13 立即停止前置阶段证明
    # Proof: Server
    # Surface: commands/process.rs
    # Entry: stop_current_process
    # Covers: S2 P13
    # Uses: SD1, DB1
    # Decisions: D3, D4
    # Evidence: EV1, EV3, EV6
    Given B1 中 tiktok_1 正在上传且尚未进入提交阶段，tiktok_2 还在队列
    When 经 stop_current_process 触发 S2 P13 的同一业务事件
    Then 取消通过条件UPDATE与提交CAS竞争，取消先赢则Post调用为0，提交先赢则确认子进程退出后记pending_confirmation；未确认退出保持正在停止；停止后不再推进队列，重启仅在旧进程退出后reconcile
    And 验证 S2 P13 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T14 提交后中断证明
    # Proof: Server
    # Surface: publishing recovery
    # Entry: reconcile_publish_records
    # Covers: S2 P14
    # Uses: SD1, DB1
    # Decisions: D4
    # Evidence: EV1, EV3, EV6
    Given tiktok_1 已进入提交阶段，程序随后中断，尚无主页核验结果
    When 经 reconcile_publish_records 触发 S2 P14 的同一业务事件
    Then 仅确认旧子进程已退出/锁已释放后协调遗留行；committing/verifying 不回退到 queued；compare-and-set 防止启动双执行；同 batch/account 不能再次发布
    And 验证 S2 P14 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T15 完成当前账号后停止证明
    # Proof: Server
    # Surface: commands/process.rs
    # Entry: stop_after_current_account
    # Covers: S2 P15
    # Uses: SD1, DB1
    # Decisions: D3, D4
    # Evidence: EV1, EV3
    Given B1 中 tiktok_1 正在核验，tiktok_2 尚未执行
    When 经 stop_after_current_account 触发 S2 P15 的同一业务事件
    Then 沿用 stop_after_current，当前发布保持执行到终态、剩余 queued 原子取消；汇总页不把 pending_confirmation 算成功
    And 验证 S2 P15 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T16 上传前文件变化证明
    # Proof: Server
    # Surface: platforms/tiktok/publish.py
    # Entry: validate_publish_source
    # Covers: S2 P16
    # Uses: SD1, DB1
    # Decisions: D2, D4
    # Evidence: EV1, EV3
    Given B1 的 tiktok_1 已完成，tiktok_2 尚未上传；海边.mp4 的大小或修改时间相对启动时发生变化
    When 经 validate_publish_source 触发 S2 P16 的同一业务事件
    Then 每个账号 set_input_files 前比较 canonical_path,size_bytes,modified_ns，并在上传完成后重验；变化则不Post，批次不复制素材，metadata指纹不声称内容级去重
    And 验证 S2 P16 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T17 提交后身份变化证明
    # Proof: Server
    # Surface: platforms/tiktok/publish.py
    # Entry: verify_published_video
    # Covers: S2 P17
    # Uses: SD1, DB1
    # Decisions: D6
    # Evidence: EV1, EV4
    Given tiktok_1 已提交作品，核验时主页显示另一个登录账号 @bob
    When 经 verify_published_video 触发 S2 P17 的同一业务事件
    Then 提交后 identity_mismatch 与提交前failed分开；不再次Post，持久化最初handle和候选证据
    And 验证 S2 P17 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T18 没有上传提示证明
    # Proof: Server
    # Surface: publishing runtime
    # Entry: handle_known_upload_prompts
    # Covers: S2 P18
    # Uses: SD1, DB1
    # Decisions: D3, D4, D5
    # Evidence: EV1, EV7
    Given 海边.mp4已Uploaded且没有内容检查或编辑引导提示
    When 经 handle_known_upload_prompts 触发 S2 P18 的同一业务事件
    Then 无弹窗为正常分支，不固定等30秒；验证文案回读和单次Post
    And 验证 S2 P18 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T19 弹窗顺序变化证明
    # Proof: Server
    # Surface: publishing runtime
    # Entry: handle_known_upload_prompts
    # Covers: S2 P19
    # Uses: SD1, DB1
    # Decisions: D3, D4, D5
    # Evidence: EV1, EV7
    Given tiktok_1上传后先出现编辑引导，再出现内容检查
    When 经 handle_known_upload_prompts 触发 S2 P19 的同一业务事件
    Then 根据当前可见标题容器处理而非写死顺序，遮罩消失后继续Description
    And 验证 S2 P19 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S2 T20 浏览器启动失败仍继续证明
    # Proof: Server
    # Surface: publishing runtime
    # Entry: spawn_account_process
    # Covers: S2 P20
    # Uses: SD1, DB1
    # Decisions: D3, D4, D5
    # Evidence: EV1, EV3
    Given B1包含tiktok_1及tiktok_2，第一个BitBrowser窗口无法打开，第二个环境正常
    When 经 spawn_account_process 触发 S2 P20 的同一业务事件
    Then 只批量检查结构合法性；provider/spawn失败逐账号写failed并推进剩余队列，含首和中账号
    And 验证 S2 P20 的可见结果及不变量，证据绑定同一批次和账号

