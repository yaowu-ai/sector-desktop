# Account Matrix 存储与调度页性能根因诊断

## Machine Handoff

```json
{
  "schema_version": 1,
  "kind": "root-cause-report",
  "producer": "root-cause-analysis",
  "report_id": "account-matrix-storage-scheduler-20261113-223107",
  "created_at": "2026-11-13T22:31:07+08:00",
  "status": "PARTIAL_EVIDENCE",
  "source_context": {
    "analysis_class": "non-trivial",
    "trivial_basis": null,
    "investigation_boundary": "静态检查 account-matrix 桌面端、Python scheduler、浏览器 provider、SQLite 读写链路，以及 h-sector 桌面端任务额度接口；未连接用户实际运行中的 APPDATA 数据目录、进程和生产数据库。",
    "repository_root": "E:/YAOWU/yangHao/account-matrix",
    "code_revision": "account-matrix=8db291a24c6f4c76e1af2224117949381a9c1da6; h-sector=ed64c8af617a77a896c76bacda4dc0c810e8f154",
    "providers_used": ["repository-source", "repository-config", "user-reported-symptom"]
  },
  "failure_object": {
    "trigger_input": "在 account-matrix 中启用调度并持续运行 TikTok 养号任务，随后打开或停留在调度计划页。",
    "state_environment": "Windows 桌面端；多个账号；scheduler.py 以本地时间触发；浏览器 provider 可能为 builtin_chromium、BitBrowser 或 ixBrowser；运行数据与日志位于配置的数据目录及 APPDATA 本地目录。",
    "failing_signal": "用户报告运行一段时间后本机磁盘容易爆满，调度计划页加载慢且交互卡顿。",
    "expected_behavior": {
      "statement": "任务运行产生的本地浏览器缓存、日志、运行历史和诊断产物应有可预期的容量上限或保留策略；调度计划页应以有界数据和低频/去重状态刷新，保持可交互。",
      "authority_evidence_ids": ["EV-USER-001"]
    },
    "actual_behavior": "代码存在长期保留的浏览器 user-data、追加式 scheduler/session 日志、持续增长的 SQLite 明细表和配置/数据库备份；调度页及 AppShell 对状态和浏览器接口重复轮询，历史查询按 COALESCE 时间表达式排序且没有对应索引。",
    "affected_boundary": "account-matrix desktop frontend -> Tauri commands -> Python scheduler/runtime -> local browser profiles/SQLite/log files; h-sector only participates in per-fire quota reservation.",
    "nearby_objects_not_accepted": ["浏览器 profile、Cookies、Local Storage、登录态和浏览器缓存清理不属于本次优化边界", "h-sector 的服务端日志不是 account-matrix 本机磁盘爆满的直接证据", "当前工作区 account-matrix/data/actions.db 是旧测试/开发数据库，不能代表用户运行时数据库容量"]
  },
  "evidence": [
    {
      "id": "EV-USER-001",
      "kind": "user-authority",
      "provider": "user-reported-symptom",
      "observation": "用户明确报告长期养号后磁盘爆满、调度计划页面卡顿和加载慢。",
      "source_anchor": "conversation:2026-11-13",
      "proves": "failure_object 的外部症状和影响边界。",
      "does_not_prove": "不能单独证明某一个文件或查询是第一错误步骤。"
    },
    {
      "id": "EV-001",
      "kind": "repository-source",
      "provider": "account-matrix",
      "observation": "builtin_chromium 启动时按账号创建持久 user-data-dir；正常 close_session 只终止匹配进程并清理 runtime.json，未删除 user-data-dir。单独的 cleanup_builtin_chromium_data 命令才执行 remove_dir_all。",
      "source_anchor": "src/browser_providers.py#423-486, #692-699, #1108-1161 (sha256=2ED730432CAFDD8954CCCD3D0C8CC6898EE1458F2D89C208A1E7BFEC4729DC08); desktop/src-tauri/src/commands/bitbrowser.rs#553-594 (sha256=84A71E992A06273EB4286A8EFDB5B4C18D86CF73F0338EC18D37C4D9240B4135)",
      "proves": "内置 Chromium 的缓存、History、Network、GPU 等持久浏览器数据会跨任务保留；删除数据是人工/显式命令路径。",
      "does_not_prove": "没有用户实际 APPDATA 目录的容量采样；且按用户约束，本次不把浏览器 profile、登录态或缓存清理纳入修复边界。"
    },
    {
      "id": "EV-002",
      "kind": "repository-source",
      "provider": "account-matrix",
      "observation": "session_log 以 append 模式写 sessions.log；scheduler 启动时以 append 模式打开 logs/scheduler.log，Python logging.basicConfig 输出到 stderr，stdout/stderr 均重定向到该文件；未发现本地轮转、大小上限或按日期清理。",
      "source_anchor": "src/core/runtime.py#927-932 (sha256=E36B4C51DE451A5D1DD474BB374178CAF1B536DF8F3C5DAFE438B9BF4C59CA16); src/scheduler.py#100-104 (sha256=29BDB922C62756A91D20AC4A2E3718C2B4777A8860C23ED6E41D289CCC2A0E6E); desktop/src-tauri/src/commands/scheduler.rs#187-232 (sha256=8BB3CBB1A91741030968B30DEB9BEB41F83E528502E2B9995708D5F11A16D3BA)",
      "proves": "本地 session/scheduler 日志是无界追加文件；长时间运行会单调增长。",
      "does_not_prove": "未测量实际日志行大小；按用户补充约束，文本日志不作为本次磁盘问题的修复对象。"
    },
    {
      "id": "EV-003",
      "kind": "repository-source",
      "provider": "account-matrix",
      "observation": "SQLite 建表包含 action_log、scheduler_job_runs、fyp_video_views、profile_stats_snapshots、ins_warm_log 等明细表；运行代码持续 INSERT/UPDATE 并 commit，没有 DELETE、TTL、归档或 VACUUM 策略。scheduler_job_runs 只有主键 job_id，未建立按平台/账号/时间的查询索引。",
      "source_anchor": "src/core/runtime.py#138-258, #314-377, #428-643, #821-843 (sha256=E36B4C51DE451A5D1DD474BB374178CAF1B536DF8F3C5DAFE438B9BF4C59CA16); desktop/src-tauri/src/commands/stats.rs#743-807 (sha256=A90880E1295297106C46EBCE7B069DCCA80F5D899B1718B8C6C83340B65DD3EC)",
      "proves": "运行历史和明细表容量随任务/视频/动作数增长，且调度历史查询缺少专用索引。",
      "does_not_prove": "不能从当前工作区旧数据库推断用户生产数据的行数。"
    },
    {
      "id": "EV-004",
      "kind": "repository-source",
      "provider": "account-matrix",
      "observation": "TikTok FYP 默认 2-5 分钟；video_capture 配置未提供时 normalize_video_capture_config 默认 enabled=true；fyp_browse 每个视频调用 record_fyp_video_view，动作发生后还可能再次 update_fyp_video_interactions。",
      "source_anchor": "desktop/src-tauri/resources/templates/config/accounts.yaml#18-26 (sha256=611370DECE9CDC3059C3D9BBE8A5E4318EFD5C2A2D4A14379A080B3F93E8A977); src/platforms/tiktok/fyp.py#9-52 (sha256=D70B39D48B0D45D0C62E954A77ABC24284F147F1E3A92BD46EFB7C1EE7965DBA); src/platforms/tiktok/actions.py#284-444 (sha256=FE2BED49B12EFA831DA9ADE05CC35534EFB3901A5F3F4171D9F334A271E6EA3D)",
      "proves": "每次养号会产生按视频粒度的 SQLite 明细；账号数、每日触发次数和浏览时长共同放大增长速率。",
      "does_not_prove": "未在真实浏览器测量每次任务的视频数量或每行字节数。"
    },
    {
      "id": "EV-005",
      "kind": "repository-source",
      "provider": "account-matrix",
      "observation": "SchedulerPage refresh 每次并行执行 loadConfig、scheduler process status、scheduler health、BitBrowser 探测、ixBrowser 探测和 querySchedulerJobRuns；页面挂载后每 10 秒重复 refresh。两个浏览器探测即使当前没有该 provider 的调度账号也会执行。",
      "source_anchor": "desktop/src/platforms/tiktok/pages/SchedulerPage.tsx#201-266 (sha256=40D2CF7365F29B488C335DF9F2C808E82AF78C0E2BE7E6A3D139421CD2C9F3D4)",
      "proves": "页面刷新路径包含 6 个独立调用和固定 10 秒周期，存在不必要探测与并发刷新风险。",
      "does_not_prove": "没有浏览器性能 trace，不能量化每个调用对首屏时间的具体贡献。"
    },
    {
      "id": "EV-006",
      "kind": "repository-source",
      "provider": "account-matrix",
      "observation": "AppShell 在所有页面全局每 10 秒并行 checkBitbrowserApi/checkIxbrowserApi，并每 1.5 秒轮询 getCurrentRunStatus；SchedulerPage 自己又每 10 秒执行相同两个浏览器探测。",
      "source_anchor": "desktop/src/components/AppShell.tsx#133-141, #192-211, #275-287 (sha256=65B2B9C7BC84ECD6038388163E9535D5DD9F810BCB1136FDBD955C310FFA2D5F)",
      "proves": "调度页存在页面级和全局级重复轮询，Tauri 命令线程会承受重复探测。",
      "does_not_prove": "不能单凭代码判断 Tauri 主线程是否已经成为实际瓶颈。"
    },
    {
      "id": "EV-007",
      "kind": "repository-source",
      "provider": "account-matrix",
      "observation": "get_scheduler_health 先调用 get_scheduler_process_status（运行时会读一次 /health），随后又读一次 /health；同时每次健康查询读取配置、任务锁并对所有启用且参与调度账号做 O(n²) 两两 IP 分组/时段冲突检查。",
      "source_anchor": "desktop/src-tauri/src/commands/scheduler.rs#413-514, #759-795, #874-914 (sha256=8BB3CBB1A91741030968B30DEB9BEB41F83E528502E2B9995708D5F11A16D3BA)",
      "proves": "一次页面刷新中的 scheduler health 不是单次轻量读取；账号规模增大时冲突检查复杂度为 O(n²)。",
      "does_not_prove": "未测量当前账号数量和 /health 实际响应延迟。"
    },
    {
      "id": "EV-008",
      "kind": "repository-source",
      "provider": "account-matrix",
      "observation": "query_scheduler_job_runs 使用 COALESCE(started_at, scheduled_run, created_at) 作为过滤和排序表达式，按该表达式 DESC 排序后 LIMIT；表结构只为 job_id 建主键，没有覆盖 platform/account/time 的复合索引。默认 normalized_limit 为 300，页面传 120。",
      "source_anchor": "desktop/src-tauri/src/commands/stats.rs#743-807, #1733-1735 (sha256=A90880E1295297106C46EBCE7B069DCCA80F5D899B1718B8C6C83340B65DD3EC); src/core/runtime.py#168-179 (sha256=E36B4C51DE451A5D1DD474BB374178CAF1B536DF8F3C5DAFE438B9BF4C59CA16)",
      "proves": "历史增长后该查询需要扫描/排序更多行，且无法直接利用时间索引。",
      "does_not_prove": "没有运行 EXPLAIN ANALYZE 或用户库的真实行数/耗时。"
    },
    {
      "id": "EV-009",
      "kind": "repository-source",
      "provider": "account-matrix",
      "observation": "Python init_db 每次连接都会执行 initialize_db_schema；其中 ensure_platform_column 对旧表执行全表条件 UPDATE。Tauri 查询端直接 Connection::open actions.db，没有 WAL、busy_timeout 或只读连接配置。",
      "source_anchor": "src/core/runtime.py#138-141, #254-307 (sha256=E36B4C51DE451A5D1DD474BB374178CAF1B536DF8F3C5DAFE438B9BF4C59CA16); desktop/src-tauri/src/commands/stats.rs#1386-1395 (sha256=A90880E1295297106C46EBCE7B069DCCA80F5D899B1718B8C6C83340B65DD3EC)",
      "proves": "任务写入和页面读取共享同一 SQLite 文件，连接初始化有额外扫描/写入，存在锁竞争和 IO 放大路径。",
      "does_not_prove": "不能证明每次卡顿都由 SQLite lock 等待触发。"
    },
    {
      "id": "EV-010",
      "kind": "repository-source",
      "provider": "account-matrix",
      "observation": "tail_session_log 每次都 fs::read 整个 sessions.log 后再从 offset 切片；SessionLogPage 每 3 秒增量轮询，并在前端反复 split、过滤、解析全部保留的 12000 字符窗口。",
      "source_anchor": "desktop/src-tauri/src/commands/logs.rs#30-53 (sha256=C326AEF8ECC349CB70900A708B730D1DB95F527024006FAA5C06A80A8AD44DD0); desktop/src/platforms/tiktok/pages/SessionLogPage.tsx#111-119, #174-183, #406-423 (sha256=552B7E92661866E48DFE68A03D9C11331E050914B276EA92BC07C3161759DFCD)",
      "proves": "日志文件变大后读取成本随文件长度增长；这是 Session 日志页的直接性能风险。",
      "does_not_prove": "SessionLogPage 不在 SchedulerPage 的直接 JSX 树中，不能把该风险直接等同于调度页卡顿。"
    },
    {
      "id": "EV-011",
      "kind": "repository-source",
      "provider": "cross-repository account-matrix+h-sector",
      "observation": "scheduler.py 每个账号 fire 都向 h-sector /api/desktop/usage/reserve-task 发起一次额度请求；h-sector 每次请求校验订阅、套餐、设备和 License，再执行 usage_daily 事务更新。",
      "source_anchor": "account-matrix/src/scheduler.py#211-256 (sha256=29BDB922C62756A91D20AC4A2E3718C2B4777A8860C23ED6E41D289CCC2A0E6E); h-sector/src/pages/api/desktop/usage/reserve-task.ts#15-20 (sha256=703687390D512D3D2A93BEC832A9CFA5FADD8510216EA50386A1C23EA1DA3584); h-sector/backend/services/usage/usage.facade.ts#45-113 (sha256=76D21AB29737E22F394F4A1DC9FC5E6D304712BE45B64DE70AC4B6BACD3B3B7D); h-sector/backend/services/usage/usage.service.ts#134-227 (sha256=7F3CF30C697EB770F926635150F4EBFC9B75C0DAB872F3B9D8375D78B6F59B86)",
      "proves": "远端配额链路会增加每次账号任务的网络/数据库延迟和服务端负载。",
      "does_not_prove": "SchedulerPage 本身没有调用该 h-sector API；它不是调度页首屏慢的直接调用链。"
    },
    {
      "id": "EV-012",
      "kind": "repository-config",
      "provider": "h-sector",
      "observation": "h-sector 的测试/生产环境明确配置 daily + 100m + 30 的滚动日志，logger 将 roll 目标加入 multistream。",
      "source_anchor": "h-sector/.env.test#11-16 (sha256=50B6474E5060297E93DEC890A19132D977680EF0F0BD02A4A77CA033167212C7); h-sector/backend/lib/logger/config.ts#48-76 (sha256=FF6415473E2D71C9BE77687C21D4B1D2C5FE0220D19042EDDAC967BDC7E907F8)",
      "proves": "h-sector 服务端已有日志轮转边界；本次本机磁盘问题应优先处理 account-matrix 的本地存储链路。",
      "does_not_prove": "不能证明部署环境实际加载了这些 env 值。"
    },
    {
      "id": "EV-013",
      "kind": "repository-source",
      "provider": "account-matrix",
      "observation": "bundled 模式把 data 放到用户本地 data 目录、logs 放到用户本地 logs 目录；builtin_chromium 默认再把 profile 放到 data/browser/builtin_chromium/<account>/user-data。",
      "source_anchor": "desktop/src-tauri/src/paths.rs#573-587, #214-254 (sha256=175948210DE36E9030DF276DA91510BCBBFD49B4162C91060D79A5B77C92CE84); src/browser_providers.py#683-699 (sha256=2ED730432CAFDD8954CCCD3D0C8CC6898EE1458F2D89C208A1E7BFEC4729DC08)",
      "proves": "这些增长点位于用户本机应用数据盘，能够直接消耗系统磁盘。",
      "does_not_prove": "实际路径可能被 local-settings.json 的 data_dir/user_data_dir 覆盖。"
    },
    {
      "id": "EV-014",
      "kind": "repository-source",
      "provider": "account-matrix",
      "observation": "配置保存和 SQLite 迁移会按时间戳复制 accounts.yaml/actions.db 到 backups 目录，但没有保留数量或年龄清理。",
      "source_anchor": "desktop/src-tauri/src/commands/config.rs#1569-1607, #2518-2545 (sha256=46CD22040199F042C0926E99A8B91D31AC536E6EE9641F01B290324086D3795D)",
      "proves": "频繁保存配置或迁移时，备份也会长期累积并复制整个 actions.db。",
      "does_not_prove": "该路径不是每次养号任务都会执行，不能作为长期养号磁盘增长的主因。"
    }
  ],
  "claims": [
    {
      "id": "CL-001",
      "status": "observed",
      "claim": "内置 Chromium 的 user-data 目录在正常任务结束后不会被自动清理。",
      "evidence_ids": ["EV-001", "EV-013"],
      "does_not_prove": "用户是否使用 builtin_chromium，以及该目录实际占用多少空间。",
      "consumers": ["out-of-scope-browser-layer"]
    },
    {
      "id": "CL-002",
      "status": "observed",
      "claim": "account-matrix SQLite 运行明细表缺少保留边界；文本日志不纳入本次磁盘优化。",
      "evidence_ids": ["EV-003", "EV-004"],
      "does_not_prove": "SQLite 各表在用户环境中的实际占用比例。",
      "consumers": ["sqlite-storage-optimization"]
    },
    {
      "id": "CL-003",
      "status": "observed",
      "claim": "SchedulerPage 自身每 10 秒并行触发六类读取/探测，AppShell 又重复探测两个浏览器接口。",
      "evidence_ids": ["EV-005", "EV-006"],
      "does_not_prove": "真实设备上首屏慢的精确时间占比。",
      "consumers": ["scheduler-page-optimization"]
    },
    {
      "id": "CL-004",
      "status": "observed",
      "claim": "调度运行历史查询按 COALESCE 时间表达式过滤/排序，且 scheduler_job_runs 没有时间/平台/账号索引；数据增长后查询成本会随历史量增大。",
      "evidence_ids": ["EV-003", "EV-008"],
      "does_not_prove": "实际查询计划和耗时，需在用户数据库上 EXPLAIN/采样。",
      "consumers": ["scheduler-page-optimization", "sqlite-migration"]
    },
    {
      "id": "CL-005",
      "status": "observed",
      "claim": "h-sector 的额度接口属于每个调度 fire 的后台执行链路，不属于 SchedulerPage 的直接加载链路。",
      "evidence_ids": ["EV-005", "EV-011"],
      "does_not_prove": "远端额度接口不会拖慢任务完成或造成 scheduler fire 排队。",
      "consumers": ["cross-system-optimization"]
    }
  ],
  "hypotheses": [
    {
      "id": "H-001",
      "status": "blocked",
      "hypothesis": "浏览器 profile/cache 是磁盘增长的最大单项来源。",
      "evidence_for": ["EV-001", "EV-013"],
      "evidence_against": [],
      "challenge": "用户已明确将浏览器 profile、登录态和缓存排除在本次优化边界之外；不进入本次修复决策。"
    },
    {
      "id": "H-002",
      "status": "open",
      "hypothesis": "按视频 FYP 明细、profile snapshot、action_log、scheduler_job_runs 和 ins_warm_log 的累计增长造成长期磁盘耗尽。",
      "evidence_for": ["EV-003", "EV-004"],
      "evidence_against": [],
      "challenge": "对 actions.db 做只读检查，按表统计 COUNT(*)、page_count、freelist_count、最早/最新时间和最大 detail/result_json 长度。"
    },
    {
      "id": "H-003",
      "status": "open",
      "hypothesis": "调度页卡顿首先来自重复探测、健康查询重复读 /health 和周期刷新重叠，而非 React 表格本身。",
      "evidence_for": ["EV-005", "EV-006", "EV-007"],
      "evidence_against": [],
      "challenge": "在 Tauri invoke、Rust command、TcpStream、SQLite query 周围加入耗时采样，记录单次刷新分项耗时和 in-flight 数。"
    },
    {
      "id": "H-004",
      "status": "open",
      "hypothesis": "历史表增长、COALESCE 排序和 scheduler 写入/页面读取共享 SQLite 造成额外扫描及锁等待，放大调度页加载慢。",
      "evidence_for": ["EV-008", "EV-009"],
      "evidence_against": [],
      "challenge": "在用户数据库执行 EXPLAIN QUERY PLAN，并同时采集 sqlite busy/locked 次数、查询耗时及 scheduler commit 时间。"
    },
    {
      "id": "H-005",
      "status": "ruled-out",
      "hypothesis": "h-sector 的 /api/desktop/usage/reserve-task 是 SchedulerPage 首屏慢的直接调用。",
      "evidence_for": [],
      "evidence_against": ["EV-005", "EV-011"],
      "challenge": "若在前端/网络 trace 中发现 SchedulerPage 直接请求该接口，则重新打开该结论；当前代码调用链不支持该假设。"
    }
  ],
  "causal_chain": {
    "first_wrong_step": null,
    "first_wrong_step_edge_id": null,
    "edges": [
      {
        "id": "EDGE-STORAGE-01",
        "from": "每次任务启动内置浏览器并进行 FYP 浏览",
        "to": "账号级 user-data 和按视频明细持续写入本地",
        "evidence_ids": ["EV-001", "EV-003", "EV-004"],
        "same_chain": true
      },
      {
        "id": "EDGE-STORAGE-02",
        "from": "任务/调度器持续写入运行明细",
        "to": "SQLite 和备份目录单调增长",
        "evidence_ids": ["EV-003", "EV-014"],
        "same_chain": true
      },
      {
        "id": "EDGE-PERF-01",
        "from": "SchedulerPage/AppShell 周期性刷新",
        "to": "重复浏览器探测、健康接口读取和配置/冲突计算",
        "evidence_ids": ["EV-005", "EV-006", "EV-007"],
        "same_chain": true
      },
      {
        "id": "EDGE-PERF-02",
        "from": "调度运行历史数据增长",
        "to": "COALESCE 时间表达式扫描/排序及 SQLite 读写竞争",
        "evidence_ids": ["EV-008", "EV-009"],
        "same_chain": true
      }
    ]
  },
  "contradictions": [
    {
      "id": "CON-001",
      "statement": "当前工作区 account-matrix/data/actions.db 只有旧 action_log 表，不能代表最新运行时 schema。",
      "evidence_ids": ["EV-003"],
      "resolution": "将该文件视为开发/测试遗留，不作为用户容量结论；需要用户实际 APPDATA 数据目录快照。"
    }
  ],
  "open_unknowns": [
    {
      "id": "U-001",
      "question": "用户实际使用的 browser provider、data_dir、user_data_dir 和各目录容量是多少？",
      "impact": "may-change-root-cause",
      "owner": "user/runtime-observation",
      "next_step": "在出现磁盘告警的机器上按目录采集 APPDATA data/logs、builtin_chromium、actions.db、scheduler.log、sessions.log、publish-evidence 的大小。"
    },
    {
      "id": "U-002",
      "question": "SchedulerPage 首次加载和周期刷新各 Tauri invoke 的实际耗时、是否存在重叠请求？",
      "impact": "may-change-root-cause",
      "owner": "repository runtime instrumentation",
      "next_step": "对 refresh 请求加 request id/in-flight guard 和分项耗时日志，抓取 1-3 分钟 trace。"
    },
    {
      "id": "U-003",
      "question": "用户运行时 SQLite 的各表行数、索引、page_count、WAL/journal 状态和 busy/locked 次数是多少？",
      "impact": "may-change-root-cause",
      "owner": "repository runtime observation",
      "next_step": "在停止写入或只读副本上执行 bounded SQLite inspection 与 EXPLAIN QUERY PLAN。"
    },
    {
      "id": "U-004",
      "question": "产品希望保留多少天的任务明细、视频明细、profile snapshot 和日志？",
      "impact": "may-change-repair-boundary",
      "owner": "user/product authority",
      "next_step": "确定 retention_days、最大日志文件数/大小、是否允许仅保留聚合统计。"
    }
  ],
  "repair_handoff": {
    "readiness": "BLOCKED",
    "consumer": "$code-bugfix",
    "root_cause_claim_id": null,
    "repair_boundary": null,
    "regression_observable": null,
    "constraints": ["本次只完成诊断，不修改生产代码或数据。", "任何清理策略都必须避开仍在运行的浏览器 profile、当前任务日志和待确认发布证据。"],
    "risk_decisions": ["SQLite 删除/归档必须先定义产品保留周期并提供备份/恢复路径。", "h-sector 配额校验不能直接改成无验证的长期缓存；若做缓存需有明确失效和撤销策略。"]
  }
}
```

