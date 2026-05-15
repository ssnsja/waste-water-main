# Agent 开发任务书：废水排放调度系统

**对应文档**：TDD_废水排放调度系统 v1.3 / PRD_废水排放调度系统 v1.5  
**系统定位**：建议层（Advisory System），不控制任何物理设备，不形成闭环控制  
**编写原则**：每条 Task 均可直接交给 AI Agent 执行，无歧义，有验收标准

---

## 开发规范（强制遵守）

### 代码风格
- Python 3.13，全部使用 **类型注解**（`from __future__ import annotations` 可选）
- 所有数据类使用 `@dataclass`，禁止使用裸字典传参
- 公共方法必须有 **docstring**（一句话说明职责）
- 常量全大写，非常量用小写下划线命名
- 禁止在 DAO 层做业务判断；禁止在 Service 层直接写 SQL

### 异常处理
- 所有异常统一使用 `utils/exceptions.py` 中定义的自定义异常
- DAO 层捕获 `oracledb.DatabaseError`，包装后抛出 `DBQueryError` / `DBWriteError`
- Service 层只捕获已知异常，未知异常向上透传

### 日志规范
- 所有模块通过 `utils/logger.py` 获取 logger，**不允许** `print` 替代日志
- 关键日志消息中应包含 `schedule_id` 上下文，便于追踪
- 关键节点必须打日志：调度开始/完成、DB 操作、异常、区间判断结果

### Oracle SQL 规范
- **全部使用 ROWNUM 子查询**，禁止 `FETCH FIRST N ROWS ONLY`（Oracle 11g 不兼容）
- 参数绑定使用命名参数 `:param_name`，禁止字符串拼接 SQL
- `INSERT` 主键使用 `SEQ_XXX.NEXTVAL`，不由应用层生成

### 项目结构（固定，不可随意新增目录）
```
waste_water/
├── backend/
│   ├── config/
│   │   └── settings.py
│   ├── scheduler/
│   │   ├── trigger.py
│   │   ├── scheduler_service.py
│   │   ├── solver_service.py
│   │   ├── alert_service.py
│   │   └── config_service.py
│   ├── dao/
│   │   ├── base_dao.py
│   │   ├── workshop_dao.py
│   │   ├── config_dao.py
│   │   ├── tank_status_dao.py
│   │   ├── schedule_result_dao.py
│   │   ├── alert_log_dao.py
│   │   ├── schedule_input_dao.py
│   │   └── schedule_input_workshop_dao.py
│   ├── model/
│   │   ├── workshop.py
│   │   ├── solver_params.py
│   │   ├── schedule_result.py
│   │   ├── tank_status.py
│   │   ├── alert.py
│   │   └── schedule_input.py
│   ├── utils/
│   │   ├── logger.py
│   │   └── exceptions.py
│   ├── tests/              # 所有测试脚本放此目录
│   │   └── test_oracle_conn.py
│   └── main.py
├── docs/
├── logs/               # 运行时自动创建，不提交 git
├── sql/
└── requirements.txt
```

---

## T0 — 环境验证（开发前置，必须通过才能进行后续任务）

### T0-1：Oracle 连接可用性测试

**文件**：`backend/tests/test_oracle_conn.py`  
**目标**：验证本地 Python 3.13 + python-oracledb Thick Mode 能否连通本地 Oracle 11g

**必须验证的项目**：
1. `python-oracledb` 包可正常 `import`
2. `oracledb.init_oracle_client(lib_dir=...)` 不抛出异常（Oracle Instant Client 11.2 路径有效）
3. 使用账号/密码/DSN 创建连接池 `oracledb.create_pool(min=1, max=2, ...)`
4. 从连接池获取连接并执行 `SELECT 1 FROM DUAL`，返回结果为 `[(1,)]`
5. 执行 `SELECT * FROM WW_SYSTEM_CONFIG WHERE ROWNUM = 1`，能返回结果（验证表存在）
6. 正确释放连接并关闭连接池

**脚本输出规范**：
```
[OK] oracledb 导入成功，版本: x.x.x
[OK] Thick Mode 初始化成功
[OK] 连接池创建成功
[OK] SELECT 1 FROM DUAL 执行成功
[OK] WW_SYSTEM_CONFIG 表可访问
[OK] 连接资源释放完毕
--- 环境验证通过，可以开始开发 ---
```
若任一步骤失败，输出 `[FAIL] 原因:...` 并终止，**不继续后续步骤**。

**验收标准**：脚本运行无异常，全部打印 `[OK]`。

---

## Phase 1 — MVP 核心开发

> **MVP 范围说明**：T1~T26 均为 MVP 必须实现的功能，对应 PRD v1.5 第9.1节 P0 功能清单。
>
> **执行顺序**：T1 → T2 → T3~T7（可并行）→ T8~T9（可并行）→ T10 → T11~T15（可并行）→ T16 → T17 → T18 → T19 → T20 → T21~T22（可并行）→ T23~T25（顺序执行）→ T26（程序入口）
>
> **T21~T25 说明**：这些任务是对基础模块的增强/修改——T21-T22 新增快照数据类和 DAO；T23 验证日志模块实现（依赖T9）；T24 增强约束日志输出（修改T17/T19）；T25 集成快照写入到 SchedulerService（修改T19）。程序入口 T26 必须在所有模块完成后执行。

