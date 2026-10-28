import { ArrowLeft, Mail, Pencil, Phone, Tag as TagIcon } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Company, Contact, Deal, Tag, User } from "../api/types";
import { useList, useOne, useOptions, useSave } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { FormModal, type FieldDef } from "../components/FormModal";
import { ResourceList, type Column } from "../components/ResourceList";
import { useToast } from "../components/Toast";
import { Badge, Button, Card, EmptyState, ErrorState, InfoGrid, PageHeader, Spinner } from "../components/ui";
import { ActivityTimeline, RelatedTasks } from "../components/widgets";
import { STAGE_TONE } from "../lib/constants";
import { money } from "../lib/format";

function TagChip({ tag }: { tag: Tag }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 text-xs font-medium text-slate-800 ring-1 ring-inset ring-slate-300">
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: tag.color }} aria-hidden />{tag.name}
    </span>
  );
}

function useContactFields(): FieldDef[] {
  const { isPrivileged } = useAuth();
  const companies = useOptions<Company>("companies", { ordering: "name" });
  const tags = useOptions<Tag>("tags");
  const users = useOptions<User>("users");
  const f: FieldDef[] = [
    { name: "first_name", label: "First name", required: true, maxLength: 100 },
    { name: "last_name", label: "Last name", required: true, maxLength: 100 },
    { name: "email", label: "Email", type: "email" },
    { name: "phone", label: "Phone", type: "tel", help: "Digits, spaces and + ( ) - . only" },
    { name: "job_title", label: "Job title" },
    { name: "company", label: "Company", type: "select", nullable: true, options: (companies.data ?? []).map((c) => ({ value: c.id, label: c.name })) },
    { name: "tag_ids", label: "Tags", type: "tags", options: (tags.data ?? []).map((t) => ({ value: t.id, label: t.name })) },
    { name: "notes", label: "Notes", type: "textarea" },
  ];
  if (isPrivileged) f.splice(6, 0, { name: "owner", label: "Owner", type: "select", nullable: true, options: (users.data ?? []).map((u) => ({ value: u.id, label: u.full_name })) });
  return f;
}

const BLANK = { first_name: "", last_name: "", email: "", phone: "", job_title: "", company: "", tag_ids: [], notes: "", owner: "" };
const toForm = (c: Contact) => ({ ...c, company: c.company ?? "", owner: c.owner ?? "", tag_ids: c.tags.map((t) => t.id) });

function NewTagButton() {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const save = useSave<Tag>("tags");
  return (
    <>
      <Button onClick={() => setOpen(true)}><TagIcon className="h-4 w-4" aria-hidden /> New tag</Button>
      {open && <FormModal title="New tag" initial={{ name: "", color: "#4f46e5" }} onClose={() => setOpen(false)}
        fields={[{ name: "name", label: "Name", required: true, maxLength: 50 }, { name: "color", label: "Color (hex)", required: true, placeholder: "#4f46e5", help: "Format: #rrggbb" }]}
        onSubmit={async (v) => { await save.mutateAsync({ data: v }); toast.success("Tag created. You can now assign it to contacts."); }} />}
    </>
  );
}

