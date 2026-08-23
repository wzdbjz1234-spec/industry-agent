"""Standalone Mock QMS REST API and task page."""

from __future__ import annotations

from html import escape
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from quality_case_agent.adapters.qms.mock import MockQmsAdapter
from quality_case_agent.application.ports.qms import QmsTransientError
from quality_case_agent.application.qms.service import sign_qms_result
from quality_case_agent.contracts.qms import (
    QmsCreateTaskRequestContract,
    QmsTaskContract,
    QmsTaskResultContract,
)

DEFAULT_WEBHOOK_SECRET = b"phase9-demo-secret"


def create_mock_qms_app(
    adapter: MockQmsAdapter | None = None,
    *,
    webhook_secret: bytes = DEFAULT_WEBHOOK_SECRET,
) -> FastAPI:
    adapter = adapter or MockQmsAdapter(base_uri="http://localhost:8001")
    app = FastAPI(title="Mock QMS", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    def task_page() -> str:
        rows = "".join(
            "<tr>"
            f"<td>{escape(task.task_id)}</td>"
            f"<td>{escape(task.case_id)}</td>"
            f"<td>{escape(task.proposal_id)}</td>"
            f"<td>{escape(task.status)}</td>"
            f"<td><a href='/tasks/{escape(task.task_id)}'>查看</a> · "
            f"<a href='/tasks/{escape(task.task_id)}/result'>填写结果</a></td>"
            "</tr>"
            for task in adapter.list_tasks()
        )
        return (
            "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<title>Mock QMS Tasks</title></head><body>"
            "<h1>Mock QMS 调查任务</h1>"
            "<table><thead><tr><th>Task</th><th>Case</th><th>Proposal</th>"
            "<th>Status</th><th>Link</th></tr></thead>"
            f"<tbody>{rows or '<tr><td colspan=5>暂无任务</td></tr>'}</tbody></table>"
            "</body></html>"
        )

    @app.post("/api/v1/tasks", response_model=QmsTaskContract)
    def create_task(request: QmsCreateTaskRequestContract) -> QmsTaskContract:
        try:
            return adapter.create_task_request(request)
        except QmsTransientError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/tasks", response_model=dict[str, list[QmsTaskContract]])
    def list_tasks() -> dict[str, list[QmsTaskContract]]:
        return {"items": list(adapter.list_tasks())}

    @app.get("/api/v1/tasks/by-proposal/{proposal_id}", response_model=QmsTaskContract)
    def get_task_by_proposal(proposal_id: str) -> QmsTaskContract:
        task = adapter.get_task_by_proposal(proposal_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return task

    @app.get("/api/v1/tasks/{task_id}", response_model=QmsTaskContract)
    def get_task(task_id: str) -> QmsTaskContract:
        task = adapter.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return task

    @app.get("/tasks/{task_id}/result", response_class=HTMLResponse)
    def result_form(task_id: str) -> str:
        task = adapter.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        safe_task_id = escape(task.task_id, quote=True)
        safe_case_id = escape(task.case_id, quote=True)
        return f"""<!doctype html>
<html lang='zh-CN'><head><meta charset='utf-8'><title>提交 QMS 结果</title>
<style>body{{font-family:system-ui;max-width:760px;margin:32px auto;padding:0 16px}}label{{display:block;margin:12px 0 4px}}input,textarea,select{{width:100%;padding:8px;box-sizing:border-box}}button{{margin-top:18px;padding:10px 18px}}</style></head>
<body><h1>提交 QMS 调查结果</h1><p>Task: {safe_task_id} · Case: {safe_case_id}</p>
<form id='result-form'>
<label>确认人<input name='confirmed_by' value='engineer-01' required></label>
<label>确认编号<input name='confirmation_id' value='CONF-{safe_task_id}' required></label>
<label>根因编码<input name='root_cause_code' value='FIXTURE_LOCATING_PIN_LOOSE' required></label>
<label>实际根因<textarea name='root_cause_description' required>定位销松动导致工件向右上方向偏移</textarea></label>
<label>实际措施（每行一项）<textarea name='actions' required>更换定位销
重新标定夹具</textarea></label>
<label>验证状态<select name='verification_status'><option>VERIFIED_EFFECTIVE</option><option>NOT_VERIFIED</option><option>INCONCLUSIVE</option></select></label>
<label>样本数<input name='sample_count' type='number' value='500' min='1' required></label>
<label>验证前 NG 率<input name='ng_rate_before' type='number' value='0.087' step='0.001' min='0' max='1' required></label>
<label>验证后 NG 率<input name='ng_rate_after' type='number' value='0.018' step='0.001' min='0' max='1' required></label>
<label>验收标准<textarea name='acceptance_criteria' required>连续500件NG率低于2%</textarea></label>
<button type='submit'>生成签名结果</button></form><pre id='output'></pre>
<script>document.getElementById('result-form').addEventListener('submit', async (event) => {{
event.preventDefault(); const form = new FormData(event.target); const result = {{
event_type: 'qms.task.result-submitted.v1', event_id: 'qms-result-' + Date.now(), occurred_at: new Date().toISOString(),
confirmation_id: form.get('confirmation_id'), case_id: '{safe_case_id}', task_id: '{safe_task_id}', confirmed_by: form.get('confirmed_by'),
actual_root_cause: {{code: form.get('root_cause_code'), description: form.get('root_cause_description')}},
actual_actions: String(form.get('actions')).split('\\n').map(item => item.trim()).filter(Boolean),
verification: {{status: form.get('verification_status'), start: new Date(Date.now() - 3600000).toISOString(), end: new Date().toISOString(), sample_count: Number(form.get('sample_count')), ng_rate_before: Number(form.get('ng_rate_before')), ng_rate_after: Number(form.get('ng_rate_after')), acceptance_criteria: form.get('acceptance_criteria'), notes: ''}},
agent_assessment: {{top_hypothesis_matched: true, useful: true, human_rating: 4, comment: '现场结果已回传'}} }};
const response = await fetch('/api/v1/tasks/{safe_task_id}/result', {{method:'POST', headers:{{'content-type':'application/json'}}, body:JSON.stringify(result)}}); document.getElementById('output').textContent = await response.text();
}});</script></body></html>"""

    @app.post("/api/v1/tasks/{task_id}/result")
    def submit_result(task_id: str, result: QmsTaskResultContract) -> dict[str, object]:
        task = adapter.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        if result.task_id != task_id or result.case_id != task.case_id:
            raise HTTPException(status_code=422, detail="result does not match task")
        signature = sign_qms_result(result, webhook_secret)
        adapter.set_status(task_id, "CLOSED")
        return {
            "result": result,
            "signature": signature,
            "webhook_url": "http://localhost:8000/api/v1/integrations/qms/task-results",
        }

    @app.post("/api/v1/tasks/{task_id}/status", response_model=QmsTaskContract)
    def update_task_status(
        task_id: str, status: Literal["OPEN", "IN_PROGRESS", "CLOSED"]
    ) -> QmsTaskContract:
        try:
            return adapter.set_status(task_id, status)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task not found") from exc

    return app


app = create_mock_qms_app()
