# TDD：废水排放调度系统技术方案设计文档

**文档版本**：v1.3  
**创建日期**：2026-04-10  
**对应PRD**：PRD_废水排放调度系统 v1.5  
**系统定位**：建议层（Advisory System），不控制任何物理设备，不形成闭环控制

> **v1.1 环境适配说明**：根据实际运行环境调整技术选型——Python 升级至 3.13；Oracle 数据库为 11g，Oracle 驱动由 `cx_Oracle` 改为 `python-oracledb`（Thick Mode，需 Oracle Instant Client）；修正所有 Oracle 12c+ 专属 SQL 语法（`FETCH FIRST N ROWS ONLY` → `ROWNUM` 子查询）以兼容 11g。
>
> **v1.2 功能增强说明**：①新增调度输入快照表 `WW_SCHEDULE_INPUT` 和 `WW_SCHEDULE_INPUT_WORKSHOP`，对应新增 `ScheduleInputDAO` 和 `ScheduleInputWorkshopDAO`，在每次调度时写入配置快照；②日志模块重构——改用 `TimedRotatingFileHandler` 按日期滚动（每天独立文件），增加 `LOG_RETENTION_DAYS` 配置（默认 180 天），启动时自动清理超期日志；③算法约束条件日志——在 `SolverService` 和 `SchedulerService` 中增加约束计算值的详细日志输出，包括容量约束、处理能力约束、弹性系数、effective_limit 等中间值。
>
> **v1.3 版本对齐说明**：同步 PRD v1.5 变更——①补充 `SolverParams` 数据类中 `schedule_interval_min` 和 `manual_level_stale_threshold` 字段定义；②补充后续迭代规划中 PRD 已定义但 TDD 遗漏的功能项（移动端告警推送、多储罐支持、液位预测模型、AI智能调度优化）。

---

## 1. 系统整体架构设计

### 1.1 架构风格

采用**单体分层架构**。

理由：
- MVP 阶段规模小（7 个车间、单一 Oracle 实例、单机部署）；
- 调度逻辑无并发诉求（串行执行，每 30 分钟一次）；
- 单体架构开发维护成本最低，符合 MVP 快速落地原则；
- 后续如需横向扩展（多储罐/多厂区），可拆为独立调度服务。

分层结构：触发层 → 服务层 → 求解层 → 数据访问层 → 数据库

### 1.2 系统组成（模块关系）

```
┌──────────────────────────────────────────────────────────┐
│                      触发层（Trigger）                    │
│  APScheduler 定时触发 / CLI 手动触发                      │
└──────────────────────┬───────────────────────────────────┘
                       │ tank_level: float
┌──────────────────────▼───────────────────────────────────┐
│                   调度服务层（Service）                    │
│  SchedulerService：调度主流程编排                         │
│  ConfigService   ：系统参数读取与缓存                     │
│  AlertService    ：分级建议生成与告警构建                  │
└───────────┬──────────────────────┬───────────────────────┘
            │                      │
┌───────────▼──────────┐  ┌────────▼──────────────────────┐
│   求解层（Solver）    │  │      数据访问层（DAO）         │
│  SolverService       │  │  WorkshopDAO / ConfigDAO       │
│  PuLP LP 模型        │  │  TankStatusDAO                 │
│                      │  │  ScheduleResultDAO             │
│                      │  │  AlertLogDAO                   │
└──────────────────────┘  └────────┬──────────────────────┘
                                   │
                          ┌────────▼──────────┐
                          │   Oracle Database  │
                          │  WW_WORKSHOP_INFO  │
                          │  WW_SYSTEM_CONFIG  │
                          │  WW_TANK_STATUS    │
                          │  WW_SCHEDULE_RESULT│
                          │  WW_ALERT_LOG      │
                          └───────────────────┘
```

### 1.3 项目目录结构

```
waste_water/
├── backend/
│   ├── config/
│   │   └── settings.py            # 静态配置（DB 连接串、日志路径等）
│   ├── scheduler/
│   │   ├── trigger.py             # APScheduler 定时触发器 + CLI 手动触发
│   │   ├── scheduler_service.py   # 调度主流程服务
│   │   ├── solver_service.py      # LP 求解服务（PuLP）
│   │   ├── alert_service.py       # 分级建议生成与告警服务
│   │   └── config_service.py      # 系统参数读取与缓存
│   ├── dao/
│   │   ├── base_dao.py            # 数据库连接池封装
│   │   ├── workshop_dao.py
│   │   ├── config_dao.py
│   │   ├── tank_status_dao.py
│   │   ├── schedule_result_dao.py
│   │   ├── alert_log_dao.py
│   │   ├── schedule_input_dao.py        # 调度输入快照 DAO
│   │   └── schedule_input_workshop_dao.py  # 调度输入车间快照 DAO
│   ├── model/
│   │   ├── workshop.py            # 数据类：Workshop
│   │   ├── solver_params.py       # 数据类：SolverParams / SolverResult
│   │   ├── schedule_result.py     # 数据类：ScheduleResultRecord
│   │   ├── tank_status.py         # 数据类：TankStatusRecord
│   │   ├── alert.py               # 数据类：AlertRecord
│   │   └── schedule_input.py      # 数据类：ScheduleInputRecord / ScheduleInputWorkshopRecord
│   ├── utils/
│   │   ├── logger.py              # 日志工具（双文件 RotatingFileHandler）
│   │   └── exceptions.py          # 自定义异常类
│   ├── tests/
│   │   └── test_oracle_conn.py    # Oracle 连接验证脚本
│   └── main.py                    # 程序入口（启动定时器 / CLI 触发）
├── docs/
│   ├── PRD_废水排放调度系统.md
│   ├── TDD_废水排放调度系统.md
│   └── agent.md
├── logs/
│   ├── scheduler.log              # 主日志（运行时自动创建）
│   └── error.log                  # 仅 ERROR 及以上
├── sql/
│   └── init_tables.sql
└── requirements.txt
```

