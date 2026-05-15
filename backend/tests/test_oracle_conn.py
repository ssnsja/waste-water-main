"""
T0-1：Oracle 连接可用性测试
验证 Python 3.13 + python-oracledb Thick Mode 能否连通本地 Oracle 11g

执行方式（在 waste_water/ 根目录下）：python backend/tests/test_oracle_conn.py
"""

import sys

# ── Oracle Instant Client 路径（按实际环境修改） ──
ORACLE_CLIENT_LIB_DIR = r"D:\oracle11\product\11.2.0\dbhome_1\bin"

# ── 数据库连接参数（按实际环境修改） ──
DB_USER = "WASTE_WATER"
DB_PASSWORD = "123456"
DB_DSN = "localhost:1521/orcl"


def main() -> None:
    pool = None

    # ────────────────────────────────────────────
    # Step 1：验证 oracledb 可正常导入
    # ────────────────────────────────────────────
    try:
        import oracledb
        print(f"[OK] oracledb 导入成功，版本: {oracledb.__version__}")
    except ImportError as e:
        print(f"[FAIL] 原因: oracledb 导入失败 - {e}")
        sys.exit(1)

    # ────────────────────────────────────────────
    # Step 2：Thick Mode 初始化
    # ────────────────────────────────────────────
    try:
        oracledb.init_oracle_client(lib_dir=ORACLE_CLIENT_LIB_DIR)
        print("[OK] Thick Mode 初始化成功")
    except Exception as e:
        print(f"[FAIL] 原因: Thick Mode 初始化失败 - {e}")
        sys.exit(1)

    # ────────────────────────────────────────────
    # Step 3：创建连接池
    # ────────────────────────────────────────────
    try:
        pool = oracledb.create_pool(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=DB_DSN,
            min=1,
            max=2,
            increment=1,
            getmode=oracledb.POOL_GETMODE_WAIT,
        )
        print("[OK] 连接池创建成功")
    except Exception as e:
        print(f"[FAIL] 原因: 连接池创建失败 - {e}")
        sys.exit(1)

    # ────────────────────────────────────────────
    # Step 4：从连接池获取连接，执行 SELECT 1 FROM DUAL
    # ────────────────────────────────────────────
    conn = None
    try:
        conn = pool.acquire()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM DUAL")
            result = cursor.fetchall()
            if result == [(1,)]:
                print("[OK] SELECT 1 FROM DUAL 执行成功")
            else:
                print(f"[FAIL] 原因: SELECT 1 FROM DUAL 返回值异常 - {result}")
                sys.exit(1)
    except Exception as e:
        print(f"[FAIL] 原因: SELECT 1 FROM DUAL 执行失败 - {e}")
        sys.exit(1)

    # ────────────────────────────────────────────
    # Step 5：验证 WW_SYSTEM_CONFIG 表可访问
    # ────────────────────────────────────────────
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM WW_SYSTEM_CONFIG WHERE ROWNUM = 1"
            )
            row = cursor.fetchall()
            if row:
                print("[OK] WW_SYSTEM_CONFIG 表可访问")
            else:
                print("[FAIL] 原因: WW_SYSTEM_CONFIG 表无数据")
                sys.exit(1)
    except Exception as e:
        print(f"[FAIL] 原因: WW_SYSTEM_CONFIG 表访问失败 - {e}")
        sys.exit(1)

    # ────────────────────────────────────────────
    # Step 6：释放连接并关闭连接池
    # ────────────────────────────────────────────
    try:
        if conn is not None:
            pool.release(conn)
        pool.close()
        print("[OK] 连接资源释放完毕")
    except Exception as e:
        print(f"[FAIL] 原因: 连接资源释放失败 - {e}")
        sys.exit(1)

    # ────────────────────────────────────────────
    # 全部通过
    # ────────────────────────────────────────────
    print("--- 环境验证通过，可以开始开发 ---")


if __name__ == "__main__":
    main()