export function ContactsPage() {
  const { isPrivileged } = useAuth();
  const fields = useContactFields();
  const companies = useOptions<Company>("companies", { ordering: "name" });
  const tags = useOptions<Tag>("tags");
  const columns: Column<Contact>[] = [
    { key: "name", header: "Name", sortKey: "last_name", render: (c) => c.full_name },
    { key: "company", header: "Company", sortKey: "company__name", render: (c) => c.company_name || "-" },
    { key: "email", header: "Email", sortKey: "email", render: (c) => c.email || "-", hideOnMobile: true },
    { key: "phone", header: "Phone", render: (c) => c.phone || "-", hideOnMobile: true },
    { key: "tags", header: "Tags", hideOnMobile: true, render: (c) => <div className="flex flex-wrap gap-1">{c.tags.map((t) => <TagChip key={t.id} tag={t} />)}</div> },
  ];
  return (
    <ResourceList<Contact>
      title="Contacts" subtitle="People at your customers and prospects." resource="contacts" noun="contact" columns={columns} fields={fields}
      newValues={BLANK} toFormValues={toForm} detailPath={(c) => `/contacts/${c.id}`} rowLabel={(c) => c.full_name}
      defaultOrdering="last_name" searchPlaceholder="Search name, email, company..." canDelete={() => isPrivileged} extraActions={<NewTagButton />}
      filters={[
        { kind: "select", key: "company", label: "Company", options: (companies.data ?? []).map((c) => ({ value: c.id, label: c.name })) },
        { kind: "select", key: "tag", label: "Tag", options: (tags.data ?? []).map((t) => ({ value: t.id, label: t.name })) },
      ]}
      emptyHint="Contacts hold the people you talk to. Link each one to a company."
    />
  );
}

export function ContactDetailPage() {
  const { id } = useParams();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const contact = useOne<Contact>("contacts", id);
  const deals = useList<Deal>("deals", { contact: id, page_size: 50 });
  const save = useSave<Contact>("contacts");
  const fields = useContactFields();

  if (contact.isLoading) return <Spinner />;
  if (contact.isError || !contact.data) return <ErrorState error={contact.error} onRetry={() => contact.refetch()} />;
  const c = contact.data;
  return (
    <>
      <Link to="/contacts" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-700 hover:underline"><ArrowLeft className="h-4 w-4" aria-hidden /> Contacts</Link>
      <PageHeader title={c.full_name} subtitle={[c.job_title, c.company_name].filter(Boolean).join(" at ") || undefined}
        actions={<Button onClick={() => setEditing(true)}><Pencil className="h-4 w-4" aria-hidden /> Edit</Button>} />
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <Card title="Details">
            <InfoGrid items={[
              { label: "Email", value: c.email && <a href={`mailto:${c.email}`} className="inline-flex items-center gap-1 text-brand-700 hover:underline"><Mail className="h-3.5 w-3.5" aria-hidden />{c.email}</a> },
              { label: "Phone", value: c.phone && <span className="inline-flex items-center gap-1"><Phone className="h-3.5 w-3.5" aria-hidden />{c.phone}</span> },
              { label: "Company", value: c.company && <Link to={`/companies/${c.company}`} className="text-brand-700 hover:underline">{c.company_name}</Link> },
              { label: "Owner", value: c.owner_name },
              { label: "Tags", value: c.tags.length ? <div className="flex flex-wrap gap-1">{c.tags.map((t) => <TagChip key={t.id} tag={t} />)}</div> : null },
              { label: "Notes", value: c.notes },
            ]} />
          </Card>
          <Card title={`Deals (${deals.data?.count ?? 0})`} padded={false}>
            {!deals.data?.results.length ? <EmptyState title="No deals with this contact" /> : (
              <ul className="divide-y divide-slate-100">
                {deals.data.results.map((d) => (
                  <li key={d.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                    <Link to={`/deals/${d.id}`} className="font-medium text-brand-700 hover:underline">{d.title}</Link>
                    <span className="flex items-center gap-3"><span className="tabular-nums">{money(d.amount)}</span><Badge tone={STAGE_TONE[d.stage]}>{d.stage_label}</Badge></span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <RelatedTasks link={{ contact: c.id }} />
        </div>
        <div className="lg:col-span-1"><ActivityTimeline link={{ contact: c.id, company: c.company ?? undefined }} /></div>
      </div>
      {editing && <FormModal title="Edit contact" fields={fields} initial={toForm(c)} onClose={() => setEditing(false)}
        onSubmit={async (v) => { await save.mutateAsync({ id: c.id, data: v }); toast.success("Changes saved."); }} />}
    </>
  );
}
