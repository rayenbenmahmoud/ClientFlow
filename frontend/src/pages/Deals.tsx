import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowLeft, Check, KanbanSquare, Pencil, Plus, Table2 } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Company, Contact, Deal, DealHistoryEntry, DealStage, PipelineColumn, User } from "../api/types";
import { useAction, useOne, useOptions, useSave } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { FormModal, type FieldDef } from "../components/FormModal";
import { ResourceList, type Column } from "../components/ResourceList";
import { useToast } from "../components/Toast";
import { Badge, Button, Card, ErrorState, InfoGrid, PageHeader, Spinner } from "../components/ui";
import { ActivityTimeline, RelatedTasks } from "../components/widgets";
import { ALLOWED_TRANSITIONS, OPEN_STAGES, STAGES, STAGE_BAR, STAGE_TONE, stageLabel } from "../lib/constants";
import { formatDate, formatDateTime, money } from "../lib/format";

function useDealFields(): FieldDef[] {
  const { isPrivileged } = useAuth();
  const users = useOptions<User>("users");
  const companies = useOptions<Company>("companies", { ordering: "name" });
  const contacts = useOptions<Contact>("contacts", { ordering: "last_name" });
  const f: FieldDef[] = [
    { name: "title", label: "Deal title", required: true, full: true, maxLength: 200 },
    { name: "company", label: "Company", type: "select", required: true, options: (companies.data ?? []).map((c) => ({ value: c.id, label: c.name })) },
    { name: "contact", label: "Contact", type: "select", nullable: true, options: (contacts.data ?? []).map((c) => ({ value: c.id, label: `${c.full_name}${c.company_name ? ` (${c.company_name})` : ""}` })), help: "Must belong to the selected company." },
    { name: "amount", label: "Amount (USD)", type: "number", required: true, min: 0, step: "0.01" },
    { name: "expected_close_date", label: "Expected close", type: "date", nullable: true },
  ];
  if (isPrivileged) f.push({ name: "owner", label: "Owner", type: "select", required: true, options: (users.data ?? []).map((u) => ({ value: u.id, label: u.full_name })) });
  return f;
}

