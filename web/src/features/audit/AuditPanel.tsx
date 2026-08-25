import { ShieldCheck } from "lucide-react";

export type AuditEvent = {
  event_id: string;
  event_type: string;
  occurred_at: string;
  actor_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  event_hash: string;
};

export default function AuditPanel({ events }: { events: AuditEvent[] }) {
  return <section className="surface data-surface"><header className="panel-header"><div><span>AUDIT TRAIL</span><h3>身份与审计事件</h3></div><span className="confidence"><ShieldCheck size={14} />Append-only</span></header><div className="stack-list">{events.length === 0 ? <p className="subtle-copy">暂无审计事件</p> : events.map((event) => <article className="stack-row" key={event.event_id}><span className="row-icon"><ShieldCheck size={17} /></span><div><span className="pill">{event.action}</span><h3>{event.resource_type} · {event.resource_id}</h3><p>{event.actor_id} · {new Date(event.occurred_at).toLocaleString("zh-CN")}</p></div><div className="row-meta"><small>{event.event_hash.slice(0, 12)}…</small></div></article>)}</div></section>;
}