## Diagnosis Summary

按用户补充约束，本次不分析浏览器 profile、登录态、Cookies、Local Storage 或浏览器缓存清理。剩余证据仍支持两条并行的高概率路径，但尚不足以把某一项锁定为唯一第一错误步骤，因此终态为 `PARTIAL_EVIDENCE`。

磁盘方面，在排除浏览器层和文本日志后，核心风险集中在 SQLite：它会记录每个调度 fire、每个动作、每个 FYP 视频和每次 profile snapshot；配置/数据库备份也没有保留清理。默认每次 FYP 养号都会采集视频明细，账号数和每日触发次数会线性放大数据库增长。

调度计划页方面，首屏和每 10 秒刷新同时请求配置、进程状态、健康状态、两个浏览器接口和历史记录；AppShell 又全局重复探测两个浏览器接口。Rust 健康命令内部还会重复读取 scheduler `/health`，并对启用账号做 O(n²) 的 IP/班次冲突检查。运行历史 SQL 使用 `COALESCE` 表达式做时间过滤和排序，`scheduler_job_runs` 没有匹配索引；Python 写入和 Tauri 读取共享同一 SQLite 文件，也没有 WAL/busy-timeout 设计。这些路径会在历史增长和任务持续写入时叠加放大。

## Source Context