/** Shared "move deal" logic: validates in the UI, asks for a reason when losing, relies on the server for the real rules. */
function useMoveDeal() {
  const toast = useToast();
  const change = useAction<Deal>("deals", "change-stage");
  const [lostFor, setLostFor] = useState<Deal | null>(null);

  async function move(deal: Deal, stage: DealStage, lost_reason?: string) {
    if (stage === "lost" && lost_reason === undefined) return setLostFor(deal);
    try {
      await change.mutateAsync({ id: deal.id, data: { stage, lost_reason } });
      toast.success(`"${deal.title}" moved to ${stageLabel(stage)}.`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not move the deal.");
    }
  }
  const lostModal = lostFor && (
    <FormModal title={`Mark "${lostFor.title}" as lost`} submitLabel="Mark as lost" initial={{ lost_reason: "" }} onClose={() => setLostFor(null)}
      fields={[{ name: "lost_reason", label: "Why was it lost?", type: "textarea", required: true }]}
      onSubmit={async (v) => { await change.mutateAsync({ id: lostFor.id, data: { stage: "lost", lost_reason: v.lost_reason } }); toast.success("Deal marked as lost."); }} />
  );
  return { move, lostModal };
}

function ViewToggle({ view, setView }: { view: "board" | "table"; setView: (v: "board" | "table") => void }) {
  const btn = (v: "board" | "table", Icon: typeof Table2, label: string) => (
    <button type="button" onClick={() => setView(v)} aria-pressed={view === v}
      className={clsx("inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium", view === v ? "bg-brand-600 text-white" : "bg-white text-slate-800 hover:bg-slate-50")}>
      <Icon className="h-4 w-4" aria-hidden /> {label}
    </button>
  );
  return <div className="inline-flex overflow-hidden rounded-lg ring-1 ring-slate-300" role="group" aria-label="View">{btn("board", KanbanSquare, "Board")}{btn("table", Table2, "Table")}</div>;
}

function DealCard({ deal, onMove, onDragStart }: { deal: Deal; onMove: (d: Deal, s: DealStage) => void; onDragStart: (d: Deal) => void }) {
  const targets = ALLOWED_TRANSITIONS[deal.stage];
  return (
    <li draggable={targets.length > 0}
      onDragStart={(e) => { e.dataTransfer.setData("text/plain", String(deal.id)); e.dataTransfer.effectAllowed = "move"; onDragStart(deal); }}
      className={clsx("rounded-lg bg-white p-3 shadow-sm ring-1 ring-slate-200", targets.length > 0 && "cursor-grab active:cursor-grabbing")}>
      <Link to={`/deals/${deal.id}`} className="text-sm font-medium text-slate-900 hover:text-brand-700 hover:underline">{deal.title}</Link>
      <p className="mt-0.5 truncate text-xs text-slate-600">{deal.company_name}</p>
      <div className="mt-2 flex items-center justify-between gap-2 text-xs">
        <span className="text-sm font-semibold tabular-nums text-slate-900">{money(deal.amount)}</span>
        <span className="text-slate-600">{deal.expected_close_date ? formatDate(deal.expected_close_date) : "No close date"}</span>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="truncate text-xs text-slate-600">{deal.owner_name}</span>
        {targets.length > 0 && (
          <select aria-label={`Move ${deal.title} to another stage`} value="" onChange={(e) => e.target.value && onMove(deal, e.target.value as DealStage)}
            className="max-w-[7.5rem] rounded-md border-0 py-1 pl-2 pr-6 text-xs ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-brand-600">
            <option value="">Move to...</option>
            {targets.map((s) => <option key={s} value={s}>{stageLabel(s)}</option>)}
          </select>
        )}
      </div>
    </li>
  );
}

function Board({ params }: { params: Record<string, string> }) {
  const { move, lostModal } = useMoveDeal();
  const [dragging, setDragging] = useState<Deal | null>(null);
  const [over, setOver] = useState<DealStage | null>(null);
  const q = useQuery({ queryKey: ["deals", "pipeline", params], queryFn: () => api.get<PipelineColumn[]>("/deals/pipeline/", params) });

  if (q.isLoading) return <Spinner />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const allDeals = q.data!.flatMap((c) => c.deals);
  const empty = q.data!.every((c) => c.count === 0);

  return (
    <>
      {empty && <p className="mb-3 rounded-lg bg-white p-4 text-sm text-slate-700 ring-1 ring-slate-200">No deals yet. Create your first deal to see it on the board.</p>}
      <div className="flex gap-3 overflow-x-auto pb-3" onDragEnd={() => { setDragging(null); setOver(null); }}>
        {q.data!.map((col) => {
          const canDrop = dragging ? ALLOWED_TRANSITIONS[dragging.stage].includes(col.stage) : false;
          return (
            <section key={col.stage} aria-label={`${col.label} stage`}
              onDragOver={(e) => { if (canDrop) { e.preventDefault(); setOver(col.stage); } }}
              onDragLeave={() => setOver((o) => (o === col.stage ? null : o))}
              onDrop={(e) => { e.preventDefault(); setOver(null); const id = Number(e.dataTransfer.getData("text/plain")); const d = allDeals.find((x) => x.id === id); if (d && canDrop) void move(d, col.stage); }}
              className={clsx("w-72 shrink-0 rounded-xl bg-slate-100 p-2.5 ring-2 transition-colors", over === col.stage ? "ring-brand-600" : canDrop ? "ring-brand-600/30" : "ring-transparent")}>
              <header className="mb-2 flex items-center justify-between px-1">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900"><span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: STAGE_BAR[col.stage] }} aria-hidden />{col.label}<span className="rounded-full bg-white px-2 text-xs font-medium text-slate-700">{col.count}</span></h3>
                <span className="text-xs font-medium tabular-nums text-slate-700">{money(col.total)}</span>
              </header>
              <ul className="min-h-[3rem] space-y-2">
                {col.deals.map((d) => <DealCard key={d.id} deal={d} onDragStart={setDragging} onMove={(deal, s) => void move(deal, s)} />)}
                {col.deals.length === 0 && <li className="rounded-lg border border-dashed border-slate-300 p-3 text-center text-xs text-slate-600">{canDrop ? "Drop here" : "No deals"}</li>}
                {col.count > col.deals.length && <li className="text-center text-xs text-slate-600">Showing {col.deals.length} of {col.count}. Use the table view for the rest.</li>}
              </ul>
            </section>
          );
        })}
      </div>
      <p className="mt-1 text-xs text-slate-600">Drag a card to a highlighted column, or use the "Move to" menu. Only valid next stages are offered; the server enforces the rules.</p>
      {lostModal}
    </>
  );
}

export function DealsPage() {
  const { isPrivileged, user } = useAuth();
  const [view, setView] = useState<"board" | "table">("board");
  const [creating, setCreating] = useState(false);
  const [owner, setOwner] = useState("");
  const [search, setSearch] = useState("");
  const toast = useToast();
  const fields = useDealFields();
  const users = useOptions<User>("users");
  const save = useSave<Deal>("deals");
  const blank = { title: "", company: "", contact: "", amount: "", expected_close_date: "", owner: user?.id ?? "" };

  const columns: Column<Deal>[] = [
    { key: "title", header: "Deal", sortKey: "title", render: (d) => d.title },
    { key: "company", header: "Company", sortKey: "company__name", render: (d) => d.company_name, hideOnMobile: true },
    { key: "amount", header: "Amount", sortKey: "amount", render: (d) => money(d.amount), className: "tabular-nums" },
    { key: "stage", header: "Stage", sortKey: "stage", render: (d) => <Badge tone={STAGE_TONE[d.stage]}>{d.stage_label}</Badge> },
    { key: "close", header: "Expected close", sortKey: "expected_close_date", render: (d) => formatDate(d.expected_close_date), hideOnMobile: true },
    ...(isPrivileged ? [{ key: "owner", header: "Owner", render: (d: Deal) => d.owner_name, hideOnMobile: true } as Column<Deal>] : []),
  ];

  if (view === "table") {
    return (
      <ResourceList<Deal>
        title="Deals" subtitle="Every opportunity with an amount, owner and expected close date." resource="deals" noun="deal" columns={columns}
        fields={fields} newValues={blank} toFormValues={(d) => ({ ...d, contact: d.contact ?? "", expected_close_date: d.expected_close_date ?? "" })}
        detailPath={(d) => `/deals/${d.id}`} rowLabel={(d) => d.title} defaultOrdering="-updated_at" searchPlaceholder="Search deal, company, contact..."
        canDelete={() => isPrivileged} extraActions={<ViewToggle view={view} setView={setView} />}
        filters={[
          { kind: "select", key: "stage", label: "Stage", options: STAGES },
          ...(isPrivileged ? [{ kind: "select" as const, key: "owner", label: "Owner", options: (users.data ?? []).map((u) => ({ value: u.id, label: u.full_name })) }] : []),
          { kind: "toggle", key: "open", label: "Open deals only" },
        ]}
        emptyHint="Deals track the money: attach each one to a company and move it through the pipeline."
      />
    );
  }

  return (
    <>
      <PageHeader title="Pipeline" subtitle="Drag deals between stages to keep the pipeline current."
        actions={<>
          <ViewToggle view={view} setView={setView} />
          <Button variant="primary" onClick={() => setCreating(true)}><Plus className="h-4 w-4" aria-hidden /> New deal</Button>
        </>} />
      <div className="mb-4 flex flex-wrap gap-2">
        <input type="search" aria-label="Search deals" placeholder="Search deals..." value={search} onChange={(e) => setSearch(e.target.value)}
          className="min-w-[12rem] flex-1 rounded-lg border-0 px-3 py-2 text-sm ring-1 ring-inset ring-slate-300 placeholder:text-slate-500 focus:ring-2 focus:ring-brand-600 sm:max-w-xs" />
        {isPrivileged && (
          <select aria-label="Owner" value={owner} onChange={(e) => setOwner(e.target.value)} className="rounded-lg border-0 py-2 pl-3 pr-8 text-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-brand-600">
            <option value="">Owner: everyone</option>
            {(users.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
          </select>
        )}
      </div>
      <Board params={{ search, owner }} />
      {creating && <FormModal title="New deal" fields={fields} initial={blank} submitLabel="Create deal" onClose={() => setCreating(false)}
        onSubmit={async (v) => { await save.mutateAsync({ data: v }); toast.success("Deal created in the New stage."); }} />}
    </>
  );
}

export function DealDetailPage() {
  const { id } = useParams();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const deal = useOne<Deal>("deals", id);
  const history = useQuery({ queryKey: ["deals", "history", id], queryFn: () => api.get<DealHistoryEntry[]>(`/deals/${id}/history/`) });
  const save = useSave<Deal>("deals");
  const fields = useDealFields();
  const { move, lostModal } = useMoveDeal();

  if (deal.isLoading) return <Spinner />;
  if (deal.isError || !deal.data) return <ErrorState error={deal.error} onRetry={() => deal.refetch()} />;
  const d = deal.data;
  const targets = ALLOWED_TRANSITIONS[d.stage];
  const currentIdx = OPEN_STAGES.indexOf(d.stage);

  return (
    <>
      <Link to="/deals" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-700 hover:underline"><ArrowLeft className="h-4 w-4" aria-hidden /> Deals</Link>
      <PageHeader title={<span className="flex flex-wrap items-center gap-3">{d.title} <Badge tone={STAGE_TONE[d.stage]}>{d.stage_label}</Badge></span>}
        subtitle={<><Link to={`/companies/${d.company}`} className="text-brand-700 hover:underline">{d.company_name}</Link> · {money(d.amount, true)}</>}
        actions={<Button onClick={() => setEditing(true)}><Pencil className="h-4 w-4" aria-hidden /> Edit</Button>} />

      <Card className="mb-5" title="Stage">
        <ol className="mb-4 flex flex-wrap items-center gap-2" aria-label="Pipeline progress">
          {OPEN_STAGES.concat(d.stage === "lost" ? ["lost"] : ["won"]).map((s, i) => {
            const reached = d.stage === "won" ? s !== "lost" : d.stage === "lost" ? s === "lost" : i <= currentIdx;
            return (
              <li key={s} aria-current={s === d.stage ? "step" : undefined} className={clsx("flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset", reached ? STAGE_TONE[s] : "bg-white text-slate-600 ring-slate-300")}>
                {reached && <Check className="h-3.5 w-3.5" aria-hidden />}{stageLabel(s)}
              </li>
            );
          })}
        </ol>
        {targets.length ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-slate-700">Move to:</span>
            {targets.map((s) => <Button key={s} size="sm" variant={s === "won" ? "primary" : s === "lost" ? "danger" : "secondary"} onClick={() => void move(d, s)}>{stageLabel(s)}</Button>)}
          </div>
        ) : <p className="text-sm text-slate-700">This deal is closed as won. Won deals are final.</p>}
        {d.stage === "lost" && d.lost_reason && <p className="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-900 ring-1 ring-rose-300"><strong>Lost reason:</strong> {d.lost_reason}</p>}
      </Card>

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <Card title="Details">
            <InfoGrid items={[
              { label: "Amount", value: money(d.amount, true) },
              { label: "Expected close", value: d.expected_close_date && formatDate(d.expected_close_date) },
              { label: "Company", value: <Link to={`/companies/${d.company}`} className="text-brand-700 hover:underline">{d.company_name}</Link> },
              { label: "Contact", value: d.contact && <Link to={`/contacts/${d.contact}`} className="text-brand-700 hover:underline">{d.contact_name}</Link> },
              { label: "Owner", value: d.owner_name },
              { label: "Closed", value: d.closed_at && formatDateTime(d.closed_at) },
            ]} />
          </Card>
          <Card title="Stage history">
            {history.isLoading ? <Spinner /> : (
              <ol className="space-y-2 text-sm">
                {history.data?.map((h) => (
                  <li key={h.id} className="flex flex-wrap items-center gap-x-2">
                    <span className="font-medium text-slate-900">{h.from_stage ? `${h.from_stage_label} → ${h.to_stage_label}` : `Created in ${h.to_stage_label}`}</span>
                    <span className="text-xs text-slate-600">{formatDateTime(h.changed_at)}{h.changed_by_name ? ` · ${h.changed_by_name}` : ""}</span>
                  </li>
                ))}
              </ol>
            )}
          </Card>
          <RelatedTasks link={{ deal: d.id }} />
        </div>
        <div className="lg:col-span-1"><ActivityTimeline link={{ deal: d.id, company: d.company, contact: d.contact ?? undefined }} /></div>
      </div>
      {editing && <FormModal title="Edit deal" fields={fields} initial={{ ...d, contact: d.contact ?? "", expected_close_date: d.expected_close_date ?? "" }} onClose={() => setEditing(false)}
        onSubmit={async (v) => { await save.mutateAsync({ id: d.id, data: v }); toast.success("Changes saved."); }} />}
      {lostModal}
    </>
  );
}
