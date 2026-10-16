Feature: S3 查询逐账号发布记录
  # Actor: 已登录的桌面端运营用户
  # Source: 本聊天中已确认需求，design.md 的 Product Examples

  Rule: R1 entry 发布历史

    Scenario: P1 记录入口
      Given 运营当前位于发布作品表单
      When 进入二级菜单“发布记录”
      Then 看到逐账号发布记录列表
      And 原有通用执行记录菜单仍存在

  Rule: R2 display 逐账号结果

    Scenario: P2 批量独立记录
      Given B1 的 tiktok_1 已确认成功，tiktok_2 上传失败，两者视频均为海边.mp4
      When 查看发布记录
      Then 分别看到两行对应账号、视频文件名、提交时间和各自结果
      And 不能只显示一条“批次完成”代替两个账号的事实

  Rule: R3 display 账号条件

    Scenario: P3 账号筛选
      Given 历史中包含 tiktok_1 成功记录和 tiktok_2 失败记录
      When 按账号 tiktok_1 筛选
      Then 列表仅显示 tiktok_1 的记录
      And 其他账号记录仍保留且不显示在本次结果中

  Rule: R4 display 状态条件

    Scenario: P4 状态筛选
      Given 历史中有已确认成功、待确认和发布失败三类记录
      When 筛选“待确认”
      Then 列表仅显示待确认记录
      And 成功和失败记录不混入本次列表

  Rule: R5 display 时间范围

    Scenario: P5 时间筛选
      Given 记录 A 创建于北京时间2026-10-15 00:00，记录 B 创建于2026-10-16 00:00
      When 筛选2026-10-15当天
      Then 列表包含 A，不包含 B
      And 记录本身的时间保持不变

  Rule: R6 entry 作品链接

    Scenario: P6 成功作品链接
      Given tiktok_1 记录已确认成功，作品地址为 https://www.tiktok.com/@alice/video/101
      When 打开记录中的作品链接
      Then 浏览器打开该条记录的 TikTok 作品
      And 不打开其他账号作品或任意非TikTok地址

  Rule: R7 display 记录详情

    Scenario: P7 失败原因与文案
      Given tiktok_2 发布失败，原文案为两行“海边日常\n#旅行”，原因是上传失败
      When 查看该记录详情
      Then 看到完整文案、原视频路径、执行阶段和“视频上传失败”原因
      And 没有伪造作品链接，长文案不挤坏列表

  Rule: R8 empty 初始历史

    Scenario: P8 无记录
      Given 本机尚无发布历史或当前筛选没有匹配记录
      When 进入发布记录页面
      Then 看到“暂无发布记录”或“没有符合条件的发布记录”
      And 页面可用，允许返回发布页或清空筛选

  Rule: R9 state 重新核验成功

    Scenario: P9 待确认重新核验
      Given tiktok_1 的 B1 记录为待确认，本次关联视频 V101 现在已出现在 @alice 主页
      When 运营对该记录执行“重新核验”
      Then 原记录从“待确认”变为“已确认成功”，链接为 V101
      And 原视频和文案快照保持不变，没有重新上传或再次发布

  Rule: R10 state 保留待确认

    Scenario: P10 重新核验仍不确定
      Given tiktok_1 的 B1 记录待确认，主页仍只有旧视频 V100
      When 运营对该记录执行“重新核验”
      Then 记录仍为“待确认”，展示本次核验未找到匹配作品
      And 不自动重发，也不新增一条发布尝试

  Rule: R11 rejection 非本次作品

    Scenario: P11 隔天同文案不误确认
      Given B1昨日提交后待确认且无关联ID，今日人工另发V202，文案同为“海边日常”
      When 运营对B1重新核验
      Then B1仍为待确认
      And 不把V202记作B1成功链接、不再次发布

