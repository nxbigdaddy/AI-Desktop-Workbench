# 10 API 与事件协议设计

> 状态：draft  
> 风格：REST/JSON + SSE 事件流 + 异步任务  
> 基础路径：`/api/v1`

## 1. 目标

- 为桌面端、管理后台和连接器提供稳定契约；
- 明确认证、授权、幂等、分页、错误、取消和版本；
- 支持模型流和任务事件；
- 避免客户端依赖内部 ORM 或第三方响应；
- 支持逐步升级和兼容窗口。

## 2. 协议约定

- HTTPS；
- JSON 使用 UTF-8；
- 时间为 ISO 8601 UTC；
- ID 为不透明字符串；
- 金额和高精度计量以字符串传输，例如 `"12.3400"`；
- Boolean 使用 JSON true/false；
- 未知响应字段客户端应忽略；
- 未知枚举客户端应显示“未知状态”并保持安全默认；
- 上传大文件不使用 Base64 JSON；
- API Schema 生成 OpenAPI 并进入版本库/制品。

## 3. 通用请求头

| Header | 必需 | 说明 |
|---|---:|---|
| Authorization | 受保护 API | `Bearer <access-token>` |
| X-Request-ID | 建议 | 客户端生成请求 ID |
| Idempotency-Key | 写 API | 幂等键 |
| X-Device-ID | 桌面端 | 已注册设备 ID |
| X-Client-Version | 桌面端 | 语义版本 |
| X-API-Version | 可选 | 细粒度协商时使用 |
| traceparent | 建议 | W3C Trace Context |
| If-Match | 更新 | 资源版本/ETag |

服务端不能信任客户端 Header 中的 user_id/department_id 作为身份来源。

## 4. 通用响应

成功单资源：

```json
{
  "data": {
    "id": "...",
    "version": 3
  },
  "meta": {
    "request_id": "req_...",
    "server_time": "2026-08-07T17:14:00Z"
  }
}
```

列表：

```json
{
  "data": [{"id": "..."}],
  "page": {
    "next_cursor": "opaque...",
    "has_more": true,
    "limit": 50
  },
  "meta": {"request_id": "req_..."}
}
```

## 5. 分页、筛选和排序

- 大列表优先 cursor pagination；
- 管理后台固定小表可使用 page/page_size，但接口要明确；
- 默认 limit 20/50，最大值由资源决定；
- cursor 不透明、有签名/校验、短期有效；
- sort 使用白名单字段；
- filter 使用显式参数，禁止客户端传任意 SQL 表达式；
- 返回实际应用的筛选和时间范围（审计导出尤其需要）。

## 6. 幂等

### 6.1 必须使用的操作

- 创建任务；
- 创建上传事务/提交上传；
- 发送邮件；
- 执行业务写操作；
- 创建额度预留；
- 插件发布/撤回；
- 客户端版本发布；
- 审计导出。

### 6.2 行为

- 幂等作用域为调用者 + endpoint + key；
- 服务端保存 request body digest；
- 同 key 同 body 返回首次结果；
- 同 key 不同 body 返回 `409 IDEMPOTENCY_CONFLICT`；
- 处理中重复请求返回当前 operation/task；
- 保存期限按副作用风险设置。

## 7. 乐观并发

更新请求：

```http
PATCH /api/v1/admin/policies/pol_123
If-Match: "7"
```

版本不一致返回 412，包含当前版本摘要。客户端必须刷新、比较，不自动覆盖。

## 8. 错误格式

```json
{
  "error": {
    "code": "QUOTA_HARD_LIMIT_EXCEEDED",
    "message": "本月深度推理额度已用完",
    "details": {
      "scope": "user",
      "reset_at": "2026-09-01T00:00:00+08:00"
    },
    "retryable": false,
    "help_action": "request_quota"
  },
  "meta": {
    "request_id": "req_...",
    "trace_id": "..."
  }
}
```

`message` 可面向用户；内部堆栈只进受控日志。

## 9. HTTP 状态与错误码