---

### T1：项目初始化

**文件**：`requirements.txt`  
**内容**（固定版本下限）：
```
pulp>=2.7.0
APScheduler>=3.10.0
oracledb>=2.0.0
```
**验收**：`pip install -r requirements.txt` 无报错。

---

### T2：静态配置模块

**文件**：`backend/config/settings.py`  
**职责**：集中管理所有静态配置，不含业务逻辑

**必须包含**：
```python
# Oracle Thick Mode 初始化（程序启动时调用一次）
ORACLE_CLIENT_LIB_DIR: str = r"C:\oracle\instantclient_11_2"

# 连接池参数
DB_USER: str = "..."
DB_PASSWORD: str = "..."
DB_DSN: str = "host:port/service_name"
POOL_MIN: int = 2
POOL_MAX: int = 5
POOL_INCREMENT: int = 1
POOL_PING_INTERVAL: int = 60

# 日志参数
LOG_DIR: str = "logs"
SCHEDULER_LOG: str = "logs/scheduler.log"
ERROR_LOG: str = "logs/error.log"
LOG_MAX_BYTES: int = 10 * 1024 * 1024   # 10MB
LOG_BACKUP_COUNT: int = 5

# 注意：调度参数（SCHEDULE_INTERVAL_MIN、MANUAL_LEVEL_STALE_THRESHOLD）
# 已迁移至数据库 WW_SYSTEM_CONFIG 表，由 ConfigService 动态读取
```
**验收**：`from backend.config.settings import DB_DSN` 无报错。

---

### T3：数据类 — Workshop

**文件**：`backend/model/workshop.py`

```python
@dataclass
class Workshop:
    workshop_id: str
    workshop_name: str
    max_discharge_rate: float   # 最大排放速率 m³/h
    min_discharge_rate: float   # 最小排放速率 m³/h
    priority_weight: float      # 优先权重
```
**验收**：实例化一个 `Workshop` 对象，`repr` 输出包含所有字段。

---

### T4：数据类 — SolverParams / SolverResult

**文件**：`backend/model/solver_params.py`

```python
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
    status: str                           # "Optimal" / "Infeasible" / "Timeout"
    rates: Dict[str, float]               # workshop_id → r_i (m³/h)
    objective_value: Optional[float]      # 加权总排放速率，Infeasible/Timeout 时为 None
```
**验收**：实例化两个数据类，字段赋值正确。

---

### T5：数据类 — ScheduleResultRecord

**文件**：`backend/model/schedule_result.py`

```python
@dataclass
class ScheduleResultRecord:
    schedule_id: str
    schedule_time: datetime
    workshop_id: str
    allowed_rate: float        # r_i (m³/h)
    allowed_volume: float      # r_i * T (m³)
    tank_level_before: float
    schedule_status: str       # NORMAL / WARNING / ALERT / EMERGENCY
    solver_status: str         # Optimal / Infeasible / SKIPPED / Timeout
```
**验收**：实例化并检查字段类型。

---

### T6：数据类 — TankStatusRecord

**文件**：`backend/model/tank_status.py`

```python
@dataclass
class TankStatusRecord:
    record_time: datetime
    current_level: float
    level_ratio: float
    tank_status: str
    predicted_level: Optional[float]
    input_type: str = "MANUAL"   # "MANUAL" | "AUTO" (预留)
    create_time: datetime = field(default_factory=datetime.now)
```
**验收**：实例化，验证 `input_type` 默认值为 `"MANUAL"`。

---

### T7：数据类 — AlertRecord

**文件**：`backend/model/alert.py`

```python
@dataclass
class AlertRecord:
    schedule_id: str           # 调度批次号，关联 WW_SCHEDULE_RESULT
    alert_time: datetime
    alert_level: int           # 2=ALERT, 3=EMERGENCY
    tank_level: float
    level_ratio: float
    alert_message: str
    is_handled: int = 0
```
**验收**：实例化，验证 `is_handled` 默认值为 `0`。

---

### T8：自定义异常模块

**文件**：`backend/utils/exceptions.py`

```python
class SchedulerBaseError(Exception): pass
class ConfigLoadError(SchedulerBaseError): pass
class DBQueryError(SchedulerBaseError): pass
class DBWriteError(SchedulerBaseError): pass
class InvalidTankLevelError(SchedulerBaseError): pass
class NoActiveWorkshopError(SchedulerBaseError): pass
```
**验收**：`raise DBQueryError("test")` 能被 `except SchedulerBaseError` 捕获。

---

### T9：日志工具模块

**文件**：`backend/utils/logger.py`  
**职责**：提供全局 logger，双文件输出，支持 `schedule_id` 上下文注入