---

## 2. 模块划分设计

### 2.1 调度核心模块（SchedulerService）

**职责**：调度流程总编排，不包含业务逻辑计算，只负责驱动各子模块协作。

**输入**：`tank_level: float`（由触发层传入，来源于人工录入）

**输出**：调度结果写入数据库（无返回值），异常时抛出自定义异常由触发层捕获记录。

**调用链路**：
```
SchedulerService.run(tank_level)
  ├── ConfigService.get_all_params()            → SolverParams
  ├── WorkshopDAO.get_active_workshops()         → List[Workshop]
  ├── TankStatusDAO.get_latest_manual_level()    → (level, create_time)（液位验证）
  ├── _determine_zone(L, params)                 → (zone: str, k: float)
  ├── [NORMAL/WARNING] SolverService.solve(...)  → SolverResult
  ├── [ALERT/EMERGENCY] AlertService.generate_stop_advisory(...)
  ├── _compute_derived(results, L, params)       → L_predicted, allowed_volumes
  └── _write_all(conn, tank_status, results, alert?)  → DB事务写库
```

### 2.2 线性规划求解模块（SolverService）

**PuLP 使用方式**：使用内置 CBC 求解器，设置 `timeLimit=10`，`msg=0`（静默输出）。

**模型构建**：

```python
prob = LpProblem("WasteWaterScheduler", LpMaximize)

# 决策变量：r_i ∈ [r_min, r_max * k]
r = {ws.workshop_id: LpVariable(
         f"r_{ws.workshop_id}",
         lowBound=ws.min_discharge_rate,
         upBound=ws.max_discharge_rate * k)
     for ws in workshops}

# 目标函数：最大化加权总排放速率
prob += lpSum(ws.priority_weight * r[ws.workshop_id] for ws in workshops)

# 约束1：容量约束
capacity_limit = (V * SAFE_RATIO - L) / T + C
prob += lpSum(r[ws.workshop_id] for ws in workshops) <= capacity_limit

# 约束2：处理能力约束
process_limit = C * PROCESS_BUFFER_RATIO
prob += lpSum(r[ws.workshop_id] for ws in workshops) <= process_limit

# 求解（约束3、4已在变量 bounds 中体现）
status = prob.solve(PULP_CBC_CMD(timeLimit=10, msg=0))
```

**参数输入结构**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `workshops` | `List[Workshop]` | 含 workshop_id, max_discharge_rate, min_discharge_rate, priority_weight |
| `L` | `float` | 当前液位 |
| `params` | `SolverParams` | V, C, T, SAFE_RATIO, PROCESS_BUFFER_RATIO 等 |
| `k` | `float` | 弹性系数（正常=1.0，预警区间 ∈ [MIN_RATE_RATIO, 1.0]） |
| `effective_limit` | `float` | min(容量约束上限, 处理能力约束上限)，调用前预计算 |

**SolverParams 数据类定义**：

```python
@dataclass
class SolverParams:
    tank_capacity: float              # V (m³)
    process_capacity: float           # C (m³/h)
    schedule_interval_min: int        # 调度周期（分钟），如 30
    schedule_interval_h: float        # T（小时，如 0.5），由 schedule_interval_min / 60 计算
    safe_ratio: float                 # 默认 0.85
    warning_ratio: float              # 默认 0.80
    alert_ratio: float                # 默认 0.90
    emergency_ratio: float            # 默认 0.95
    min_rate_ratio: float             # 默认 0.30
    process_buffer_ratio: float       # 默认 1.20
    manual_level_stale_threshold: int # 液位超期阈值（调度周期倍数），默认 2
```

**输出**：`SolverResult(status, rates: Dict[str, float], objective_value: float)`

**算法约束条件日志输出（DEBUG 级别）**：

在 `SolverService.solve()` 和 `SchedulerService` 中，记录以下中间计算值，便于验证算法正确性：

```python
# SchedulerService 中记录约束上限计算
logger.debug(f"[{schedule_id}] 约束计算: L={L}, V={V}, T={T}, C={C}")
logger.debug(f"[{schedule_id}] 容量约束: (V*SAFE_RATIO-L)/T+C = ({V}*{safe_ratio}-{L})/{T}+{C} = {capacity_limit:.4f}")
logger.debug(f"[{schedule_id}] 处理能力约束: C*PROCESS_BUFFER_RATIO = {C}*{process_buffer_ratio} = {process_limit:.4f}")
logger.debug(f"[{schedule_id}] 生效约束: effective_limit = min({capacity_limit:.4f}, {process_limit:.4f}) = {effective_limit:.4f}")

# WARNING 区间记录弹性系数计算
if zone == "WARNING":
    logger.debug(f"[{schedule_id}] 弹性系数: k = 1 - (L-{warning_threshold})/(0.1*{V})*(1-{min_rate_ratio}) = {k:.4f}")

# SolverService 中记录各车间约束
for ws in workshops:
    logger.debug(f"[{schedule_id}] 车间{ws.workshop_id}: r_min={ws.min_discharge_rate}, r_max={ws.max_discharge_rate}, elastic_max={ws.max_discharge_rate*k:.4f}")
```