| HTTP | 场景 |
|---:|---|
| 400 | Schema/业务输入无效 |
| 401 | 未登录、令牌失效 |
| 403 | 已认证但无权限/数据边界不允许 |
| 404 | 资源不存在或为避免枚举而隐藏 |
| 409 | 幂等/状态冲突 |
| 412 | If-Match 版本冲突 |
| 413 | 文件/请求过大 |
| 422 | 语义校验失败 |
| 423 | 资源/任务锁定 |
| 429 | 限流/并发限制 |
| 500 | 未分类服务端错误 |
| 502/503/504 | 上游/依赖不可用或超时 |

通用错误码：

- `AUTH_REQUIRED`
- `SESSION_IDLE_EXPIRED`
- `SESSION_REVOKED`
- `DEVICE_REVOKED`
- `CLIENT_UPDATE_REQUIRED`
- `PERMISSION_DENIED`
- `APPROVAL_REQUIRED`
- `DATA_BOUNDARY_DENIED`
- `VALIDATION_FAILED`
- `RESOURCE_VERSION_CONFLICT`
- `IDEMPOTENCY_CONFLICT`
- `RATE_LIMITED`
- `DEPENDENCY_UNAVAILABLE`
- `INTERNAL_ERROR`

## 10. 身份 API

### 10.1 创建登录事务

`POST /auth/login-transactions`

请求：

```json
{
  "device": {
    "install_id": "...",
    "name": "ZhangSan-PC",
    "os": "Windows",
    "os_version": "...",
    "client_version": "0.1.0"
  },
  "client_nonce": "...",
  "callback_modes": ["poll", "deep_link"]
}
```

响应：transaction_id、qr_content/qr_url、expires_at、poll_interval。

### 10.2 查询事务

`GET /auth/login-transactions/{id}`

状态：pending/scanned/approved/denied/expired/consumed。

### 10.3 交换登录 Grant

`POST /auth/login-transactions/{id}/exchange`

返回 access token、refresh secret、用户摘要、设备、策略版本。Refresh secret 只在本次响应返回。

### 10.4 刷新与登出

- `POST /auth/sessions/refresh`
- `POST /auth/sessions/logout`
- `GET /me/sessions`
- `DELETE /me/sessions/{session_id}`

## 11. Bootstrap API

客户端登录后调用：

`GET /client/bootstrap`

返回：

- 用户和组织摘要；
- 有效模块/插件；
- 逻辑模型目录；
- 策略快照版本和过期；
- 用量摘要；
- 服务端/Runner/插件 API 版本；
- 客户端最低版本和更新策略；
- Feature Flags；
- 通知未读数。

响应可使用 ETag，敏感策略只返回客户端需要的约束。

## 12. 会话与消息 API

- `GET /conversations`
- `POST /conversations`
- `GET /conversations/{id}`
- `PATCH /conversations/{id}`
- `DELETE /conversations/{id}`
- `GET /conversations/{id}/messages`
- `POST /conversations/{id}/responses`
- `POST /responses/{request_id}/cancel`
- `POST /messages/{id}/feedback`
- `POST /conversations/{id}/archive`
- `POST /conversations/{id}/export`

删除按保留策略可能是软删除/用户不可见，不承诺立即清除审计和法定留存数据。

## 13. AI SSE

请求：`POST /conversations/{id}/responses`，响应 `text/event-stream`。

```text
id: evt_001
event: response.created
data: {"request_id":"req_...","logical_model":"deep-reasoning"}

id: evt_002
event: response.output_text.delta
data: {"message_id":"msg_...","delta":"正在分析"}

id: evt_003
event: response.completed
data: {"message_id":"msg_...","usage_status":"final"}
```

规则：

- heartbeat 事件不包含业务数据；
- event ID 单请求递增；
- final/failed/cancelled 三选一；
- 客户端断线可查询 `GET /responses/{id}` 获取权威状态；
- SSE 不承诺永久重放，保留窗口要明确。

## 14. 文件 API