**实现要求**：
- 使用 `TimedRotatingFileHandler`，按天滚动，文件名格式 `scheduler-YYYY-MM-DD.log`（INFO+）、`error-YYYY-MM-DD.log`（ERROR+）
- 日志格式：`%(asctime)s [%(levelname)-8s] %(module)s.%(funcName)s - %(message)s`
- 提供 `get_logger(name: str) -> logging.Logger` 函数，所有模块统一调用此函数获取 logger
- 首次调用时自动创建 `logs/` 目录（不存在时）
- 支持超期日志自动清理（配置 `LOG_RETENTION_DAYS`，默认 180 天）

**验收**：调用 `get_logger("test").info("hello")`，`logs/scheduler-YYYY-MM-DD.log` 文件存在且含该条记录。

---

### T10：DAO 基类 — BaseDAO（连接池封装）

**文件**：`backend/dao/base_dao.py`  
**职责**：封装连接池，提供三个通用数据库操作方法

**实现要求**：
```python
class BaseDAO:
    def __init__(self, pool: oracledb.ConnectionPool) -> None: ...

    def execute_query(self, sql: str, params: dict = None) -> List[dict]:
        """只读查询，自动从池获取连接，查完自动归还，返回字典列表"""

    def execute_dml(self, conn, sql: str, params: dict) -> None:
        """单条 DML，使用外部传入连接（调用方控制事务）"""

    def execute_batch(self, conn, sql: str, params_list: List[dict]) -> None:
        """批量 DML，使用 executemany，使用外部传入连接"""
```

**关键细节**：
- `execute_query` 内部用 `try/finally` 确保连接归还 `pool.release(conn)`
- 列名使用 `cursor.description` 动态映射为字典 key（全部转小写）
- 捕获 `oracledb.DatabaseError`，包装为 `DBQueryError` / `DBWriteError` 后抛出

**验收**：需要数据库在线，调用 `execute_query("SELECT 1 FROM DUAL")` 返回 `[{'1': 1}]`（或类似结构）。

---

### T11：WorkshopDAO

**文件**：`backend/dao/workshop_dao.py`

**实现要求**：
```python
class WorkshopDAO(BaseDAO):
    def get_active_workshops(self) -> List[Workshop]:
        """查询 IS_ACTIVE=1 的车间列表，按 WORKSHOP_ID 排序"""
```

**SQL**：
```sql
SELECT WORKSHOP_ID, WORKSHOP_NAME, MAX_DISCHARGE_RATE,
       MIN_DISCHARGE_RATE, PRIORITY_WEIGHT
FROM   WW_WORKSHOP_INFO
WHERE  IS_ACTIVE = 1
ORDER  BY WORKSHOP_ID
```

**验收**：调用返回 `List[Workshop]`，字段映射正确（注意大小写转换）。

---

### T12：ConfigDAO

**文件**：`backend/dao/config_dao.py`

**实现要求**：
```python
class ConfigDAO(BaseDAO):
    def get_all_configs(self) -> Dict[str, str]:
        """返回所有配置项字典，key=CONFIG_KEY，value=CONFIG_VALUE"""
```

**SQL**：
```sql
SELECT CONFIG_KEY, CONFIG_VALUE
FROM   WW_SYSTEM_CONFIG
```

**验收**：调用返回字典，能取到如 `"TANK_CAPACITY"` 等 key。

---

### T13：TankStatusDAO

**文件**：`backend/dao/tank_status_dao.py`

**实现要求**：
```python
class TankStatusDAO(BaseDAO):
    def get_latest_manual_level(self) -> Optional[Tuple[float, datetime]]:
        """返回最新一条 INPUT_TYPE=MANUAL 的液位值和创建时间，无记录返回 None"""

    def insert(self, conn, record: TankStatusRecord) -> None:
        """写入液位快照，主键使用 SEQ_TANK_STATUS.NEXTVAL"""
```

**SQL（get_latest_manual_level，Oracle 11g 兼容）**：
```sql
SELECT CURRENT_LEVEL, CREATE_TIME FROM (
    SELECT CURRENT_LEVEL, CREATE_TIME
    FROM   WW_TANK_STATUS
    WHERE  INPUT_TYPE = 'MANUAL'
    ORDER  BY CREATE_TIME DESC
) WHERE ROWNUM = 1
```

**INSERT SQL**：
```sql
INSERT INTO WW_TANK_STATUS
    (STATUS_ID, RECORD_TIME, CURRENT_LEVEL, LEVEL_RATIO,
     TANK_STATUS, PREDICTED_LEVEL, INPUT_TYPE, CREATE_TIME)
VALUES
    (SEQ_TANK_STATUS.NEXTVAL, :record_time, :current_level, :level_ratio,
     :tank_status, :predicted_level, :input_type, :create_time)
```

**验收**：
- `get_latest_manual_level()` 在有数据时返回 `(float, datetime)`
- `insert()` 在事务内执行不报错，commit 后数据可查询

