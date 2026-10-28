import { ArrowLeft, Globe, Mail, MapPin, Pencil, Phone } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Company, Contact, Deal, User } from "../api/types";
import { useList, useOne, useOptions, useSave } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { FormModal, type FieldDef } from "../components/FormModal";
import { ResourceList, type Column } from "../components/ResourceList";
import { useToast } from "../components/Toast";
import { Badge, Button, Card, EmptyState, ErrorState, InfoGrid, PageHeader, Spinner } from "../components/ui";
import { ActivityTimeline } from "../components/widgets";
import { STAGE_TONE } from "../lib/constants";
import { money } from "../lib/format";

export function useCompanyFields(): FieldDef[] {
  const { isPrivileged } = useAuth();
  const users = useOptions<User>("users");
  const f: FieldDef[] = [
    { name: "name", label: "Company name", required: true, full: true, maxLength: 200 },
    { name: "industry", label: "Industry" },
    { name: "website", label: "Website", type: "url", placeholder: "https://" },
    { name: "email", label: "Email", type: "email" },
    { name: "phone", label: "Phone", type: "tel", help: "Digits, spaces and + ( ) - . only" },
    { name: "address", label: "Address", full: true },
    { name: "city", label: "City" },
    { name: "country", label: "Country" },
    { name: "notes", label: "Notes", type: "textarea" },
  ];
  if (isPrivileged) f.splice(8, 0, { name: "owner", label: "Account owner", type: "select", nullable: true, options: (users.data ?? []).map((u) => ({ value: u.id, label: u.full_name })) });
  return f;
}

const BLANK = { name: "", industry: "", website: "", email: "", phone: "", address: "", city: "", country: "", notes: "", owner: "" };

export function CompaniesPage() {
  const { isPrivileged } = useAuth();
  const fields = useCompanyFields();
  const columns: Column<Company>[] = [
    { key: "name", header: "Company", sortKey: "name", render: (c) => c.name },
    { key: "industry", header: "Industry", sortKey: "industry", render: (c) => c.industry || "-", hideOnMobile: true },
    { key: "city", header: "City", sortKey: "city", render: (c) => c.city || "-", hideOnMobile: true },
    { key: "contacts", header: "Contacts", sortKey: "contact_count", render: (c) => c.contact_count ?? 0 },
    { key: "deals", header: "Deals", sortKey: "deal_count", render: (c) => c.deal_count ?? 0, hideOnMobile: true },
  ];
  return (
    <ResourceList<Company>
      title="Companies" subtitle="Organisations you work with and the people linked to them." resource="companies" noun="company"
      columns={columns} fields={fields} newValues={BLANK} defaultOrdering="name" searchPlaceholder="Search name, industry, city..."
      toFormValues={(c) => ({ ...c, owner: c.owner ?? "" })} detailPath={(c) => `/companies/${c.id}`} rowLabel={(c) => c.name}
      canDelete={() => isPrivileged} emptyHint="Add the businesses you sell to, then link contacts and deals to them."
    />
  );
}

export function CompanyDetailPage() {
  const { id } = useParams();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const company = useOne<Company>("companies", id);
  const contacts = useList<Contact>("contacts", { company: id, page_size: 50 });
  const deals = useList<Deal>("deals", { company: id, page_size: 50 });
  const save = useSave<Company>("companies");
  const fields = useCompanyFields();

  if (company.isLoading) return <Spinner />;
  if (company.isError || !company.data) return <ErrorState error={company.error} onRetry={() => company.refetch()} />;
  const c = company.data;
  return (
    <>
      <Link to="/companies" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-700 hover:underline"><ArrowLeft className="h-4 w-4" aria-hidden /> Companies</Link>
      <PageHeader title={c.name} subtitle={[c.industry, c.city].filter(Boolean).join(" · ") || undefined}
        actions={<Button onClick={() => setEditing(true)}><Pencil className="h-4 w-4" aria-hidden /> Edit</Button>} />
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <Card title="Details">
            <InfoGrid items={[
              { label: "Website", value: c.website && <a href={c.website} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-brand-700 hover:underline"><Globe className="h-3.5 w-3.5" aria-hidden />{c.website}</a> },
              { label: "Email", value: c.email && <a href={`mailto:${c.email}`} className="inline-flex items-center gap-1 text-brand-700 hover:underline"><Mail className="h-3.5 w-3.5" aria-hidden />{c.email}</a> },
              { label: "Phone", value: c.phone && <span className="inline-flex items-center gap-1"><Phone className="h-3.5 w-3.5" aria-hidden />{c.phone}</span> },
              { label: "Address", value: [c.address, c.city, c.country].filter(Boolean).join(", ") && <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" aria-hidden />{[c.address, c.city, c.country].filter(Boolean).join(", ")}</span> },
              { label: "Account owner", value: c.owner_name },
              { label: "Notes", value: c.notes },
            ]} />
          </Card>
          <Card title={`Contacts (${contacts.data?.count ?? 0})`} padded={false}>
            {!contacts.data?.results.length ? <EmptyState title="No contacts linked" hint="Create a contact and choose this company." /> : (
              <ul className="divide-y divide-slate-100">
                {contacts.data.results.map((p) => (
                  <li key={p.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                    <div><Link to={`/contacts/${p.id}`} className="font-medium text-brand-700 hover:underline">{p.full_name}</Link><p className="text-xs text-slate-600">{p.job_title || "No title"}</p></div>
                    <span className="truncate text-slate-700">{p.email}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title={`Deals (${deals.data?.count ?? 0})`} padded={false}>
            {!deals.data?.results.length ? <EmptyState title="No deals yet" /> : (
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
        </div>
        <div className="lg:col-span-1"><ActivityTimeline link={{ company: c.id }} /></div>
      </div>
      {editing && <FormModal title="Edit company" fields={fields} initial={{ ...c, owner: c.owner ?? "" }} onClose={() => setEditing(false)}
        onSubmit={async (v) => { await save.mutateAsync({ id: c.id, data: v }); toast.success("Changes saved."); }} />}
    </>
  );
}