**日志输出示例**：
```
2026-04-13 10:00:00 [DEBUG   ] [uuid-xxx] scheduler_service.run - 约束计算: L=420.0, V=500.0, T=0.5, C=60.0
2026-04-13 10:00:00 [DEBUG   ] [uuid-xxx] scheduler_service.run - 容量约束: (V*SAFE_RATIO-L)/T+C = (500.0*0.85-420.0)/0.5+60.0 = 70.0000
2026-04-13 10:00:00 [DEBUG   ] [uuid-xxx] scheduler_service.run - 处理能力约束: C*PROCESS_BUFFER_RATIO = 60.0*1.2 = 72.0000
2026-04-13 10:00:00 [DEBUG   ] [uuid-xxx] scheduler_service.run - 生效约束: effective_limit = min(70.0000, 72.0000) = 70.0000
2026-04-13 10:00:00 [DEBUG   ] [uuid-xxx] scheduler_service.run - 弹性系数: k = 1 - (420.0-400.0)/(0.1*500.0)*(1-0.3) = 0.7200
```

### 2.3 数据访问层（DAO）

**连接池**：使用 `oracledb.create_pool(min=2, max=5, increment=1, ping_interval=60)`，封装于 `BaseDAO`。驱动须以 **Thick Mode** 初始化（Oracle 11g 服务端不支持 Thin Mode），在 `settings.py` 中完成全局初始化：

```python
import oracledb
# Thick Mode 初始化，lib_dir 指向本机 Oracle Instant Client 目录
oracledb.init_oracle_client(lib_dir=r"C:\oracle\instantclient_11_2")
```

| DAO 类 | 对应表 | 核心方法 |
|--------|--------|----------|
| `WorkshopDAO` | `WW_WORKSHOP_INFO` | `get_active_workshops() → List[Workshop]` |
| `ConfigDAO` | `WW_SYSTEM_CONFIG` | `get_all_configs() → Dict[str, str]` |
| `TankStatusDAO` | `WW_TANK_STATUS` | `insert(conn, record)` / `get_latest_manual_level() → Optional[Tuple[float, datetime]]` |
| `ScheduleResultDAO` | `WW_SCHEDULE_RESULT` | `batch_insert(conn, records: List[ScheduleResultRecord])` |
| `AlertLogDAO` | `WW_ALERT_LOG` | `insert(conn, record: AlertRecord)` |

`BaseDAO` 提供三个通用方法：
- `execute_query(sql, params) → List[dict]`：只读查询，自动归还连接
- `execute_dml(conn, sql, params)`：单条 DML，使用外部传入连接（事务控制）
- `execute_batch(conn, sql, params_list)`：批量 DML，使用 `executemany`

### 2.4 配置管理模块（ConfigService）

**读取来源**：`WW_SYSTEM_CONFIG` 表，`CONFIG_KEY → CONFIG_VALUE`

**缓存策略**：内存字典 + TTL（默认 5 分钟），调度周期 30 分钟，缓存完全足够。

**支持热更新**：调度参数（如 `SCHEDULE_INTERVAL_MIN`、`MANUAL_LEVEL_STALE_THRESHOLD`）从数据库读取，可通过 `restart()` 方法实现配置热重载，无需重启进程。

```python
class ConfigService:
    _cache: Dict[str, str] = {}
    _cache_time: Optional[datetime] = None
    TTL_SECONDS: int = 300

    def _is_expired(self) -> bool:
        return (self._cache_time is None or
                (datetime.now() - self._cache_time).total_seconds() > self.TTL_SECONDS)

    def get_all_params(self) -> SolverParams:
        if self._is_expired():
            self._cache = self._config_dao.get_all_configs()
            self._cache_time = datetime.now()
        return self._parse_params(self._cache)

    def refresh(self) -> None:
        """手动触发时可调用，清除缓存强制重读"""
        self._cache_time = None
```

### 2.5 调度触发模块（SchedulerTrigger）

**定时触发**：`APScheduler BackgroundScheduler` + `IntervalTrigger`

```python
scheduler = BackgroundScheduler(
    executors={'default': ThreadPoolExecutor(max_workers=1)}
)
scheduler.add_job(
    func=trigger.run_once,
    trigger=IntervalTrigger(minutes=interval_minutes),
    max_instances=1,        # 防止任务重叠
    coalesce=True,          # 错过的任务合并为一次
    misfire_grace_time=60
)
```

**手动触发**（CLI）：

```bash
# 在 waste_water/ 根目录下执行
python -m backend.main --manual --level 300.0
```

**液位来源（MVP）**：定时触发时，从 `WW_TANK_STATUS` 读取最近一次 `INPUT_TYPE='MANUAL'` 的液位；若该记录距当前时间超过阈值（由 `MANUAL_LEVEL_STALE_THRESHOLD` 配置，默认 2 倍调度周期），记录 WARNING 日志但仍继续调度（使用该最近值，由运维判断是否有效）。

**热更新支持**：

```python
class SchedulerTrigger:
    def restart(self) -> None:
        """
        热重载调度器：
        1. 从数据库重新读取 SCHEDULE_INTERVAL_MIN 和 MANUAL_LEVEL_STALE_THRESHOLD
        2. 若周期变更，停止旧定时任务并启动新定时任务
        3. 若周期不变，仅刷新配置缓存
        """
    
    def get_interval_min(self) -> int:
        """返回当前调度周期（分钟）"""
    
    def get_stale_threshold(self) -> int:
        """返回当前液位超期阈值（调度周期倍数）"""
```

**进程守护（Windows）**：使用 NSSM 将 `main.py` 注册为 Windows 服务，设置崩溃后自动重启。