本次静态检查覆盖 account-matrix commit `8db291a24c6f4c76e1af2224117949381a9c1da6` 与 h-sector commit `ed64c8af617a77a896c76bacda4dc0c810e8f154`。浏览器 profile、登录态和缓存不在本次分析与修复边界内。未读取任何用户本地 APPDATA、未连接生产数据库、未修改代码或数据。报告中的源码证据均记录了路径、行号和当前文件 SHA-256。

## Failure Object

见 Machine Handoff `failure_object`。用户期望的是长时间运行后本地容量可控、调度计划页保持可交互；当前实现缺少本地存储生命周期管理，并在刷新链路上存在重复和无索引读取。

## Evidence Ledger

完整证据、哈希和限制见 Machine Handoff `evidence`。关键证据是：

- `EV-003/EV-004`：SQLite 明细持续追加，FYP 默认按视频采集。
- `EV-005/EV-006/EV-007`：调度页与 AppShell 重复刷新，健康查询重复读和 O(n²) 冲突检查。
- `EV-008/EV-009`：历史查询无专用索引，读写共享 SQLite。
- `EV-011/EV-012`：h-sector 额度请求属于后台 fire 链路，服务端日志自身有滚动配置。

## Claims

见 Machine Handoff `claims`。当前只提交了代码行为观察和调用链边界，没有提交唯一 root-cause claim。

