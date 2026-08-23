# Quality Case Agent events

事件模型唯一来源是 `backend/src/quality_case_agent/contracts/`。本目录只记录事件流和消费者关系，不重复定义字段。

| Event type | Producer | Consumer | Idempotency key |
| --- | --- | --- | --- |
| `quality.case.opened.v1` | Case detector | Investigation Worker | `event_id + consumer_group` |
| `quality.analysis.started.v1` | Investigation Worker | Case detail/SSE | `event_id` |
| `quality.analysis.completed.v1` | Investigation Worker | Proposal service/UI | `event_id` |
| `quality.analysis.failed.v1` | Investigation Worker | Operations UI/DLQ | `event_id` |
| `quality.investigation.proposed.v1` | Proposal service | Approval UI | `proposal_id` |
| `quality.investigation.approved.v1` | Approval service | QMS worker | `decision_id` |
| `qms.task.created.v1` | QMS worker | Case detail/UI | `task_id` |
| `qms.task.result-submitted.v1` | Mock/enterprise QMS | Confirmation worker | `event_id` |
| `quality.case.confirmed.v1` | Confirmation worker | Archive worker/UI | `confirmation_id` |
| `quality.case.archived.v1` | Archive worker | Case Library/UI | `case_id + revision` |
| `quality.investigation.rejected.v1` | Approval service | Case UI | `decision_id` |
| `quality.investigation.reanalysis.requested.v1` | Approval service | Investigation Worker | `decision_id` |