### 2.6 异常与告警模块（AlertService）

**生成停排建议**：

```python
def generate_stop_advisory(
    self,
    workshops: List[Workshop],
    tank_level: float,
    zone: str,          # "ALERT" or "EMERGENCY"
    schedule_id: str,
    schedule_time: datetime,
    T: float
) -> List[ScheduleResultRecord]:
    return [ScheduleResultRecord(
        schedule_id=schedule_id,
        schedule_time=schedule_time,
        workshop_id=ws.workshop_id,
        allowed_rate=0.0,
        allowed_volume=0.0,
        tank_level_before=tank_level,
        schedule_status=zone,
        solver_status="SKIPPED"
    ) for ws in workshops]
```

**告警级别映射**：`ALERT → level=2`，`EMERGENCY → level=3`，LP Infeasible → `level=2`

---

## 3. 数据流设计

### 3.1 一次完整调度的数据流

```
[人工录入液位] → INSERT WW_TANK_STATUS (INPUT_TYPE=MANUAL)
                            │
              ┌─────────────▼──────────────────────┐
              │     定时/手动触发 SchedulerService    │
              └─────────────┬──────────────────────┘
                            │
          ┌─────────────────▼──────────────────────┐
          │  Step 1: 读配置                          │
          │  SELECT * FROM WW_SYSTEM_CONFIG          │
          │  → SolverParams (V, C, T, 各阈值)        │
          └─────────────────┬──────────────────────┘
                            │
          ┌─────────────────▼──────────────────────┐
          │  Step 2: 读车间                          │
          │  SELECT * FROM WW_WORKSHOP_INFO          │
          │  WHERE IS_ACTIVE=1                       │
          │  → List[Workshop]                        │
          └─────────────────┬──────────────────────┘
                            │
          ┌─────────────────▼──────────────────────┐
          │  Step 3: 读最新液位                      │
          │  SELECT CURRENT_LEVEL, CREATE_TIME FROM ( │
          │    SELECT CURRENT_LEVEL, CREATE_TIME     │
          │    WW_TANK_STATUS                        │
          │    WHERE INPUT_TYPE='MANUAL'             │
          │    ORDER BY CREATE_TIME DESC             │
          │  ) WHERE ROWNUM = 1                      │
          │  → (L, create_time), 合法性校验          │
          └─────────────────┬──────────────────────┘
                            │
          ┌─────────────────▼──────────────────────┐
          │  Step 4: 区间判断 + 弹性系数             │
          │  → zone: NORMAL/WARNING/ALERT/EMERGENCY  │
          │  → k: float                              │
          └──────┬──────────────────────┬───────────┘
                 │ NORMAL/WARNING        │ ALERT/EMERGENCY
     ┌───────────▼────────┐    ┌────────▼─────────────┐
     │ Step 5a: LP 求解    │    │ Step 5b: 生成停排建议 │
     │ SolverService.solve │    │ r_i=0, status=SKIPPED │
     │ → SolverResult      │    └──────────┬───────────┘
     └───────────┬────────┘               │
                 └─────────────┬──────────┘
                               │
          ┌────────────────────▼───────────────────┐
          │  Step 6: 计算派生字段                    │
          │  allowed_volume_i = r_i * T             │
          │  L_predicted = L + Σ(r_i*T) - C*T      │
          └────────────────────┬───────────────────┘
                               │
          ┌────────────────────▼───────────────────┐
          │  Step 7: 事务写库                        │
          │  INSERT WW_TANK_STATUS (状态+预测液位)   │
          │  INSERT WW_SCHEDULE_RESULT × n (批量)   │
          │  INSERT WW_ALERT_LOG (条件写)            │
          │  COMMIT                                  │
          └───────────────────────────────────────┘
```

### 3.2 数据在模块间的流转

| 流转路径 | 数据类型 |
|----------|----------|
| Trigger → SchedulerService | `tank_level: float` |
| SchedulerService ← ConfigService | `SolverParams` |
| SchedulerService ← WorkshopDAO | `List[Workshop]` |
| SchedulerService → SolverService | `workshops, effective_limit, k, T` |
| SolverService → SchedulerService | `SolverResult(status, rates, obj)` |
| SchedulerService → AlertService | `workshops, tank_level, zone, schedule_id, T` |
| AlertService → SchedulerService | `List[ScheduleResultRecord]` |
| SchedulerService → DAO层 | `TankStatusRecord, List[ScheduleResultRecord], AlertRecord` |

---

## 4. 数据库交互设计

### 4.1 各表访问方式

| 表名 | 读/写 | 调用时机 | 是否在事务内 |
|------|-------|----------|-------------|
| `WW_SYSTEM_CONFIG` | READ | 调度开始（带缓存，TTL=5分钟） | 否 |
| `WW_WORKSHOP_INFO` | READ | 调度开始 | 否 |
| `WW_TANK_STATUS` | READ | 获取最新液位 | 否 |
| `WW_TANK_STATUS` | WRITE | Step 7 写库 | **是** |
| `WW_SCHEDULE_RESULT` | WRITE | Step 7 批量写库 | **是** |
| `WW_ALERT_LOG` | WRITE | Step 7 条件写库 | **是** |

### 4.2 事务设计

Step 7 的三张写操作合并为一个数据库事务：

```python
conn = pool.acquire()
conn.autocommit = False
try:
    tank_dao.insert(conn, tank_status_record)
    result_dao.batch_insert(conn, results)          # executemany 批量
    if alert_record:
        alert_dao.insert(conn, alert_record)
    conn.commit()
except Exception as e:
    conn.rollback()
    logger.error(f"[{schedule_id}] DB写入失败，已回滚: {e}", exc_info=True)
    raise DBWriteError(str(e))
finally:
    pool.release(conn)
```

