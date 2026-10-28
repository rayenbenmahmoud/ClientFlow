import clsx from "clsx";
import { CalendarClock, CheckCircle2, Circle, FileText, Mail, Phone, Plus, Users, Workflow } from "lucide-react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import type { Interaction, Task } from "../api/types";
import { useAction, useList, useSave } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { INTERACTION_TYPES, PRIORITIES, PRIORITY_TONE } from "../lib/constants";
import { formatDate, formatDateTime, relativeDay, toLocalInput, todayISO } from "../lib/format";
import { useState } from "react";
import { FormModal, type FieldDef } from "./FormModal";
import { useToast } from "./Toast";
import { Badge, Button, Card, EmptyState, ErrorState, OVERDUE_TONE, Spinner } from "./ui";

const ICONS = { call: Phone, meeting: Users, email: Mail, note: FileText } as const;

type Link4 = { contact?: number; company?: number; deal?: number; lead?: number };

/** Timeline of calls/meetings/notes for a record, with a "Log interaction" action. */
export function ActivityTimeline({ link, title = "Activity history" }: { link: Link4; title?: string }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const q = useList<Interaction>("interactions", { ...link, page_size: 30 });
  const save = useSave<Interaction>("interactions");
  const fields: FieldDef[] = [
    { name: "type", label: "Type", type: "select", required: true, options: INTERACTION_TYPES },
    { name: "occurred_at", label: "When", type: "datetime-local", required: true },
    { name: "subject", label: "Subject", required: true, full: true, maxLength: 200 },
    { name: "notes", label: "Notes", type: "textarea" },
  ];
  return (
    <Card title={title} action={<Button size="sm" onClick={() => setOpen(true)}><Plus className="h-3.5 w-3.5" aria-hidden /> Log interaction</Button>}>
      {q.isLoading ? <Spinner /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !q.data?.results.length ? (
        <EmptyState title="No activity yet" hint="Log a call, meeting or note to build the history." />
      ) : (
        <ol className="space-y-4">
          {q.data.results.map((i) => <InteractionItem key={i.id} i={i} />)}
        </ol>
      )}
      {open && (
        <FormModal title="Log interaction" fields={fields} initial={{ type: "call", occurred_at: toLocalInput(), subject: "", notes: "" }} submitLabel="Log interaction"
          onClose={() => setOpen(false)}
          onSubmit={async (v) => { await save.mutateAsync({ data: { ...v, ...link } }); toast.success("Interaction logged."); }} />
      )}
    </Card>
  );
}

export function InteractionItem({ i, showLinks }: { i: Interaction; showLinks?: boolean }) {
  const Icon = i.is_system ? Workflow : ICONS[i.type];
  return (
    <li className="flex gap-3">
      <span className={clsx("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full", i.is_system ? "bg-violet-100 text-violet-800" : "bg-brand-100 text-brand-800")}>
        <Icon className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0 text-sm">
        <p className="font-medium text-slate-900">
          {i.subject} {i.is_system && <Badge tone="bg-violet-100 text-violet-900 ring-violet-300" className="ml-1">Automated</Badge>}
        </p>
        {i.notes && <p className="mt-0.5 whitespace-pre-line text-slate-700">{i.notes}</p>}
        <p className="mt-0.5 text-xs text-slate-600">
          {i.is_system ? "Workflow" : i.type_label} · {formatDateTime(i.occurred_at)}{i.created_by_name ? ` · ${i.created_by_name}` : ""}
          {showLinks && (i.contact_name || i.company_name || i.deal_title) && (
            <> · {i.deal ? <Link className="text-brand-700 hover:underline" to={`/deals/${i.deal}`}>{i.deal_title}</Link> : i.contact ? <Link className="text-brand-700 hover:underline" to={`/contacts/${i.contact}`}>{i.contact_name}</Link> : i.company_name}</>
          )}
        </p>
      </div>
    </li>
  );
}

export function TaskRow({ t, onToggle, busy }: { t: Task; onToggle: (t: Task) => void; busy?: boolean }) {
  const done = t.status === "done";
  return (
    <li className="flex items-start gap-3">
      <button type="button" onClick={() => onToggle(t)} disabled={busy} aria-label={done ? `Reopen task ${t.title}` : `Mark task ${t.title} as done`} className="mt-0.5 text-slate-600 hover:text-emerald-700">
        {done ? <CheckCircle2 className="h-5 w-5 text-emerald-700" aria-hidden /> : <Circle className="h-5 w-5" aria-hidden />}
      </button>
      <div className="min-w-0 flex-1 text-sm">
        <p className={clsx("font-medium", done ? "text-slate-500 line-through" : "text-slate-900")}>{t.title}</p>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-600">
          <CalendarClock className="h-3.5 w-3.5" aria-hidden />
          <span className={clsx(t.is_overdue && "font-semibold text-rose-800")}>{done ? `Done` : relativeDay(t.due_date)} · {formatDate(t.due_date)}</span>
          {t.is_overdue && <Badge tone={OVERDUE_TONE}>Overdue</Badge>}
          <Badge tone={PRIORITY_TONE[t.priority]}>{t.priority_label}</Badge>
          {t.auto_created && <Badge tone="bg-violet-100 text-violet-900 ring-violet-300">Auto</Badge>}
        </p>
      </div>
    </li>
  );
}

/** Tasks attached to a record, with quick-add and complete/reopen. */
export function RelatedTasks({ link, title = "Tasks" }: { link: { lead?: number; deal?: number; contact?: number }; title?: string }) {
  const toast = useToast();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const q = useList<Task>("tasks", { ...link, ordering: "status,due_date", page_size: 50 });
  const save = useSave<Task>("tasks");
  const complete = useAction("tasks", "complete");
  const reopen = useAction("tasks", "reopen");
  const fields: FieldDef[] = [
    { name: "title", label: "Title", required: true, full: true, maxLength: 200 },
    { name: "due_date", label: "Due date", type: "date", required: true },
    { name: "priority", label: "Priority", type: "select", required: true, options: PRIORITIES },
    { name: "description", label: "Details", type: "textarea" },
  ];
  async function toggle(t: Task) {
    try {
      await (t.status === "done" ? reopen : complete).mutateAsync({ id: t.id });
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "Could not update the task."); }
  }
  return (
    <Card title={title} action={<Button size="sm" onClick={() => setOpen(true)}><Plus className="h-3.5 w-3.5" aria-hidden /> Add task</Button>}>
      {q.isLoading ? <Spinner /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !q.data?.results.length ? (
        <EmptyState title="No tasks" hint="Add a reminder so nothing slips through." />
      ) : (
        <ul className="space-y-3">{q.data.results.map((t) => <TaskRow key={t.id} t={t} onToggle={toggle} />)}</ul>
      )}
      {open && (
        <FormModal title="New task" fields={fields} initial={{ title: "", due_date: todayISO(), priority: "medium", description: "" }} submitLabel="Add task"
          onClose={() => setOpen(false)}
          onSubmit={async (v) => { await save.mutateAsync({ data: { ...v, ...link, assignee: user?.id } }); toast.success("Task added."); }} />
      )}
    </Card>
  );
}