## Hypotheses

见 Machine Handoff `hypotheses`。需要用户运行时目录大小、SQLite 行数/查询计划和页面分项耗时来决定修复优先级。

## Causal Chain

见 Machine Handoff `causal_chain`。链条已能从代码行为连接到症状，但 `first_wrong_step` 留空，避免把静态可能性误写成已验证的运行时根因。

## Contradictions

当前工作区的 `account-matrix/data/actions.db` 是旧开发/测试数据库，仅有旧 `action_log` 表，不能作为用户运行时容量证据；已在 `CON-001` 中隔离处理。

## Open Unknowns

见 Machine Handoff `open_unknowns`。最关键的三个补证动作是：目录容量快照、页面分项耗时/in-flight trace、SQLite bounded inspection + EXPLAIN。

## Repair Handoff

当前为 `BLOCKED`，因为还没有产品保留周期、用户实际运行时容量和同一失败对象的运行时性能证据。建议修复前先按优先级验证：

1. 先对 actions.db 做只读容量盘点，确认各表、索引、freelist 和备份的占比；浏览器目录与文本日志不纳入清理或修复决策。
2. 在调度页加入刷新去重和分项耗时采样，确认重复探测/健康查询/历史 SQL 的真实占比。
3. 在确认保留周期后，再设计 SQLite retention/归档和历史查询索引迁移。
4. h-sector 侧保持订阅/设备/License 的实时撤销语义；若要减少每个 fire 的校验成本，应设计有明确 TTL/撤销失效机制的批量额度接口，而不是无边界缓存。