---

### T14：ScheduleResultDAO

**文件**：`backend/dao/schedule_result_dao.py`

**实现要求**：
```python
class ScheduleResultDAO(BaseDAO):
    def batch_insert(self, conn, records: List[ScheduleResultRecord]) -> None:
        """批量写入调度结果，使用 executemany，主键使用 SEQ_SCHEDULE_RESULT.NEXTVAL"""
```

**INSERT SQL（executemany 写法）**：
```sql
INSERT INTO WW_SCHEDULE_RESULT
    (RESULT_ID, SCHEDULE_ID, SCHEDULE_TIME, WORKSHOP_ID,
     ALLOWED_RATE, ALLOWED_VOLUME, TANK_LEVEL_BEFORE,
     SCHEDULE_STATUS, SOLVER_STATUS)
VALUES
    (SEQ_SCHEDULE_RESULT.NEXTVAL, :schedule_id, :schedule_time, :workshop_id,
     :allowed_rate, :allowed_volume, :tank_level_before,
     :schedule_status, :solver_status)
```

**验收**：传入 3 条 `ScheduleResultRecord`，批量写入，commit 后表中新增 3 条记录。

---

### T15：AlertLogDAO

**文件**：`backend/dao/alert_log_dao.py`

**实现要求**：
```python
class AlertLogDAO(BaseDAO):
    def insert(self, conn, record: AlertRecord) -> None:
        """写入告警记录，主键使用 SEQ_ALERT_LOG.NEXTVAL"""
```

**INSERT SQL**：
```sql
INSERT INTO WW_ALERT_LOG
    (ALERT_ID, SCHEDULE_ID, ALERT_TIME, ALERT_LEVEL, TANK_LEVEL,
     LEVEL_RATIO, ALERT_MESSAGE, IS_HANDLED, CREATE_TIME)
VALUES
    (SEQ_ALERT_LOG.NEXTVAL, :schedule_id, :alert_time, :alert_level, :tank_level,
     :level_ratio, :alert_message, :is_handled, :create_time)
```

**验收**：写入一条 `AlertRecord`，commit 后可查询到。

---

### T16：ConfigService（配置读取与缓存）

**文件**：`backend/scheduler/config_service.py`  
**职责**：从 DB 读取系统配置，内存缓存（TTL=5分钟），提供强类型解析接口

**实现要求**：
```python
class ConfigService:
    TTL_SECONDS: int = 300
    _cache: Dict[str, str] = {}
    _cache_time: Optional[datetime] = None

    def __init__(self, config_dao: ConfigDAO) -> None: ...

    def get_all_params(self) -> SolverParams:
        """缓存未过期直接返回，过期则查 DB 刷新缓存后返回"""

    def get(self, key: str) -> str: ...
    def get_float(self, key: str) -> float: ...
    def get_int(self, key: str) -> int: ...

    def refresh(self) -> None:
        """手动清除缓存，下次 get_all_params 会强制重读 DB"""

    def _is_expired(self) -> bool: ...
    def _parse_params(self, raw: Dict[str, str]) -> SolverParams: ...
```

**_parse_params 必须映射的 CONFIG_KEY**：

| CONFIG_KEY | SolverParams 字段 | 默认值 |
|---|---|---|
| TANK_CAPACITY | tank_capacity | 无默认，必填 |
| PROCESS_CAPACITY | process_capacity | 无默认，必填 |
| SCHEDULE_INTERVAL_MIN | schedule_interval_min（整型，分钟） | 30 |
| MANUAL_LEVEL_STALE_THRESHOLD | manual_level_stale_threshold（整型，周期倍数） | 2 |
| SAFE_RATIO | safe_ratio | 0.85 |
| WARNING_RATIO | warning_ratio | 0.80 |
| ALERT_RATIO | alert_ratio | 0.90 |
| EMERGENCY_RATIO | emergency_ratio | 0.95 |
| MIN_RATE_RATIO | min_rate_ratio | 0.30 |
| PROCESS_BUFFER_RATIO | process_buffer_ratio | 1.20 |

**缓存失效场景**：`_cache_time is None` 或 `(now - _cache_time).total_seconds() > TTL_SECONDS`

**验收**：
- 首次调用查 DB，第二次调用不查 DB（可通过日志验证）
- `refresh()` 后下次调用重新查 DB
- 返回的 `SolverParams.schedule_interval_min` 为 `30`（当数据库配置为30时）
- 返回的 `SolverParams.manual_level_stale_threshold` 为 `2`（当数据库配置为2时）

---

### T17：SolverService（LP 求解）

**文件**：`backend/scheduler/solver_service.py`  
**职责**：构建 PuLP LP 模型并求解，返回各车间建议排放速率