### 4.3 写入顺序（重要）

1. **WW_TANK_STATUS**：先写当前液位快照，确保状态记录与结果记录时间一致
2. **WW_SCHEDULE_RESULT**：批量写入所有车间的建议结果
3. **WW_ALERT_LOG**：最后写告警，避免结果写失败导致"有告警无对应结果"的孤立数据

### 4.4 序列使用

| 表 | 主键字段 | 序列名 |
|----|---------|--------|
| `WW_TANK_STATUS` | `STATUS_ID` | `SEQ_TANK_STATUS` |
| `WW_SCHEDULE_RESULT` | `RESULT_ID` | `SEQ_SCHEDULE_RESULT` |
| `WW_ALERT_LOG` | `ALERT_ID` | `SEQ_ALERT_LOG` |

INSERT 语句中使用 `SEQ_XXX.NEXTVAL` 生成主键，不由应用层生成。

---

## 5. 调度流程详细设计（时序级）

```
Step 1  [Trigger 触发]
        生成 schedule_id = str(uuid.uuid4())
        记录 schedule_time = datetime.now()
        记录触发方式（定时 / 手动）到日志

Step 2  [读取配置]
        ConfigService.get_all_params()
        ├── 缓存未过期 → 直接返回内存缓存
        └── 缓存过期 → 查询 WW_SYSTEM_CONFIG → 刷新缓存
        异常 → 抛出 ConfigLoadError → 记录 CRITICAL 日志 → 本次调度中止

Step 3  [读取启用车间]
        WorkshopDAO.get_active_workshops()
        SELECT workshop_id, workshop_name, max_discharge_rate,
               min_discharge_rate, priority_weight
        FROM   WW_WORKSHOP_INFO
        WHERE  IS_ACTIVE = 1
        空列表 → 记录 WARNING 日志 → 本次调度中止
        查询异常 → 抛出 DBQueryError → 记录 ERROR 日志 → 本次调度中止

Step 4  [读取最新液位]
        TankStatusDAO.get_latest_manual_level()
        -- Oracle 11g 不支持 FETCH FIRST，使用 ROWNUM 子查询
        SELECT CURRENT_LEVEL, CREATE_TIME FROM (
            SELECT CURRENT_LEVEL, CREATE_TIME
            FROM   WW_TANK_STATUS
            WHERE  INPUT_TYPE = 'MANUAL'
            ORDER  BY CREATE_TIME DESC
        ) WHERE ROWNUM = 1
        校验：L 为 None → 跳过本次调度（记录 ERROR）
             L <= 0    → 跳过本次调度（记录 ERROR）
             L > V     → 以 V 为液位，按 EMERGENCY 处理（记录 ERROR）
        时效检查：若最新记录距今 > 2×T（超时未更新）→ 记录 WARNING，继续调度

Step 5  [液位区间判断]
        level_ratio = L / V
        NORMAL    : level_ratio < WARNING_RATIO       → k = 1.0
        WARNING   : WARNING_RATIO ≤ level_ratio < ALERT_RATIO
                    k = 1 - (L - WARNING_RATIO*V) / (0.1*V) * (1 - MIN_RATE_RATIO)
                    k = max(k, MIN_RATE_RATIO)
        ALERT     : ALERT_RATIO ≤ level_ratio < EMERGENCY_RATIO
        EMERGENCY : level_ratio ≥ EMERGENCY_RATIO

Step 6a [LP 求解]（仅 NORMAL / WARNING 进入）
        capacity_limit  = (V * SAFE_RATIO - L) / T + C
        process_limit   = C * PROCESS_BUFFER_RATIO
        effective_limit = min(capacity_limit, process_limit)
        若 effective_limit ≤ 0 → 跳过求解，生成全零建议（记录 WARNING）
        否则调用 SolverService.solve(workshops, effective_limit, k, T)
        ├── Optimal  → 提取各车间 r_i
        ├── Infeasible → solver_status="Infeasible" → 全零建议 + 准备告警
        └── Timeout  → solver_status="Timeout"     → 全零建议 + 准备告警

Step 6b [停排建议]（ALERT / EMERGENCY 进入）
        AlertService.generate_stop_advisory(workshops, L, zone, ...)
        全部 r_i = 0，solver_status = "SKIPPED"
        AlertService.build_alert_record(L, level_ratio, zone, message)

Step 7  [计算派生字段]
        for each workshop i:
            allowed_volume_i = r_i * T
        L_predicted = max(0.0, L + sum(r_i * T for all i) - C * T)

Step 8  [事务写库]
        conn = pool.acquire(); conn.autocommit = False
        TankStatusDAO.insert(conn, tank_status_record)
        ScheduleResultDAO.batch_insert(conn, results)
        ScheduleInputDAO.insert(conn, schedule_input_record)          # 新增：系统级配置快照
        ScheduleInputWorkshopDAO.batch_insert(conn, input_workshop_records)  # 新增：车间级配置快照
        if alert_record: AlertLogDAO.insert(conn, alert_record)
        conn.commit()
        异常 → conn.rollback() → 记录 ERROR 日志 → 抛出 DBWriteError

Step 9  [完成]
        记录 INFO 日志：schedule_id, zone, n_workshops, elapsed_ms
        等待下次触发
```

---

## 6. 核心类/模块设计

### 6.1 数据类（model/）

