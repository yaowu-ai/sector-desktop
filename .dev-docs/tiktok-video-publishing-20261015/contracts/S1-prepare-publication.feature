Feature: S1 准备视频发布任务
  # Actor: 已登录的桌面端运营用户
  # Source: 本聊天中已确认需求，design.md 的 Product Examples

  Rule: R1 entry 菜单分组

    Scenario: P1 一级菜单展开
      Given 运营当前位于首页，平台为 TikTok
      When 展开一级菜单“发布作品”
      Then 看到“发布作品”和“发布记录”两个子菜单
      And 没有第三个同名一级入口

  Rule: R2 entry 发布表单

    Scenario: P2 发布页入口
      Given 运营当前处于 TikTok 平台
      When 进入二级菜单“发布作品”
      Then 看到本地视频选择、可编辑文案和执行账号选择
      And 原有养号入口仍可访问

  Rule: R3 state 视频来源

    Scenario: P3 选择本地路径
      Given 运营发布表单尚未选择视频，文案为“海边日常”
      When 选择本地文件 D:\Videos\海边.mp4
      Then 表单显示该视频的绝对路径、文件名和大小
      And 文案仍为“海边日常”，不要求复制视频到应用素材库

  Rule: R4 state 文案输入

    Scenario: P4 直接输入文案
      Given 运营文案输入框原值为空，已选择海边.mp4
      When 输入两行文案“海边日常\n#旅行”
      Then 输入框完整显示两行文字
      And 所选视频保持不变

  Rule: R5 state 文案导入

    Scenario: P5 TXT文案导入
      Given 运营已选择海边.mp4，文案为空，caption.txt 为 UTF-8 含两行“海边日常\n#旅行”
      When 导入 caption.txt
      Then 同一文案输入框显示“海边日常\n#旅行”
      And 视频保持不变，文字仍可编辑

  Rule: R6 state Word正文

    Scenario: P6 Word文案导入
      Given 运营文案为空，caption.docx 正文含“海边”、一个空段和“#旅行”
      When 导入 caption.docx
      Then 文案框显示“海边\n\n#旅行”
      And 不包含图片、页眉页脚或 Word 格式代码

  Rule: R7 rejection 取消覆盖

    Scenario: P7 覆盖确认
      Given 运营文案原值为“人工修改稿”，新 caption.txt 内容为“文件稿”
      When 取消导入覆盖确认
      Then 输入框仍为“人工修改稿”
      And 新文件内容未覆盖原文

  Rule: R8 rejection 格式错误

    Scenario: P8 无效文案文件
      Given 运营文案为“人工修改稿”，选择旧版 caption.doc
      When 尝试导入该文件
      Then 看到“请另存为 .docx 或 UTF-8 .txt”的提示
      And 原文案保持不变

  Rule: R9 state 单账号范围

    Scenario: P9 单账号
      Given 运营已选海边.mp4及文案“海边日常”，tiktok_1 和 tiktok_2 均已启用
      When 以单账号方式为 tiktok_1 启动发布
      Then 任务账号列表仅含 tiktok_1
      And tiktok_2 不产生本次发布记录

  Rule: R10 state 多账号范围

    Scenario: P10 多账号
      Given 运营已选同一视频和文案，tiktok_1、tiktok_2、tiktok_3 均已启用
      When 为选中的 tiktok_1 和 tiktok_3 启动发布
      Then 任务仅按选定顺序包含 tiktok_1 和 tiktok_3
      And 两账号共用同一视频路径和文案，tiktok_2 不参与

  Rule: R11 state 全部启用TikTok

    Scenario: P11 全部账号
      Given 运营有启用的 tiktok_1、tiktok_2，停用的 tiktok_3 及启用的 instagram_1
      When 选择全部账号启动发布
      Then 本次任务包含 tiktok_1 和 tiktok_2
      And 不包含 tiktok_3 和 instagram_1

  Rule: R12 state 内容快照

    Scenario: P12 启动后固定内容
      Given 批次 B1 已用海边.mp4及文案“海边日常”为 tiktok_1、tiktok_2 启动，tiktok_2 尚未开始
      When 运营将表单文案改为“明天发布”
      Then B1 中 tiktok_2 的待发文案仍为“海边日常”
      And 表单新文案只影响下次任务

  Rule: R13 rejection 无效素材

    Scenario: P13 失效视频
      Given 运营已选 D:\Videos\海边.mp4，但该文件在开始前被删除
      When 启动发布
      Then 看到视频不存在的错误
      And 不打开浏览器且不创建可执行批次

  Rule: R14 rejection 无目标账号

    Scenario: P14 无可用账号
      Given 运营账号列表中没有已启用 TikTok 账号，视频路径有效
      When 选择全部账号启动发布
      Then 看到“没有可执行的启用账号”
      And 不打开浏览器、不占用每日任务额度

  Rule: R15 rejection 运行受限

    Scenario: P15 互斥与授权
      Given 运营的养号任务仍在执行，发布表单视频及文案有效
      When 启动视频发布
      Then 看到“已有任务正在执行”
      And 原养号任务保持运行，本次不打开新浏览器

  Rule: R16 state 替换文案

    Scenario: P16 确认覆盖文案
      Given 运营文案原值为“人工修改稿”，新 caption.txt 内容为“文件稿”
      When 确认导入文件替换原文案
      Then 文案框从“人工修改稿”变为“文件稿”
      And 视频选择保持不变，仍可继续编辑文件稿

  Rule: R17 rejection 文案长度

    Scenario: P17 文案过长
      Given 运营已选择有效视频，输入框文案长度超过页面显示的4000上限
      When 启动发布
      Then 看到文案超长提示
      And 不截断文案、不打开浏览器

  Rule: R18 rejection 平台边界

    Scenario: P18 非TikTok入口拒绝
      Given 技术员当前选择 Instagram 平台
      When 尝试打开发布作品页面
      Then 看到当前平台不支持视频发布的说明
      And 不能启动 TikTok 或 Instagram 发布任务

  Rule: R19 state 启动重放

    Scenario: P19 重复启动同一请求
      Given 已接受B1使用海边.mp4、文案“海边日常”
      When 运营以相同请求重试B1
      Then 返回B1原进度
      And 不重建批次、不重复发布、已接受B1不重复扣额

  Rule: R20 rejection 不可变请求

    Scenario: P20 冲突启动请求
      Given B1原文案为“海边日常”
      When 运营以相同请求B1提交“城市夜景”
      Then 提示请求内容与原任务不一致
      And B1原文案仍为“海边日常”，不重复扣额

  Rule: R21 rejection 额度不确定

    Scenario: P21 额度结果不明
      Given 视频与账号有效，但额度请求网络超时，任务尚未接受
      When 运营收到本次启动结果
      Then 提示额度结果无法确认、任务未启动
      And 不自动重试额度、不打开浏览器，不声称额度未扣

  Rule: R22 rejection 导入环境

    Scenario: P22 DOCX环境不可用
      Given 原文案为“人工稿”，当前WebView无法解压DOCX
      When 运营导入caption.docx
      Then 提示更新WebView2或另存TXT
      And 原文案仍为“人工稿”，直接输入和TXT仍可使用

  Rule: R23 rejection 导入文案超限

    Scenario: P23 超长文件保留原文
      Given caption.txt有4001个英文字符，输入框原值为空
      When 运营导入caption.txt
      Then 完整显示4001字符并提示上限4000，开始发布禁用
      And 不截断文案、不打开浏览器

