import { ArrowLeft, ArrowRightLeft, Mail, Pencil, Phone } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { Deal, Lead, User } from "../api/types";
import { useAction, useOne, useOptions, useSave } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { FormModal, type FieldDef } from "../components/FormModal";
import { ResourceList, type Column } from "../components/ResourceList";
import { useToast } from "../components/Toast";
import { Badge, Button, Card, ErrorState, InfoGrid, OVERDUE_TONE, PageHeader, Spinner } from "../components/ui";
import { ActivityTimeline, RelatedTasks } from "../components/widgets";
import { LEAD_SOURCES, LEAD_STATUSES, LEAD_TONE } from "../lib/constants";
import { formatDate, money, relativeDay, todayISO } from "../lib/format";

function useLeadFields(editing: boolean): FieldDef[] {
  const { isPrivileged } = useAuth();
  const users = useOptions<User>("users");
  const f: FieldDef[] = [
    { name: "first_name", label: "First name", required: true, maxLength: 100 },
    { name: "last_name", label: "Last name", required: true, maxLength: 100 },
    { name: "email", label: "Email", type: "email" },
    { name: "phone", label: "Phone", type: "tel", help: "Digits, spaces and + ( ) - . only" },
    { name: "company_name", label: "Company", help: "Required to convert the lead into a deal" },
    { name: "job_title", label: "Job title" },
    { name: "source", label: "Source", type: "select", required: true, options: LEAD_SOURCES },
    { name: "status", label: "Status", type: "select", required: true, options: LEAD_STATUSES.filter((s) => s.value !== "converted") },
    { name: "follow_up_date", label: "Follow-up date", type: "date", nullable: true, min: editing ? undefined : todayISO(), help: editing ? undefined : "A follow-up task is created automatically (default: in 2 days)." },
    { name: "estimated_value", label: "Estimated value (USD)", type: "number", nullable: true, min: 0, step: "0.01" },
    { name: "notes", label: "Notes", type: "textarea" },
  ];
  if (isPrivileged) f.splice(8, 0, { name: "owner", label: "Owner", type: "select", required: true, options: (users.data ?? []).map((u) => ({ value: u.id, label: u.full_name })) });
  return f;
}

export function FollowUp({ lead }: { lead: Lead }) {
  if (!lead.follow_up_date) return <span className="text-slate-500">-</span>;
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span className={lead.is_overdue ? "font-semibold text-rose-800" : undefined}>{formatDate(lead.follow_up_date)}</span>
      {lead.is_overdue ? <Badge tone={OVERDUE_TONE}>Overdue · {relativeDay(lead.follow_up_date)}</Badge> : null}
    </span>
  );
}

function ConvertModal({ lead, onClose }: { lead: Lead; onClose: () => void }) {
  const toast = useToast();
  const nav = useNavigate();
  const convert = useAction<Deal>("leads", "convert");
  return (
    <FormModal
      title={`Convert ${lead.full_name}`} submitLabel="Convert to deal" onClose={onClose}
      intro={`Creates (or reuses) the company "${lead.company_name}" and a contact, then opens a new deal. This happens all at once or not at all.`}
      initial={{ deal_title: `${lead.company_name} - new opportunity`, amount: lead.estimated_value ?? "", expected_close_date: "" }}
      fields={[
        { name: "deal_title", label: "Deal title", required: true, full: true, maxLength: 200 },
        { name: "amount", label: "Amount (USD)", type: "number", required: true, min: 0, step: "0.01" },
        { name: "expected_close_date", label: "Expected close", type: "date", nullable: true },
      ]}
      onSubmit={async (v) => {
        const deal = await convert.mutateAsync({ id: lead.id, data: v });
        toast.success("Lead converted. The new deal is in the pipeline.");
        nav(`/deals/${deal.id}`);
      }}
    />
  );
}

