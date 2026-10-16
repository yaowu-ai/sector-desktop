# 发布顺序修正（用户指令优先）

2026-10-16，用户通过实时页面明确要求：先点击左侧 Upload 发布作品，提交后才进入本人主页检查。此指令取代原设计 ED1 中“发布前采集本人作品基线”的前置要求。原设计与已编译义务保留，不修改其冻结哈希；引用旧基线要求的实施义务不应再作为当前行为依据，原全量 BUDGET_GUARD 状态不升级为 PASS。

## 证据和改动边界

- 当前 `publish.py::run_tiktok_publish` 原先在 `open_upload_page` 前调用 `profile_observation`，读取失败即记录 `baseline_unavailable`，所以不会点击 Upload。聚焦回归在修正前证明 Upload 调用数为 0、结果为 baseline_unavailable。
- 用户截图是空作品主页，显示 `Upload your first video`；代码原本已有该文案匹配，所以不能仅凭截图把事故根因归结为文案缺失。部署时页面何以未被识别仍未实证。本次直接消除不符合用户要求的前置作品列表依赖。
- 发布前只从登录页面导航 Profile 链接读取账号 handle，不进入个人主页、不读作品列表。随后在当前页面点击 Upload。
- Studio 提交前保留账号身份复核：在同一浏览器 context 的临时首页读取 cookie 对应的 Profile 导航 handle，不访问个人主页。发现变化仍禁止 Post；临时页结束关闭。
- Post 后沿用本人主页核验、原提交精确作品 ID、作者及文案检查；无原提交 ID 仍待确认，不以最新作品或相同文案冒充成功。
- 新任务不保存发布前作品基线，`baseline_json` 保持 NULL；兼容已有记录的基线与重新核验，SQLite 不变。

## 聚焦验证

`python -m unittest discover -s src -p test_publish_unit.py -q`

修正前新增测试出现 1 failure / 1 error：Upload 未调用、身份检查仍进入主页。修正后 20 tests passed。

覆盖：首次发帖不调用发布前作品观察；Upload→上传→Description→单次 Post→本人主页核验的顺序；提交前身份复核不访问本人主页；账号变化拒绝；空作品状态；既有取消、响应关联、待确认和 verify-only 安全测试。

此测试仅证明本地流程与状态转换，不证明真实 TikTok DOM、接口返回、三浏览器实发或安装包。用户继续负责最终打包与实机测试；安装版需要重新打包内置 Python runtime 才能携带本次修改，单更新前端资源不足以更新 runtime exe。