**实现要求**：
```python
class SolverService:
    def solve(
        self,
        workshops: List[Workshop],
        effective_limit: float,
        k: float,
        T: float
    ) -> SolverResult:
        """构建并求解 LP，返回 SolverResult"""

    def _build_model(
        self,
        workshops: List[Workshop],
        effective_limit: float,
        k: float,
        T: float
    ) -> Tuple[LpProblem, Dict[str, LpVariable]]:
        """构建 PuLP 模型，返回 (prob, r_vars)"""

    def _parse_result(
        self,
        prob: LpProblem,
        r_vars: Dict[str, LpVariable],
        workshops: List[Workshop]
    ) -> SolverResult:
        """解析求解结果，处理 Optimal/Infeasible/Timeout 三种状态"""
```

**LP 模型规范**：

```python
# 决策变量：r_i ∈ [r_min, r_max * k]
r = {ws.workshop_id: LpVariable(
         f"r_{ws.workshop_id}",
         lowBound=ws.min_discharge_rate,
         upBound=ws.max_discharge_rate * k)
     for ws in workshops}

# 目标：最大化加权总排放速率
prob += lpSum(ws.priority_weight * r[ws.workshop_id] for ws in workshops)

# 约束：总排放速率 ≤ effective_limit（已在 SchedulerService 预计算）
prob += lpSum(r[ws.workshop_id] for ws in workshops) <= effective_limit

# 求解参数
status = prob.solve(PULP_CBC_CMD(timeLimit=10, msg=0))
```

**状态判断**：
- `LpStatus[prob.status] == "Optimal"` → 提取 `value(r[id])`，四舍五入 4 位
- 其他状态 → `solver_status="Infeasible"` 或 `"Timeout"`，`rates` 全 0，`objective_value=None`

**验收**：构造 3 个 Workshop（min=5, max=20, weight=1/2/3），`effective_limit=40`, `k=1.0`, `T=0.5`，求解结果 `status="Optimal"`，总速率 ≤ 40。

---

### T18：AlertService（分级建议与告警构建）

**文件**：`backend/scheduler/alert_service.py`  
**职责**：生成停排建议记录，构建告警记录对象（只构建，不写库）

**实现要求**：
```python
class AlertService:
    def generate_stop_advisory(
        self,
        workshops: List[Workshop],
        tank_level: float,
        zone: str,           # "ALERT" or "EMERGENCY"
        schedule_id: str,
        schedule_time: datetime,
        T: float
    ) -> List[ScheduleResultRecord]:
        """为所有车间生成 allowed_rate=0, allowed_volume=0, solver_status=SKIPPED 的建议"""

    def build_alert_record(
        self,
        schedule_id: str,
        tank_level: float,
        level_ratio: float,
        zone: str,
        reason: str
    ) -> AlertRecord:
        """构建告警记录，告警级别：ALERT→2, EMERGENCY→3"""
```

**告警级别映射**：
```python
ALERT_LEVEL_MAP = {"ALERT": 2, "EMERGENCY": 3}
```
LP Infeasible / Timeout 告警：`level=2`，`zone="ALERT"`

**验收**：传入 2 个 Workshop，`generate_stop_advisory` 返回 2 条 `ScheduleResultRecord`，每条 `allowed_rate=0.0`，`solver_status="SKIPPED"`。

---

### T19：SchedulerService（调度主流程编排）

**文件**：`backend/scheduler/scheduler_service.py`  
**职责**：调度全流程编排，串联所有子模块，不包含业务计算逻辑

**实现要求**：
```python
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
        schedule_input_dao: ScheduleInputDAO,           # 调度输入快照 DAO
        schedule_input_workshop_dao: ScheduleInputWorkshopDAO,  # 调度输入车间快照 DAO
        pool: oracledb.ConnectionPool
    ) -> None: ...

    def run(self, tank_level: float) -> None:
        """主调度入口，执行完整 Step1~Step9 流程"""

    def _determine_zone(self, L: float, params: SolverParams) -> Tuple[str, float]:
        """返回 (zone, k)，zone ∈ {NORMAL, WARNING, ALERT, EMERGENCY}"""

    def _compute_k(self, L: float, params: SolverParams) -> float:
        """仅 WARNING 区间使用，线性插值计算弹性系数"""

    def _compute_derived(
        self,
        results: List[ScheduleResultRecord],
        L: float,
        params: SolverParams
    ) -> float:
        """计算预测液位 L_predicted = max(0.0, L + Σ(r_i*T) - C*T)"""

    def _write_all(
        self,
        conn,
        tank_record: TankStatusRecord,
        results: List[ScheduleResultRecord],
        schedule_input: ScheduleInputRecord,           # 调度输入快照
        input_workshops: List[ScheduleInputWorkshopRecord],  # 调度输入车间快照
        alert: Optional[AlertRecord]
    ) -> None:
        """事务写库：WW_TANK_STATUS → WW_SCHEDULE_RESULT → WW_SCHEDULE_INPUT → WW_SCHEDULE_INPUT_WORKSHOP → WW_ALERT_LOG"""
```