```python
# backend/model/workshop.py
@dataclass
class Workshop:
    workshop_id: str
    workshop_name: str
    max_discharge_rate: float
    min_discharge_rate: float
    priority_weight: float

# backend/model/solver_params.py
@dataclass
class SolverParams:
    tank_capacity: float              # V (m³)
    process_capacity: float           # C (m³/h)
    schedule_interval_min: int        # 调度周期（分钟），如 30
    schedule_interval_h: float        # T（小时），由 schedule_interval_min / 60 计算
    safe_ratio: float                 # 默认 0.85
    warning_ratio: float              # 默认 0.80
    alert_ratio: float                # 默认 0.90
    emergency_ratio: float            # 默认 0.95
    min_rate_ratio: float             # 默认 0.30
    process_buffer_ratio: float       # 默认 1.20
    manual_level_stale_threshold: int # 液位超期阈值（调度周期倍数），默认 2

@dataclass
class SolverResult:
    status: str                              # "Optimal" / "Infeasible" / "Timeout"
    rates: Dict[str, float]                  # workshop_id → r_i (m³/h)
    objective_value: Optional[float]         # 加权总排放速率

# backend/model/schedule_result.py
@dataclass
class ScheduleResultRecord:
    schedule_id: str
    schedule_time: datetime
    workshop_id: str
    allowed_rate: float          # r_i (m³/h)
    allowed_volume: float        # r_i * T (m³)
    tank_level_before: float
    schedule_status: str         # NORMAL / WARNING / ALERT / EMERGENCY
    solver_status: str           # Optimal / Infeasible / SKIPPED / Timeout

# backend/model/tank_status.py
@dataclass
class TankStatusRecord:
    record_time: datetime
    current_level: float
    level_ratio: float
    tank_status: str
    predicted_level: Optional[float]
    input_type: str = "MANUAL"
    create_time: datetime = field(default_factory=datetime.now)

# backend/model/alert.py
@dataclass
class AlertRecord:
    schedule_id: str             # 调度批次号，关联 WW_SCHEDULE_RESULT
    alert_time: datetime
    alert_level: int             # 2=ALERT, 3=EMERGENCY
    tank_level: float
    level_ratio: float
    alert_message: str
    is_handled: int = 0

# backend/model/schedule_input.py
@dataclass
class ScheduleInputRecord:
    schedule_id: str
    schedule_time: datetime
    tank_capacity: float
    process_capacity: float
    schedule_interval_min: int
    safe_ratio: float
    warning_ratio: float
    alert_ratio: float
    emergency_ratio: float
    min_rate_ratio: float
    process_buffer_ratio: float
    tank_level: float
    level_ratio: float
    zone: str
    elastic_k: Optional[float]
    capacity_limit: Optional[float]
    process_limit: Optional[float]
    effective_limit: Optional[float]
    workshop_count: int

@dataclass
class ScheduleInputWorkshopRecord:
    schedule_id: str
    workshop_id: str
    workshop_name: str
    max_discharge_rate: float
    min_discharge_rate: float
    priority_weight: float
    elastic_max_rate: Optional[float]
    create_time: datetime
```

### 6.2 DAO 层

```python
# backend/dao/base_dao.py
class BaseDAO:
    def __init__(self, pool: oracledb.ConnectionPool): ...
    def execute_query(self, sql: str, params: dict = None) -> List[dict]: ...
    def execute_dml(self, conn, sql: str, params: dict) -> None: ...
    def execute_batch(self, conn, sql: str, params_list: List[dict]) -> None: ...

# backend/dao/workshop_dao.py
class WorkshopDAO(BaseDAO):
    def get_active_workshops(self) -> List[Workshop]: ...

# backend/dao/config_dao.py
class ConfigDAO(BaseDAO):
    def get_all_configs(self) -> Dict[str, str]: ...

# backend/dao/tank_status_dao.py
class TankStatusDAO(BaseDAO):
    def insert(self, conn, record: TankStatusRecord) -> None: ...
    def get_latest_manual_level(self) -> Optional[Tuple[float, datetime]]: ...

# backend/dao/schedule_result_dao.py
class ScheduleResultDAO(BaseDAO):
    def batch_insert(self, conn, records: List[ScheduleResultRecord]) -> None: ...

# backend/dao/alert_log_dao.py
class AlertLogDAO(BaseDAO):
    def insert(self, conn, record: AlertRecord) -> None: ...

# backend/dao/schedule_input_dao.py
class ScheduleInputDAO(BaseDAO):
    def insert(self, conn, record: ScheduleInputRecord) -> None:
        """写入调度输入系统级快照，主键使用 SEQ_SCHEDULE_INPUT.NEXTVAL"""

# backend/dao/schedule_input_workshop_dao.py
class ScheduleInputWorkshopDAO(BaseDAO):
    def batch_insert(self, conn, records: List[ScheduleInputWorkshopRecord]) -> None:
        """批量写入调度输入车间级快照，主键使用 SEQ_SCHEDULE_INPUT_WORKSHOP.NEXTVAL"""
```

### 6.3 服务层

