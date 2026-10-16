Feature: S3 查询逐账号发布记录技术证明
  # Profile: mixed-system
  # 每条证明仅对 # Surface 声明的边界负责；模拟外站不能证明真实发布成功。

  Scenario: S3 T1 记录入口证明
    # Proof: UI
    # Surface: PublishRecordsPage
    # Entry: publish-records route
    # Covers: S3 P1
    # Uses: Visual Contract VC1
    # Decisions: D1, D7
    # Evidence: EV1, EV2
    Given 运营当前位于发布作品表单
    When 经 publish-records route 触发 S3 P1 的同一业务事件
    Then 普通客户及技术员均可进入，TikTok scope 下读取 query_publish_records；菜单默认展开与hash定位一致
    And 验证 S3 P1 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S3 T2 批量独立记录证明
    # Proof: Server
    # Surface: commands/publishing.rs
    # Entry: query_publish_records
    # Covers: S3 P2
    # Uses: DB1
    # Decisions: D4, D7
    # Evidence: EV1, EV6
    Given B1 的 tiktok_1 已确认成功，tiktok_2 上传失败，两者视频均为海边.mp4
    When 经 query_publish_records 触发 S3 P2 的同一业务事件
    Then 按 account record 联 batch 快照查询，展示 createdAt/submittedAt 分开；路径filename在前端取，不复制为另一列；provider snapshot 随记录可查
    And 验证 S3 P2 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S3 T3 账号筛选证明
    # Proof: Server
    # Surface: commands/publishing.rs
    # Entry: query_publish_records
    # Covers: S3 P3
    # Uses: DB1
    # Decisions: D7
    # Evidence: EV1, EV6
    Given 历史中包含 tiktok_1 成功记录和 tiktok_2 失败记录
    When 经 query_publish_records 触发 S3 P3 的同一业务事件
    Then 参数绑定 accountId exact match，与status/date组合 AND；账号已删除时仍可用历史 account_id 过滤
    And 验证 S3 P3 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S3 T4 状态筛选证明
    # Proof: Server
    # Surface: commands/publishing.rs
    # Entry: query_publish_records
    # Covers: S3 P4
    # Uses: DB1
    # Decisions: D7
    # Evidence: EV1, EV6
    Given 历史中有已确认成功、待确认和发布失败三类记录
    When 经 query_publish_records 触发 S3 P4 的同一业务事件
    Then status 枚举白名单与parameterized query；中间态不混为成功；页大小默认20上限100，稳定按 created_at DESC,id DESC 排序
    And 验证 S3 P4 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S3 T5 时间筛选证明
    # Proof: Server
    # Surface: commands/publishing.rs
    # Entry: query_publish_records
    # Covers: S3 P5
    # Uses: DB1
    # Decisions: D7
    # Evidence: EV1, EV6
    Given 记录 A 创建于北京时间2026-10-15 00:00，记录 B 创建于2026-10-16 00:00
    When 经 query_publish_records 触发 S3 P5 的同一业务事件
    Then UI 本地日历边界转UTC，后端created_at>=from且<to，字符串规范UTC RFC3339定宽，非法或反向区间拒绝
    And 验证 S3 P5 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S3 T6 成功作品链接证明
    # Proof: UI
    # Surface: PublishRecordsPage
    # Entry: open_external_link
    # Covers: S3 P6
    # Uses: DB1
    # Decisions: D7
    # Evidence: EV1, EV6
    Given tiktok_1 记录已确认成功，作品地址为 https://www.tiktok.com/@alice/video/101
    When 经 open_external_link 触发 S3 P6 的同一业务事件
    Then 复用外链命令并验证 https、精确TikTok host、/@handle/video/id 路径；首次实现检查现有外链白名单，按需只增加该路径类别
    And 验证 S3 P6 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S3 T7 失败原因与文案证明
    # Proof: UI
    # Surface: PublishRecordsPage
    # Entry: record detail drawer
    # Covers: S3 P7
    # Uses: DB1, Visual Contract VC1
    # Decisions: D4, D7
    # Evidence: EV1, EV6
    Given tiktok_2 发布失败，原文案为两行“海边日常\n#旅行”，原因是上传失败
    When 经 record detail drawer 触发 S3 P7 的同一业务事件
    Then 详情显示 batch不可变caption、原路径、provider、error_code/detail、evidence_json；文字转义，令牌凭据不落记录；截图不存在时提示不可用
    And 验证 S3 P7 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S3 T8 无记录证明
    # Proof: UI
    # Surface: PublishRecordsPage
    # Entry: query_publish_records
    # Covers: S3 P8
    # Uses: DB1, Visual Contract VC1
    # Decisions: D7
    # Evidence: EV1, EV6
    Given 本机尚无发布历史或当前筛选没有匹配记录
    When 经 query_publish_records 触发 S3 P8 的同一业务事件
    Then 数据库或表尚不存在时返回空页，不能因历史未迁移报整页错误；查询失败另显错误及重试，不伪装为空数据
    And 验证 S3 P8 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S3 T9 待确认重新核验证明
    # Proof: Acceptance
    # Surface: PublishRecordsPage / TikTok profile
    # Entry: recheck_tiktok_publish
    # Covers: S3 P9
    # Uses: SD1, DB1
    # Decisions: D4, D6, D7
    # Evidence: EV1, EV3, EV4
    Given tiktok_1 的 B1 记录为待确认，本次关联视频 V101 现在已出现在 @alice 主页
    When 经 recheck_tiktok_publish 触发 S3 P9 的同一业务事件
    Then 复用单运行锁、provider、auth与原handle/baseline证据，仅verify分支；无set_input_files/Description/Post；任务类型tiktok_publish_verify显式映射且本次人工启动沿用一次task quota
    And 验证 S3 P9 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S3 T10 重新核验仍不确定证明
    # Proof: Server
    # Surface: platforms/tiktok/publish.py
    # Entry: recheck_tiktok_publish
    # Covers: S3 P10
    # Uses: SD1, DB1
    # Decisions: D6, D7
    # Evidence: EV1, EV4
    Given tiktok_1 的 B1 记录待确认，主页仍只有旧视频 V100
    When 经 recheck_tiktok_publish 触发 S3 P10 的同一业务事件
    Then recheck限定pending_confirmation，无同次Post关联的精确ID或本人主页未找到该ID时保留待确认并更新最近证据；运行中及verified/failed/cancelled记录禁用recheck，后端同样拒绝
    And 验证 S3 P10 的可见结果及不变量，证据绑定同一批次和账号

  Scenario: S3 T11 隔天同文案不误确认证明
    # Proof: Server
    # Surface: publishing runtime
    # Entry: recheck_tiktok_publish
    # Covers: S3 P11
    # Uses: SD1, DB1
    # Decisions: D6
    # Evidence: EV1, EV4, EV7
    Given B1昨日提交后待确认且无关联ID，今日人工另发V202，文案同为“海边日常”
    When 经 recheck_tiktok_publish 触发 S3 P11 的同一业务事件
    Then 只允许同一次原Post明确关联post_id在本人主页出现才verified；无ID候选不能确认，原时间窗不扩展
    And 验证 S3 P11 的可见结果及不变量，证据绑定同一批次和账号

