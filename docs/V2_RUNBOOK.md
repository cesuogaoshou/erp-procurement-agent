# V2 独立模拟数据运行说明

版本 `simulated_procurement_v2_20261029.1`，自主生成的教学模拟数据，不是真实企业或公开采购数据。设计见 `V2_DATA_DESIGN_20261029.md`；验收和失败见 `V2_ACCEPTANCE_20261030.md`。

## 数据与离线复现

在项目根目录运行（Python 3.13、现有 requirements.txt）：

```powershell
python -m scripts.generate_v2_data
python -m scripts.generate_v2_data --validate-only
python -m scripts.compare_v1_v2
python -m backend.evaluation.run_v2_eval
python -m pytest backend/tests/test_v2_dataset.py -q
```

生成器只写 `data/v2/raw/`。如需独立重生成对照，用 `--output <新目录>`；同版本所有文件逐字节一致。不运行会写回 `data/raw/` 的旧 `scripts.export_seed_data` 或 `backend.evaluation.run_supplier_eval` main。V1 回归只调用原函数并将结果另存到本轮证据目录。

V2 对 V1 的五个文件逐字节复制：materials、suppliers、demand_history、inventory_snapshots、data_splits。供应商原表没有单独的编码列，沿用原ID作为稳定标识，不新增或重排名称。供应商报价、交期、容量、MOQ、包装和履约表现由 `data/v2/design.json` 决定。独立随机源仅用于历史参考价格；不参与推荐排序。

`manifest.json` 保存固定版本/种子、设计冻结日期、观察日期、完整参数、生成器/设计散列、V1全部源文件散列、V2文件行数/散列和主键。日期是固定发布与观察口径，不伪装成每次命令运行的时间。实际执行日期保存在验收报告。

金额和数量最多两位小数，和数据库 Numeric(12,2) 对齐。报价、MOQ、包装和容量必须为正；交期1–90天；容量容纳按包装取整后的最小起订量；承诺交付和检验分母为正，准时/合格不超过分母，投诉不超过交付数或不合格件数。校验还检查唯一键、外键、完整100种供应商物料关系、文件篡改、固定标签与五个不变项。

## 独立 MySQL 导入

仅接受明确的 `V2_DATABASE_URL`，目标库必须**恰为** `erp_procurement_demo_v2`，驱动限定 `mysql+pymysql`，连接串 query 仅允许 `charset=utf8mb4`，拒绝 database/db/host 等目标覆盖。连接后还核对 `SELECT DATABASE()`。

已有账号最初仅有原库权限，管理员已完成 V2 建库及授权。本轮成功导入后已有业务验收数据，**再次导入会拒绝非空库，这是正常保护行为**。没有 reset、force 或覆盖选项。

```powershell
# 在本地安全配置中提供 V2_DATABASE_URL，不打印其值，不写入原 .env。
python -m backend.app.db.import_v2_data
# 仅在账号有建库权限且确需首次建库时，显式附加 --create-database。
```

若要复用当前 shell 中已配置的原账号凭证，可用以下方式仅在子进程内换库，不显示连接串，也不改变当前 shell 的 DATABASE_URL：

```powershell
@'
import os, subprocess, sys
from sqlalchemy.engine import make_url
from backend.app.config import load_project_env
load_project_env()
env = os.environ.copy()
env['V2_DATABASE_URL'] = make_url(env['DATABASE_URL']).set(
    database='erp_procurement_demo_v2'
).render_as_string(hide_password=False)
subprocess.run([sys.executable, '-m', 'scripts.start_v2_demo'], env=env, check=True)
'@ | python -
```

首次导入时，将最后一行的模块换为 `backend.app.db.import_v2_data`。导入器先离线校验，再在目标库获取命名锁、检查所有业务表为空、迁移到 head、事务插入并核对实际参考数据。失败回滚数据行；MySQL建库/建表DDL不能事务回滚，失败可留下空表。异常仅输出错误类别或安全业务码，不输出密码或连接串。建库权限不足时保留离线结果并报告未导入，不能使用原库替代。

## 页面与隔离启动

```powershell
# 已提供 V2_DATABASE_URL 时：
python -m scripts.start_v2_demo
```

- V2页面：<http://127.0.0.1:5176>。
- V2 API：<http://127.0.0.1:8002>；`/environment` 返回V2版本和库名。
- 页面显著显示“V2 · 自主模拟数据 · 独立演示库”。
- 原8000/5173服务继续保留，启动器不切换原服务、不初始化数据、不修改.env。启动先拒绝已占用端口，绑定loopback；后端核对实际库名及六张参考表内容，空库或错误数据不能伪装成就绪。
- 现有演示账号：采购员buyer、审批员approver；密码沿用项目原演示账号约定。真实模型沿用本地OPENAI环境配置，未使用Mock冒充真实调用。
- PID、地址和独立日志在 `reports/generated/v2_acceptance_20261029/services.json` 及 `v2-backend.log`、`v2-frontend.log`。停止时只停止核对过命令行的这两个V2进程；不要停原8000/5173服务。

## 评测与验收复现

```powershell
python -m backend.evaluation.run_v2_eval --mysql --output reports/generated/<新目录>/supplier_eval_mysql.json
python -m scripts.accept_v2_business --output reports/generated/<新目录>
python -m pytest backend/tests -q
# 真实MySQL检查须将子进程DATABASE_URL明确指向V2，并设置RUN_MYSQL_INTEGRATION=1；
# V2导入保护测试还要求同值V2_DATABASE_URL。原有6项检查会新增V2演示订单。
python -m pytest backend/tests/test_mysql_integration.py backend/tests/test_v2_mysql_integration.py -q
npm --prefix frontend run build
```

真实模型验收脚本会创建V2业务记录，拒绝覆盖已有证据目录。模型结果可能波动，不能覆盖本次失败。离线标签50正例/30拒绝例，Top-1、Top-3、拒绝正确性分别统计；不将不同数据集成绩差异称作算法提升。MySQL保护测试的整表快照比较应在无并发业务写入时执行。

本轮V1全库只读保护核对：`python -m scripts.verify_v2_protection`。它使用本轮事前快照，对原库所有表内容及309个已有文件复核；仅允许前端V2标识/代理配置的既定改动。不要用该命令创建基线或初始化数据库。