- `POST /files/upload-transactions`
- `POST /files/upload-transactions/{id}/complete`
- `GET /files/{id}`
- `GET /files/{id}/scan-status`
- `DELETE /files/{id}`
- `POST /artifacts/{id}/download-ticket`

上传事务返回服务端代理或对象存储短期凭据；下载 ticket 短期、单资源、记录审计。

## 15. Agent API

- `POST /tasks`
- `GET /tasks`
- `GET /tasks/{id}`
- `GET /tasks/{id}/steps`
- `GET /tasks/{id}/events`
- `GET /tasks/{id}/events/stream`
- `POST /tasks/{id}/confirm-plan`
- `POST /tasks/{id}/pause`
- `POST /tasks/{id}/resume`
- `POST /tasks/{id}/cancel`
- `POST /tasks/{id}/retry`
- `POST /tasks/{id}/replan`
- `POST /tasks/{id}/events:batch`（本地 Runner 同步）

### 15.1 创建任务

```json
{
  "objective": "根据三份月报生成经营分析 PPT",
  "input_refs": ["file_1", "file_2", "file_3"],
  "desired_outputs": [
    {"type": "presentation", "format": "pptx"}
  ],
  "execution_preference": "local"
}
```

服务端返回 task_id、state、规划方式和初始策略。

### 15.2 本地事件批量同步

请求包含 task_id、device_id、from_sequence、events[]。每事件带 local_event_id 和 sequence。服务端返回 accepted_through、duplicates 和 rejected events。

## 16. 审批 API

- `GET /approvals?status=pending`
- `GET /approvals/{id}`
- `POST /approvals/{id}/approve`
- `POST /approvals/{id}/reject`

批准响应返回短期、一次性 capability：

```json
{
  "approval_token": "opaque...",
  "action": "artifact.publish",
  "resource_digest": "...",
  "expires_at": "..."
}
```

Token 不应被普通日志记录。

## 17. Knowledge/MaxKB API

- `GET /knowledge-bases`
- `POST /knowledge-bases`
- `GET /knowledge-bases/{id}`
- `POST /knowledge-bases/{id}/documents`
- `GET /knowledge-ingestions/{job_id}`
- `POST /knowledge-bases/{id}/responses`
- `GET /knowledge-documents/{id}`
- `DELETE /knowledge-documents/{id}`

平台 API 使用内部资源 ID，不直接把 MaxKB 外部 ID 暴露为主要契约。

## 18. 企业连接器 API

- `GET /enterprise-apps`
- `GET /datasets`
- `GET /datasets/{id}/metrics`
- `POST /datasets/{id}/query-plans`
- `POST /datasets/{id}/queries`
- `POST /connector-actions/{action_id}/prepare`
- `POST /connector-actions/{action_id}/execute`

写操作使用 prepare → 展示 effect → approval → execute。

## 19. 邮件 API（P1）

- `GET /mailboxes`
- `GET /mail/capabilities`
- `POST /mailboxes/authorizations`
- `GET /mailboxes/{id}/authorization-status`
- `POST /mailboxes/{id}/sync-requests`
- `GET /mail/sync-jobs/{id}`
- `GET /mail/messages`
- `GET /mail/messages/{id}`
- `POST /mail/drafts`
- `PATCH /mail/drafts/{id}`
- `POST /mail/drafts/{id}/prepare-send`
- `POST /mail/drafts/{id}/send`
- `GET /mail/send-attempts/{id}`
- `POST /mail/send-attempts/{id}/reconcile`

PATCH 草稿使用 If-Match/draft_version。prepare-send 返回冻结版本、From/To/Cc/Bcc、正文/附件预览、外部联系人、DLP、附件扫描、content digest、风险和一次性 approval/confirmation token。

send 必须同时使用 draft_version、prepare 返回的 content digest、approval/confirmation token 和 Idempotency-Key。同一 key 对不同请求摘要返回冲突；网络超时不自动重发，先查询 send-attempt 并进入 reconciliation_required。任一收件人、正文、主题、附件或发送账户变化都使旧 token 失效。