export function LeadsPage() {
  const { isPrivileged, user } = useAuth();
  const users = useOptions<User>("users");
  const fields = useLeadFields(false);
  const editFields = useLeadFields(true);
  const [converting, setConverting] = useState<Lead | null>(null);
  const columns: Column<Lead>[] = [
    { key: "name", header: "Lead", sortKey: "last_name", render: (l) => l.full_name },
    { key: "company", header: "Company", sortKey: "company_name", render: (l) => l.company_name || "-", hideOnMobile: true },
    { key: "source", header: "Source", sortKey: "source", render: (l) => l.source_label, hideOnMobile: true },
    { key: "status", header: "Status", sortKey: "status", render: (l) => <Badge tone={LEAD_TONE[l.status]}>{l.status_label}</Badge> },
    { key: "follow", header: "Follow-up", sortKey: "follow_up_date", render: (l) => <FollowUp lead={l} /> },
    ...(isPrivileged ? [{ key: "owner", header: "Owner", render: (l: Lead) => l.owner_name, hideOnMobile: true } as Column<Lead>] : []),
    { key: "value", header: "Est. value", render: (l) => money(l.estimated_value), hideOnMobile: true, className: "tabular-nums" },
  ];
  return (
    <>
      <ResourceList<Lead>
        title="Leads" subtitle="Prospects to qualify. Every new lead gets a follow-up task automatically." resource="leads" noun="lead"
        columns={columns} fields={fields} editFields={editFields} newValues={{ first_name: "", last_name: "", email: "", phone: "", company_name: "", job_title: "", source: "website", status: "new", follow_up_date: "", estimated_value: "", notes: "", owner: user?.id ?? "" }}
        toFormValues={(l) => ({ ...l, follow_up_date: l.follow_up_date ?? "", estimated_value: l.estimated_value ?? "" })}
        detailPath={(l) => `/leads/${l.id}`} rowLabel={(l) => l.full_name} defaultOrdering="-created_at" searchPlaceholder="Search name, company, email..."
        filters={[
          { kind: "select", key: "status", label: "Status", options: LEAD_STATUSES },
          { kind: "select", key: "source", label: "Source", options: LEAD_SOURCES },
          ...(isPrivileged ? [{ kind: "select" as const, key: "owner", label: "Owner", options: (users.data ?? []).map((u) => ({ value: u.id, label: u.full_name })) }] : []),
          { kind: "toggle", key: "overdue", label: "Overdue follow-ups" },
        ]}
        rowActions={(l) => l.status !== "converted" && l.status !== "unqualified" ? <Button size="sm" variant="ghost" onClick={() => setConverting(l)} aria-label={`Convert ${l.full_name}`}>Convert</Button> : null}
        emptyHint="Leads are prospects who haven't been qualified yet. Add one to see the automatic follow-up task."
      />
      {converting && <ConvertModal lead={converting} onClose={() => setConverting(null)} />}
    </>
  );
}

export function LeadDetailPage() {
  const { id } = useParams();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [converting, setConverting] = useState(false);
  const lead = useOne<Lead>("leads", id);
  const save = useSave<Lead>("leads");
  const fields = useLeadFields(true);

  if (lead.isLoading) return <Spinner />;
  if (lead.isError || !lead.data) return <ErrorState error={lead.error} onRetry={() => lead.refetch()} />;
  const l = lead.data;
  const canConvert = l.status !== "converted" && l.status !== "unqualified";
  return (
    <>
      <Link to="/leads" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-700 hover:underline"><ArrowLeft className="h-4 w-4" aria-hidden /> Leads</Link>
      <PageHeader
        title={<span className="flex flex-wrap items-center gap-3">{l.full_name} <Badge tone={LEAD_TONE[l.status]}>{l.status_label}</Badge>{l.is_overdue && <Badge tone={OVERDUE_TONE}>Follow-up overdue</Badge>}</span>}
        subtitle={[l.job_title, l.company_name].filter(Boolean).join(" at ") || undefined}
        actions={<>
          {canConvert && <Button variant="primary" onClick={() => setConverting(true)}><ArrowRightLeft className="h-4 w-4" aria-hidden /> Convert to deal</Button>}
          <Button onClick={() => setEditing(true)}><Pencil className="h-4 w-4" aria-hidden /> Edit</Button>
        </>}
      />
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <Card title="Details">
            <InfoGrid items={[
              { label: "Email", value: l.email && <a href={`mailto:${l.email}`} className="inline-flex items-center gap-1 text-brand-700 hover:underline"><Mail className="h-3.5 w-3.5" aria-hidden />{l.email}</a> },
              { label: "Phone", value: l.phone && <span className="inline-flex items-center gap-1"><Phone className="h-3.5 w-3.5" aria-hidden />{l.phone}</span> },
              { label: "Source", value: l.source_label },
              { label: "Owner", value: l.owner_name },
              { label: "Follow-up", value: <FollowUp lead={l} /> },
              { label: "Estimated value", value: l.estimated_value && money(l.estimated_value) },
              { label: "Converted deal", value: l.converted_deal && <Link to={`/deals/${l.converted_deal}`} className="text-brand-700 hover:underline">View deal #{l.converted_deal}</Link> },
              { label: "Notes", value: l.notes },
            ]} />
          </Card>
          <RelatedTasks link={{ lead: l.id }} title="Follow-up tasks" />
        </div>
        <div className="lg:col-span-1"><ActivityTimeline link={{ lead: l.id }} /></div>
      </div>
      {editing && <FormModal title="Edit lead" fields={fields} initial={{ ...l, follow_up_date: l.follow_up_date ?? "", estimated_value: l.estimated_value ?? "" }} onClose={() => setEditing(false)}
        onSubmit={async (v) => { await save.mutateAsync({ id: l.id, data: v }); toast.success("Changes saved."); }} />}
      {converting && <ConvertModal lead={l} onClose={() => setConverting(false)} />}
    </>
  );
}
