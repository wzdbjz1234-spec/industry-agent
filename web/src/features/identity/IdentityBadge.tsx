import { ShieldCheck } from "lucide-react";

export type IdentityBadgeProps = {
  actorId: string;
  role: string;
  organization: string;
};

export default function IdentityBadge({ actorId, role, organization }: IdentityBadgeProps) {
  return <span className="identity-badge" title={`${actorId} · ${organization}`}><ShieldCheck size={14} /><span>{role}</span></span>;
}