**区间判断逻辑（_determine_zone）**：
```
level_ratio = L / V
NORMAL    : level_ratio < WARNING_RATIO              → k = 1.0
WARNING   : WARNING_RATIO ≤ level_ratio < ALERT_RATIO
            k = 1 - (L - WARNING_RATIO*V) / (0.1*V) * (1 - MIN_RATE_RATIO)
            k = max(k, MIN_RATE_RATIO)
ALERT     : ALERT_RATIO ≤ level_ratio < EMERGENCY_RATIO → r_i=0
EMERGENCY : level_ratio ≥ EMERGENCY_RATIO                → r_i=0
```

**liquid level 校验逻辑（run 方法内）**：
```
L is None 或 L <= 0  → raise InvalidTankLevelError → 记录 ERROR，跳过本次调度
L > V               → L = V，按 EMERGENCY 处理，记录 ERROR
```

**effective_limit 预计算（Step 6a）**：
```python
capacity_limit  = (V * SAFE_RATIO - L) / T + C
process_limit   = C * PROCESS_BUFFER_RATIO
effective_limit = min(capacity_limit, process_limit)
# 若 effective_limit <= 0 → 跳过求解，生成全零建议，记录 WARNING
```

**事务写库顺序（_write_all）**：
1. `tank_dao.insert(conn, tank_record)`
2. `result_dao.batch_insert(conn, results)`
3. `schedule_input_dao.insert(conn, schedule_input)`
4. `schedule_input_workshop_dao.batch_insert(conn, input_workshops)`
5. `if alert: alert_dao.insert(conn, alert)`
6. `conn.commit()`
7. 异常 → `conn.rollback()` → 记录 ERROR → `raise DBWriteError`

**Step 9 完成日志**（INFO 级别，必须包含）：
```
[{schedule_id}] 调度完成 zone={zone} workshops={n} elapsed={ms}ms
```

**验收**：Mock 所有依赖后，传入合法液位，`run()` 不抛出异常，日志输出包含"调度完成"。

---

### T20：SchedulerTrigger（触发层）

**文件**：`backend/scheduler/trigger.py`  
**职责**：APScheduler 定时触发 + 对外暴露 `run_once()` 供 CLI 调用

**实现要求**：
```python
class SchedulerTrigger:
    def __init__(
        self,
        scheduler_svc: SchedulerService,
        config_svc: ConfigService,
        tank_dao: TankStatusDAO
    ) -> None: ...

    def start(self) -> None:
        """启动 APScheduler BackgroundScheduler，使用 IntervalTrigger"""

    def stop(self) -> None:
        """优雅停止调度器"""

    def restart(self) -> None:
        """
        热重载调度器：
        1. 刷新 ConfigService 缓存
        2. 从数据库读取 SCHEDULE_INTERVAL_MIN 和 MANUAL_LEVEL_STALE_THRESHOLD
        3. 若周期变更，停止旧定时任务并启动新定时任务
        4. 若周期不变，仅更新内部阈值配置
        """

    def get_interval_min(self) -> int:
        """返回当前调度周期（分钟）"""

    def get_stale_threshold(self) -> int:
        """返回当前液位超期阈值（调度周期倍数）"""

    def run_once(self) -> None:
        """
        APScheduler 回调：
        1. 从 DB 读取最新 MANUAL 液位（TankStatusDAO.get_latest_manual_level）
        2. 检查时效（超过 stale_threshold × T 则记录 WARNING，不中止）
        3. 调用 SchedulerService.run(tank_level)
        """
```

**APScheduler 配置**：
```python
# 调度周期从数据库动态读取
interval_minutes = self._interval_min  # 从 ConfigService 获取

scheduler = BackgroundScheduler(
    executors={'default': ThreadPoolExecutor(max_workers=1)}
)
scheduler.add_job(
    func=self.run_once,
    trigger=IntervalTrigger(minutes=interval_minutes),
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60
)
```

**验收**：`start()` 不抛异常，调度器状态为 running，`stop()` 后状态变为 stopped。`restart()` 能正确热重载配置，`get_interval_min()` 和 `get_stale_threshold()` 返回数据库配置值。

---

### T21：调度输入快照数据类

**文件**：`backend/model/schedule_input.py`

```python
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

**验收**：实例化两个数据类，字段赋值正确。

---

### T22：调度输入快照 DAO

**文件**：`backend/dao/schedule_input_dao.py`

```python
class ScheduleInputDAO(BaseDAO):
    def insert(self, conn, record: ScheduleInputRecord) -> None:
        """写入调度输入系统级快照，主键使用 SEQ_SCHEDULE_INPUT.NEXTVAL"""
```

**INSERT SQL**：
```sql
INSERT INTO WW_SCHEDULE_INPUT
    (INPUT_ID, SCHEDULE_ID, SCHEDULE_TIME, TANK_CAPACITY, PROCESS_CAPACITY,
     SCHEDULE_INTERVAL_MIN, SAFE_RATIO, WARNING_RATIO, ALERT_RATIO, EMERGENCY_RATIO,
     MIN_RATE_RATIO, PROCESS_BUFFER_RATIO, TANK_LEVEL, LEVEL_RATIO, ZONE,
     ELASTIC_K, CAPACITY_LIMIT, PROCESS_LIMIT, EFFECTIVE_LIMIT, WORKSHOP_COUNT)