```python
# backend/scheduler/config_service.py
class ConfigService:
    def __init__(self, config_dao: ConfigDAO): ...
    def get_all_params(self) -> SolverParams: ...
    def get(self, key: str) -> str: ...
    def get_float(self, key: str) -> float: ...
    def get_int(self, key: str) -> int: ...
    def refresh(self) -> None: ...
    def _is_expired(self) -> bool: ...
    def _parse_params(self, raw: Dict[str, str]) -> SolverParams: ...

# backend/scheduler/solver_service.py
class SolverService:
    def solve(
        self,
        workshops: List[Workshop],
        effective_limit: float,
        k: float,
        T: float
    ) -> SolverResult: ...
    def _build_model(
        self,
        workshops: List[Workshop],
        effective_limit: float,
        k: float,
        T: float
    ) -> Tuple[LpProblem, Dict[str, LpVariable]]: ...
    def _parse_result(
        self,
        prob: LpProblem,
        r_vars: Dict[str, LpVariable]
    ) -> SolverResult: ...

# backend/scheduler/alert_service.py
class AlertService:
    def __init__(self, alert_dao: AlertLogDAO): ...
    def generate_stop_advisory(
        self,
        workshops: List[Workshop],
        tank_level: float,
        zone: str,
        schedule_id: str,
        schedule_time: datetime,
        T: float
    ) -> List[ScheduleResultRecord]: ...
    def build_alert_record(
        self,
        schedule_id: str,
        tank_level: float,
        level_ratio: float,
        zone: str,
        reason: str
    ) -> AlertRecord: ...

# backend/scheduler/scheduler_service.py
class SchedulerService:
    def __init__(
        self,
        config_svc: ConfigService,
        solver_svc: SolverService,
        alert_svc: AlertService,
        workshop_dao: WorkshopDAO,
        tank_dao: TankStatusDAO,
        result_dao: ScheduleResultDAO,
        alert_dao: AlertLogDAO,
        schedule_input_dao: ScheduleInputDAO,
        schedule_input_workshop_dao: ScheduleInputWorkshopDAO,
        pool: oracledb.ConnectionPool
    ): ...
    def run(self, tank_level: float) -> None: ...
    def _determine_zone(
        self, L: float, params: SolverParams
    ) -> Tuple[str, float]: ...           # 返回 (zone, k)
    def _compute_k(self, L: float, params: SolverParams) -> float: ...
    def _compute_derived(
        self,
        results: List[ScheduleResultRecord],
        L: float,
        params: SolverParams
    ) -> float: ...                        # 返回 L_predicted
    def _write_all(
        self,
        conn,
        tank_record: TankStatusRecord,
        results: List[ScheduleResultRecord],
        schedule_input: ScheduleInputRecord,
        input_workshops: List[ScheduleInputWorkshopRecord],
        alert: Optional[AlertRecord]
    ) -> None: ...
```

### 6.4 触发层

```python
# backend/scheduler/trigger.py
class SchedulerTrigger:
    def __init__(
        self,
        scheduler_svc: SchedulerService,
        config_svc: ConfigService,
        tank_dao: TankStatusDAO
    ): ...
    def start(self) -> None: ...         # 启动 APScheduler
    def stop(self) -> None: ...          # 优雅停止
    def run_once(self) -> None: ...      # APScheduler 回调：读取最新液位 → 触发调度

# backend/main.py（入口）
def run_manual(tank_level: float) -> None: ...  # CLI 手动触发
```

---

## 7. 异常处理设计

### 7.1 LP 无解（Infeasible）

**触发**：`n × r_min > effective_limit`，约束不可行。

**处理**：
1. `solver_status = "Infeasible"`
2. 生成全零保守建议（所有 `r_i = 0`）
3. 构建 `AlertRecord(level=2, message="LP求解无可行解，已生成保守建议，请检查参数配置")`
4. 正常走事务写库，结果与告警一并入库

### 7.2 数据异常（液位非法）

| 情形 | 处理方式 |
|------|----------|
| `L is None` 或 `L <= 0` | 记录 ERROR，跳过本次调度，不写任何结果 |
| `L > V` | 记录 ERROR，将 `L` 置为 `V`，以 EMERGENCY 区间处理（最保守） |
| 液位超 2 周期未更新 | 记录 WARNING，继续调度，使用最近值 |

### 7.3 DB 写入失败

**触发**：`oracledb` 抛出 `DatabaseError`（网络中断、ORA-* 等）。

**处理**：
1. `conn.rollback()`，不写半段数据
2. `logger.error(f"[{schedule_id}] DB写入失败", exc_info=True)`
3. 不重试（避免重复数据），等待下一调度周期重新执行
4. 连接池的 `ping_interval=60` 自动检测并重建断开的连接

### 7.4 求解超时

**触发**：PuLP CBC `timeLimit=10` 到达，返回非 Optimal 状态码。

**处理**：
1. 检查 `LpStatus[prob.status] != "Optimal"` → `solver_status = "Timeout"`
2. 生成全零保守建议
3. 写入告警（`level=2, message="LP求解超时，已生成保守建议"`）

### 7.5 自定义异常类

```python
# utils/exceptions.py
class SchedulerBaseError(Exception): pass
class ConfigLoadError(SchedulerBaseError): pass
class DBQueryError(SchedulerBaseError): pass
class DBWriteError(SchedulerBaseError): pass
class InvalidTankLevelError(SchedulerBaseError): pass
class NoActiveWorkshopError(SchedulerBaseError): pass
```

---

## 8. 非功能设计

### 8.1 性能

| 环节 | 目标耗时 |
|------|---------|
| 配置读取（缓存命中） | < 1 ms |
| 车间读取（7 条） | < 50 ms |
| LP 求解（7 变量，CBC） | < 100 ms（实测通常 < 10 ms） |
| DB 批量写入（约 9 条） | < 500 ms |
| 全流程端到端 | < 1 s |

### 8.2 稳定性

**任务重叠防护**：`max_instances=1`，`coalesce=True`，`misfire_grace_time=60`

