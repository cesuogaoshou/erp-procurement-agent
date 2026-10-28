# 数据库快照与课程交付包

本目录按用户要求于 **2026-10-29** 发布到 GitHub。只包含明确选择的快照和交付文件；不包含 `.env`、API 密钥、数据库连接密码、MySQL 系统账号/授权或运行缓存。

## 数据库

路径：`database/2026-10-29/`。

| 文件 | 内容 |
| --- | --- |
| `erp_procurement.sql` | 当前本地 MySQL 项目库的结构和数据，使用 `mysqldump --single-transaction` 导出；包含采购订单、审批、Agent 执行与工具记录。 |
| `erp_demo.sqlite` | 本地 SQLite 演示库的在线备份，含模拟基础数据。 |
| `erp_dev.sqlite` | 本地 SQLite 开发库的在线备份，保留已有演示订单与执行记录。 |
| `MANIFEST.json` | 导出时间、来源代码版本、各表记录数、SHA-256 和实际验证结果。 |

未收录 `tmp_*.sqlite` 临时迁移检查库和空文件。两个 SQLite 文件保留原有结构，不代表当前 MySQL 集成状态；开发库的 Alembic 版本表没有记录。对其执行版本相关操作前应先检查结构和迁移状态。

MySQL 导出完成且所有 13 张表的建表语句、INSERT 记录数均已核对；两份 SQLite 的 `PRAGMA integrity_check` 均为 `ok`。当前 MySQL 账号没有创建隔离数据库的权限，因此未完成 MySQL 隔离恢复测试，也未调整权限或修改源库。

### 恢复 MySQL

使用 MySQL 8.4 客户端连接自行准备的**空数据库**。SQL 包含 `DROP TABLE` / `CREATE TABLE`，会替换目标库中的同名项目表；导入时应选择新的专用数据库。导出文件不包含 `CREATE DATABASE` 或 `USE`，也不包含连接凭据。

在 MySQL 客户端中先选择新库，再执行：

```sql
USE erp_restore_demo;
SOURCE D:/demo/erp/artifacts/database/2026-10-29/erp_procurement.sql;
```

`erp_restore_demo` 须预先由有权限的账号创建；路径按实际克隆位置调整。随后在本地 `.env` 中设置自己的 `DATABASE_URL` 和认证/模型配置。不要将这些值提交到 GitHub。

### 使用 SQLite

将所需快照复制到仓库之外或一个新的本地运行文件，再将 `DATABASE_URL` 指向该副本，例如 `sqlite+pysqlite:///./erp_restored_demo.sqlite`。保留本目录快照作为固定历史证据。

## 课程交付包

文件：`delivery/erp-course-delivery-2026-10-13.zip`，约 4.6 MB。

- 来自本地 **2026-10-13** 的既有交付目录，参考代码版本为 `77a09a8`；本次仅打包上传，没有重新生成 Word 或替换原交付物。
- 包含 Word 报告、PDF、9 页渲染图、源码与模拟数据、评测证据、截图、原交付清单及敏感信息检查记录，共 147 个文件。
- 移除了 LibreOffice 临时 profile、依赖缓存等 70 个文件。
- 个人姓名、学号和班级仍为待填写占位符。
- **不包含 2026-10-28 尚未提交的修复代码**，也不是本次 MySQL 快照日期对应的重新验收版本。数据库快照与历史交付包应分别理解。
- `delivery/MANIFEST.json` 记录压缩包及每个成员的 SHA-256、原始日期和版本边界。

本次发布没有提交工作区中其他尚未提交的后端、前端或验收文档改动。
