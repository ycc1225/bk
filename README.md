# job-backupend

基于蓝鲸 PaaS 平台的文件备份管理后端服务，对接蓝鲸 CMDB 和 JOB 平台，提供主机文件搜索与备份功能。

技术栈：Django 3.2 + DRF + Celery + MySQL + Redis，部署于蓝鲸 PaaS V3。

## 功能

- **CMDB 数据同步**：从蓝鲸 CMDB 同步业务、集群、模块拓扑数据到本地，支持定时和手动触发
- **主机查询**：按业务/集群/模块层级查询主机列表和详情
- **文件搜索**：指定主机、路径、后缀，通过 JOB 平台搜索文件
- **文件备份**：将主机上的文件备份到指定路径，支持异步执行和状态跟踪
- **权限管理**：四级角色体系 Admin > Ops > Dev = Bot，读写权限分离
- **监控埋点**：API 请求统计、Prometheus 指标推送、OpenTelemetry 链路追踪

## API 接口

基础路径：`/api/`，完整文档启动后访问 `/api/swagger/`。

### CMDB 相关

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/cmdb/biz-info/` | 业务列表（支持分页、搜索） |
| GET | `/api/cmdb/set-info/?bk_biz_id=2` | 集群列表（按业务过滤） |
| GET | `/api/cmdb/module-info/?bk_biz_id=2&bk_set_id=3` | 模块列表（按业务和集群过滤） |
| GET | `/api/cmdb/hosts/?bk_biz_id=2` | 主机列表（必须指定业务ID） |
| GET | `/api/cmdb/host-detail/?bk_host_id=1001` | 主机详情 |
| GET | `/api/cmdb/sync/` | 手动触发 CMDB 数据同步 |

### JOB 相关

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/job/search-file/?host_id_list=1001,1002&search_path=/tmp&suffix=.log` | 搜索文件 |
| POST | `/api/job/backup-file/` | 备份文件（Body: `{"host_list": [1001], "search_path": "/tmp", "suffix": ".log", "backup_path": "/project/backup"}`） |
| GET | `/api/job/backup-jobs/` | 备份作业列表 |
| GET | `/api/job/backup-job-detail/{id}/` | 备份作业详情（含每台主机的文件记录） |

### 权限管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/permission/user-roles/` | 用户角色列表 |
| POST | `/api/permission/user-roles/` | 创建用户角色 |
| PUT | `/api/permission/user-roles/{id}/` | 修改用户角色 |
| DELETE | `/api/permission/user-roles/{id}/` | 删除用户角色 |

### 其他

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/cmdb/api-stats/` | API 调用统计 |
| GET | `/api/health/` | 健康检查 |

## 响应格式

```json
// 成功
{"result": true, "data": { ... }}

// 成功（分页）
{"result": true, "data": { ... }, "pagination": {"current": 1, "count": 100, "limit": 10}}

// 失败
{"result": false, "message": "错误信息", "code": "错误码"}
```

## 约束条件

- 备份路径必须以 `/project` 开头
- 允许的文件后缀：`log`、`txt`、`csv`、`json`、`bak`
- 分页参数：`page`（默认1）、`page_size`（默认10，最大100）

## 权限说明

| 角色 | 级别 | 说明 |
|------|------|------|
| Admin | 100 | 全部权限，Django superuser/staff 自动获得 |
| Ops | 50 | 读写权限 |
| Dev | 10 | 默认角色，只读权限 |
| Bot | 10 | 与 Dev 同级，用于程序调用 |

未注册用户首次访问自动分配 Dev 角色。写操作（POST/PUT/DELETE）默认需要 Ops 及以上权限。

## 部署

项目通过 `app_desc.yaml` 描述，部署为 3 个进程：

- **web**：Gunicorn，2 worker x 2 threads，端口 5000
- **beat**：Celery Beat 定时调度
- **worker**：Celery Worker，prefork 模式，2 并发

发布前自动执行数据库迁移（`python manage.py migrate --no-input`）。

## 项目结构

```
job-backupend/
├── config/               # 环境配置（default/dev/stag/prod）
├── core/                 # 中间件（API埋点、TraceId注入）
├── home_application/     # 核心业务
│   ├── views/            # 视图层
│   ├── services/         # 业务逻辑层
│   ├── tasks/            # Celery 异步任务
│   ├── serializers/      # 序列化器
│   ├── utils/            # 工具类
│   ├── models.py         # 数据模型
│   ├── permission.py     # 权限控制
│   └── constants.py      # 常量配置
├── blueking/             # 蓝鲸 SDK
└── app_desc.yaml         # 部署描述
```