本地镜像模式中的邮件列表和详情可由桌面插件本地 Application Service 提供；策略、AI 调用、发送审计、健康和撤销仍使用平台 API。事件至少包含 mail.sync.*、mail.ai.*、mail.draft.*、mail.send.*、mail.policy.changed 和 mail.connector.paused，事件 payload 不携带完整正文或附件。

## 20. 插件 API

客户端：

- `GET /client/plugins`
- `POST /client/plugins/{id}/install-report`
- `POST /client/plugins/{id}/health-report`
- `GET /client/plugins/{id}/package-ticket`

管理端：

- `POST /admin/plugins`
- `POST /admin/plugins/{id}/versions`
- `POST /admin/plugin-versions/{id}/submit`
- `POST /admin/plugin-versions/{id}/approve`
- `POST /admin/plugin-versions/{id}/rollouts`
- `POST /admin/plugin-versions/{id}/revoke`

## 21. 模型与额度 API

客户端：

- `GET /models`
- `GET /usage/me/summary`
- `GET /usage/me/details`
- `POST /quota-requests`

管理端：

- `/admin/logical-models`
- `/admin/provider-models`
- `/admin/model-routes`
- `/admin/pricing-rules`
- `/admin/quota-rules`
- `/admin/usage/reconciliation`

## 22. 管理 API

- `/admin/users`
- `/admin/departments`
- `/admin/roles`
- `/admin/policies`
- `/admin/entitlements`
- `/admin/devices`
- `/admin/sessions`
- `/admin/connectors`
- `/admin/audit-events`
- `/admin/client-releases`
- `/admin/system-health`

所有管理写操作要求 reason 字段，并记录 before/after digest 或差异。

## 23. 领域事件

### 23.1 Envelope

```json
{
  "event_id": "evt_...",
  "event_type": "identity.user.disabled.v1",
  "occurred_at": "2026-08-07T17:14:00Z",
  "producer": "identity",
  "aggregate": {"type": "user", "id": "usr_...", "version": 8},
  "trace_id": "...",
  "data": {},
  "metadata": {"classification": "L1"}
}
```

### 23.2 关键事件

- `identity.user.disabled.v1`
- `identity.session.revoked.v1`
- `authorization.policy.published.v1`
- `model.catalog.published.v1`
- `quota.threshold.reached.v1`
- `ai.request.completed.v1`
- `agent.task.state_changed.v1`
- `agent.approval.required.v1`
- `plugin.version.revoked.v1`
- `connector.health.changed.v1`
- `client.release.rollout_paused.v1`
- `audit.export.completed.v1`

事件类型带版本；新增可选字段不升版本，破坏性 Schema 变化升版本。

## 24. 客户端版本协商

Bootstrap 返回：

```json
{
  "compatibility": {
    "server_api": "1.4",
    "minimum_client": "1.2.0",
    "recommended_client": "1.4.2",
    "runner_api": "1.1",
    "plugin_manifest_versions": [1]
  }
}
```

低于最低版本：只允许登录、更新、诊断和必要的数据迁移，不允许业务请求。

## 25. API 安全

- OpenAPI 文档生产环境需要授权；
- CORS 只允许管理后台正式 Origin，桌面原生请求不依赖开放 CORS；
- CSRF 用于 Cookie 管理后台；桌面 Bearer API 使用不同策略；
- 上传下载 URL 短期、资源级、不可列目录；
- API 响应不返回 secret_ref 的内部细节；
- 字段级脱敏按角色；
- 管理 API 和用户 API 可使用不同网关策略。

## 26. 契约测试

- OpenAPI Schema breaking change 检测；
- 旧客户端对新增字段/枚举容忍；
- 所有写 API 幂等；
- 401 刷新、403 禁止、429 Retry-After；
- SSE 正常、取消、中断、序号缺失和终态；
- 分页 cursor 篡改；
- If-Match 冲突；
- 管理字段脱敏；
- 外部连接器错误标准化；
- 本地事件重复和乱序同步。