**连接池配置**：
```python
import oracledb
# 程序启动时全局初始化一次（Thick Mode，连接 Oracle 11g 必须）
oracledb.init_oracle_client(lib_dir=r"C:\oracle\instantclient_11_2")

pool = oracledb.create_pool(
    user=user, password=password, dsn=dsn,
    min=2, max=5, increment=1,
    ping_interval=60          # 定期 ping，自动重建断开连接
)
```

**进程守护（Windows）**：
- 使用 NSSM 注册为 Windows 服务，设置失败后自动重启
- 或使用 Windows 任务计划程序，触发条件"程序退出时重启"

### 8.3 日志

**框架**：Python 标准库 `logging` + `TimedRotatingFileHandler`（按日期滚动）

**日志文件**：
- `logs/scheduler-YYYY-MM-DD.log`：INFO 及以上，每天独立文件
- `logs/error-YYYY-MM-DD.log`：ERROR 及以上，每天独立文件，便于运维监控

**日志配置参数**（`settings.py`）：
```python
LOG_RETENTION_DAYS: int = 180  # 日志保留天数，默认半年
```

**日志格式**：
```
%(asctime)s [%(levelname)-8s] %(module)s.%(funcName)s - %(message)s
```

**超期日志清理**：
- 在 `get_logger()` 首次调用时执行清理
- 遍历 `logs/` 目录，删除修改时间超过 `LOG_RETENTION_DAYS` 的日志文件
- 清理逻辑独立，不影响当前日志写入性能

**关键日志点**：

| 级别 | 场景 |
|------|------|
| INFO | 调度开始/完成，写库成功，求解状态 |
| WARNING | 液位超期未更新，车间列表为空，缓存刷新 |
| ERROR | DB 异常，液位非法，LP Infeasible/Timeout |
| CRITICAL | 配置加载失败，连接池初始化失败 |
| DEBUG | 算法约束条件计算值（容量约束、处理能力约束、弹性系数等）|

---

## 9. 技术选型说明

| 技术组件 | 版本/规格 | 选型理由 |
|----------|---------|---------|
| Python | **3.13**（本地实际版本） | 完全兼容 `dataclass`、`typing`；`python-oracledb` 官方支持 3.13 |
| PuLP | 2.7+ | 内置 CBC 求解器，无需额外安装；7 变量规模 < 10 ms 求解 |
| APScheduler | 3.10+ | `BackgroundScheduler` 轻量，支持 `max_instances=1` 防重叠 |
| python-oracledb | 2.x+ | Oracle 官方新驱动，替代已停止维护的 `cx_Oracle`；Python 3.13 兼容；支持连接池与 `executemany` |
| Oracle Instant Client | **11.2**（与数据库版本匹配） | Thick Mode 必需；本机安装后通过 `oracledb.init_oracle_client(lib_dir=...)` 指定路径 |
| Oracle Database | **11g**（服务端实际版本） | 不支持 Thin Mode，须使用 Thick Mode 连接；不支持 `FETCH FIRST N ROWS ONLY`，查询需使用 `ROWNUM` 子查询 |

> **Thick Mode 说明**：`python-oracledb` 默认使用 Thin Mode（无需 Oracle Client），但 Thin Mode 仅支持 Oracle 12.1+ 服务端。连接 Oracle 11g **必须**使用 Thick Mode，需在程序启动时调用 `oracledb.init_oracle_client(lib_dir=...)`。

**依赖文件（requirements.txt）**：

```
pulp>=2.7.0
APScheduler>=3.10.0
oracledb>=2.0.0
```

---

## 10. MVP 实现范围（技术视角）

### 10.1 第一版必须实现

| 模块 | 实现内容 |
|------|---------|
| `SchedulerService` | 完整调度流程：读配置 → 读车间 → 液位校验 → 区间判断 → 求解/停排建议 → 派生计算 → 事务写库 |
| `SolverService` | PuLP LP 模型：4 约束 + 加权目标函数，CBC 10s 超时 |
| `ConfigService` | DB 读取 + 内存缓存（TTL=5 分钟）+ `refresh()` |
| `WorkshopDAO` | `get_active_workshops()` |
| `TankStatusDAO` | `insert()` + `get_latest_manual_level()` |
| `ScheduleResultDAO` | `batch_insert()`（`executemany`） |
| `AlertLogDAO` | `insert()` |
| `AlertService` | `generate_stop_advisory()` + `build_alert_record()` |
| `SchedulerTrigger` | APScheduler 定时触发 + CLI 手动触发（`--manual --level`） |
| 日志模块 | 双文件日志（`scheduler.log` / `error.log`） |
| 异常处理 | Infeasible / Timeout / DB 失败 / 液位非法 全覆盖 |

### 10.2 MVP 阶段预留（不实现，保留接口占位）

> 以下迭代规划与 PRD v1.5 第9.2节保持一致

| 预留项 | 预留方式 | 规划版本 |
|--------|---------|---------|
| 传感器自动采集液位 | `WW_TANK_STATUS.INPUT_TYPE` 字段已预留 `AUTO` 值 | v1.1 |
| REST API（手动触发/查询接口） | `trigger.run_once()` 可被 Flask/FastAPI 路由调用 | v1.1 |
| 移动端告警推送 | 通过短信/企业微信推送告警通知 | v1.2 |
| 前端可视化界面 | 数据已完整入库，直接对接前端 | v2.0 |
| 液位预测模型 | 基于历史数据预测未来液位，提前干预 | v2.0 |
| 多储罐支持 | 扩展支持多个储罐的联合调度 | v2.0 |
| 调度效果分析报表 | 定期生成调度效果统计报告 | v2.0 |
| AI 智能调度优化 | 引入强化学习或机器学习优化调度策略 | v3.0 |

---

*文档结束*