VALUES
    (SEQ_SCHEDULE_INPUT.NEXTVAL, :schedule_id, :schedule_time, :tank_capacity, :process_capacity,
     :schedule_interval_min, :safe_ratio, :warning_ratio, :alert_ratio, :emergency_ratio,
     :min_rate_ratio, :process_buffer_ratio, :tank_level, :level_ratio, :zone,
     :elastic_k, :capacity_limit, :process_limit, :effective_limit, :workshop_count)
```

**文件**：`backend/dao/schedule_input_workshop_dao.py`

```python
class ScheduleInputWorkshopDAO(BaseDAO):
    def batch_insert(self, conn, records: List[ScheduleInputWorkshopRecord]) -> None:
        """批量写入调度输入车间级快照，主键使用 SEQ_SCHEDULE_INPUT_WORKSHOP.NEXTVAL"""
```

**INSERT SQL（executemany）**：
```sql
INSERT INTO WW_SCHEDULE_INPUT_WORKSHOP
    (INPUT_WORKSHOP_ID, SCHEDULE_ID, WORKSHOP_ID, WORKSHOP_NAME,
     MAX_DISCHARGE_RATE, MIN_DISCHARGE_RATE, PRIORITY_WEIGHT, ELASTIC_MAX_RATE, CREATE_TIME)
VALUES
    (SEQ_SCHEDULE_INPUT_WORKSHOP.NEXTVAL, :schedule_id, :workshop_id, :workshop_name,
     :max_discharge_rate, :min_discharge_rate, :priority_weight, :elastic_max_rate, :create_time)
```

**验收**：传入 1 条 `ScheduleInputRecord` 和 3 条 `ScheduleInputWorkshopRecord`，事务写入后表中新增对应记录。

---

### T23：日志模块验证（验证T9的实现）

**文件**：`backend/utils/logger.py`

**验证要求**：
1. 确认使用 `TimedRotatingFileHandler` 按天滚动
2. 确认日志文件名格式：`scheduler-YYYY-MM-DD.log`，`error-YYYY-MM-DD.log`
3. 确认配置项 `LOG_RETENTION_DAYS`（默认 180）生效
4. 确认首次调用 `get_logger()` 时，清理超过 `LOG_RETENTION_DAYS` 天的历史日志文件

**实现要点**：
```python
# settings.py 新增
LOG_RETENTION_DAYS: int = 180

# logger.py 中
def _cleanup_old_logs() -> None:
    """清理超期日志文件"""
    cutoff_time = time.time() - LOG_RETENTION_DAYS * 24 * 3600
    for log_file in Path(LOG_DIR).glob("*.log*"):
        if log_file.stat().st_mtime < cutoff_time:
            log_file.unlink()

def get_logger(name: str) -> logging.Logger:
    # 首次调用时执行清理
    _cleanup_old_logs()
    # ... 原有逻辑，改用 TimedRotatingFileHandler(when='midnight')
```

**验收**：
- 运行程序，检查 `logs/` 目录下生成 `scheduler-YYYY-MM-DD.log` 和 `error-YYYY-MM-DD.log`
- 修改系统时间或手动创建旧文件，验证超期日志被自动清理

---

### T24：算法约束条件日志输出（增强T17/T19）

**文件**：`backend/scheduler/scheduler_service.py` 和 `backend/scheduler/solver_service.py`

**修改要求**：
1. 在 `SchedulerService` 中，计算约束后输出 DEBUG 日志：
   - 容量约束计算过程和结果
   - 处理能力约束计算过程和结果
   - effective_limit 取值
   - 预警区间输出弹性系数 k 的计算过程
2. 在 `SolverService` 中，输出各车间的约束边界值

**日志格式示例**：
```
[DEBUG] [schedule_id] 约束计算: L=420.0, V=500.0, T=0.5, C=60.0
[DEBUG] [schedule_id] 容量约束: (V*SAFE_RATIO-L)/T+C = (500.0*0.85-420.0)/0.5+60.0 = 70.0000
[DEBUG] [schedule_id] 处理能力约束: C*PROCESS_BUFFER_RATIO = 60.0*1.2 = 72.0000
[DEBUG] [schedule_id] 生效约束: effective_limit = min(70.0000, 72.0000) = 70.0000
[DEBUG] [schedule_id] 弹性系数: k = 1 - (420.0-400.0)/(0.1*500.0)*(1-0.3) = 0.7200
```

**验收**：运行一次调度，检查 `scheduler.log` 中包含上述 DEBUG 级别的约束计算日志。

---

### T25：SchedulerService 集成调度输入快照写入（修改T19）

**文件**：`backend/scheduler/scheduler_service.py`

**修改要求**：
1. 构造函数新增 `ScheduleInputDAO` 和 `ScheduleInputWorkshopDAO` 依赖
2. 在 `_write_all()` 方法中，新增调度输入快照写入：
   - 构建 `ScheduleInputRecord`（包含所有约束计算值）
   - 构建 `List[ScheduleInputWorkshopRecord]`（每个车间一条）
   - 在事务中一并写入

**修改 `_write_all` 签名**：
```python
def _write_all(
    self,
    conn,
    tank_record: TankStatusRecord,
    results: List[ScheduleResultRecord],
    schedule_input: ScheduleInputRecord,                    # 新增
    input_workshops: List[ScheduleInputWorkshopRecord],    # 新增
    alert: Optional[AlertRecord]
) -> None:
    """事务写库：WW_TANK_STATUS → WW_SCHEDULE_RESULT → WW_SCHEDULE_INPUT → WW_SCHEDULE_INPUT_WORKSHOP → WW_ALERT_LOG"""
```

**验收**：运行一次完整调度，检查 `WW_SCHEDULE_INPUT` 和 `WW_SCHEDULE_INPUT_WORKSHOP` 表中新增对应记录。

------

### T26：程序入口

**文件**：`backend/main.py`  
**职责**：依赖注入组装 + 定时启动 / CLI 手动触发

**实现要求**：

```python
# CLI 参数
# python -m backend.main                          # 启动定时调度（在 waste_water/ 根目录执行）
# python -m backend.main --manual --level 300.0   # 手动触发一次

def build_dependencies() -> SchedulerTrigger:
    """完成所有依赖注入：初始化 oracledb Thick Mode → 创建连接池 → 实例化 DAO/Service/Trigger"""

def run_scheduled() -> None:
    """启动定时调度，注册 SIGINT/SIGTERM 优雅退出"""

def run_manual(tank_level: float) -> None:
    """手动触发一次调度，完成后退出"""

if __name__ == "__main__":
    # argparse 解析 --manual --level
    ...
```

**依赖注入顺序**（严格按此顺序）：

1. `oracledb.init_oracle_client(lib_dir=ORACLE_CLIENT_LIB_DIR)`
2. `pool = oracledb.create_pool(...)`
3. 实例化各 DAO（传入 pool）
4. 实例化各 Service（传入 DAO）
5. 实例化 `SchedulerTrigger`

**优雅退出**：捕获 `KeyboardInterrupt`，调用 `trigger.stop()`，关闭连接池 `pool.close()`

**验收**：`python -m backend.main --manual --level 300.0` 执行一次调度后程序正常退出。

---

## Phase 2 — 迭代增强（MVP 稳定后实施）

> 以下迭代规划与 PRD v1.5 第9.2节保持一致

| 编号 | 功能 | 预留接口 | 目标版本 |
|------|------|----------|---------|
| P2-1 | 传感器自动采集液位 | `WW_TANK_STATUS.INPUT_TYPE` 已预留 `AUTO` 值 | v1.1 |
| P2-2 | 调度结果查询 REST API | `trigger.run_once()` 可被 FastAPI 路由直接调用 | v1.1 |
| P2-3 | 移动端告警推送 | 通过短信/企业微信推送告警通知 | v1.2 |
| P2-4 | 前端可视化界面 | 数据已完整入库，直接对接前端 | v2.0 |
| P2-5 | 液位预测模型 | 基于历史数据预测未来液位，提前干预 | v2.0 |
| P2-6 | 多储罐支持 | 扩展支持多个储罐的联合调度 | v2.0 |
| P2-7 | 调度效果分析报表 | 定期生成调度效果统计报告 | v2.0 |
| P2-8 | AI 智能调度优化 | 引入强化学习或机器学习优化调度策略 | v3.0 |

---

## 验收矩阵（MVP 完成标准）

| 验收项 | 验收方法 |
|--------|---------|
| T0 Oracle 连通 | `backend/tests/test_oracle_conn.py` 全部 `[OK]` |
| 正常区间调度 | 手动传入低液位，`WW_SCHEDULE_RESULT` 新增记录，`solver_status=Optimal` |
| 预警区间弹性 | 传入 WARNING 区间液位，各车间 `allowed_rate < max_discharge_rate` |
| ALERT/EMERGENCY 停排 | 传入高液位，所有车间 `allowed_rate=0`，`WW_ALERT_LOG` 新增记录 |
| LP Infeasible 处理 | 配置极小容量触发 Infeasible，全零结果入库 + 告警入库 |
| 事务回滚 | Mock DB 写入抛异常，`WW_TANK_STATUS` / `WW_SCHEDULE_RESULT` 均无残留数据 |
| 液位非法 | 传入 `L=0` / `L=None`，调度跳过，无任何 DB 写入 |
| 日志完整性 | `logs/scheduler.log` 含调度开始/完成记录，`logs/error.log` 仅含 ERROR |
| CLI 手动触发 | `python -m backend.main --manual --level 300.0` 正常执行并退出 |
| 定时调度启动 | `python -m backend.main` 启动后 30 分钟内自动执行一次调度 |

---

*文档结束*
