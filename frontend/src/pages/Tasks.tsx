import clsx from "clsx";
import { CalendarDays, ChevronLeft, ChevronRight, List, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import type { Task, User } from "../api/types";
import { useAction, useList, useOptions, useSave } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { FormModal, type FieldDef } from "../components/FormModal";
import { ResourceList, type Column } from "../components/ResourceList";
import { useToast } from "../components/Toast";
import { Badge, Button, Card, EmptyState, ErrorState, OVERDUE_TONE, PageHeader, Spinner } from "../components/ui";
import { TaskRow } from "../components/widgets";
import { PRIORITIES, PRIORITY_TONE } from "../lib/constants";
import { formatDate, relativeDay, todayISO, toISODate } from "../lib/format";

function useTaskFields(): FieldDef[] {
  const { isPrivileged } = useAuth();
  const users = useOptions<User>("users");
  const f: FieldDef[] = [
    { name: "title", label: "Title", required: true, full: true, maxLength: 200 },
    { name: "due_date", label: "Due date", type: "date", required: true },
    { name: "priority", label: "Priority", type: "select", required: true, options: PRIORITIES },
    { name: "description", label: "Details", type: "textarea" },
  ];
  if (isPrivileged) f.splice(3, 0, { name: "assignee", label: "Assigned to", type: "select", required: true, options: (users.data ?? []).map((u) => ({ value: u.id, label: u.full_name })) });
  return f;
}

function useToggleTask() {
  const toast = useToast();
  const complete = useAction("tasks", "complete");
  const reopen = useAction("tasks", "reopen");
  return async (t: Task) => {
    try {
      await (t.status === "done" ? reopen : complete).mutateAsync({ id: t.id });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not update the task.");
    }
  };
}

function ViewToggle({ view, setView }: { view: "list" | "calendar"; setView: (v: "list" | "calendar") => void }) {
  const btn = (v: "list" | "calendar", Icon: typeof List, label: string) => (
    <button type="button" onClick={() => setView(v)} aria-pressed={view === v}
      className={clsx("inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium", view === v ? "bg-brand-600 text-white" : "bg-white text-slate-800 hover:bg-slate-50")}>
      <Icon className="h-4 w-4" aria-hidden /> {label}
    </button>
  );
  return <div className="inline-flex overflow-hidden rounded-lg ring-1 ring-slate-300" role="group" aria-label="View">{btn("list", List, "List")}{btn("calendar", CalendarDays, "Calendar")}</div>;
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function Calendar({ view, setView }: { view: "list" | "calendar"; setView: (v: "list" | "calendar") => void }) {
  const { user } = useAuth();
  const toast = useToast();
  const toggle = useToggleTask();
  const fields = useTaskFields();
  const save = useSave<Task>("tasks");
  const [cursor, setCursor] = useState(() => { const n = new Date(); return new Date(n.getFullYear(), n.getMonth(), 1); });
  const [selected, setSelected] = useState(todayISO());
  const [creating, setCreating] = useState(false);

  const gridStart = new Date(cursor.getFullYear(), cursor.getMonth(), 1 - cursor.getDay());
  const days = Array.from({ length: 42 }, (_, i) => new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + i));
  const q = useList<Task>("tasks", { due_after: toISODate(days[0]), due_before: toISODate(days[41]), page_size: 100, ordering: "due_date" });

  const byDay = new Map<string, Task[]>();
  for (const t of q.data?.results ?? []) byDay.set(t.due_date, [...(byDay.get(t.due_date) ?? []), t]);
  const today = todayISO();
  const selectedTasks = byDay.get(selected) ?? [];
  const monthLabel = cursor.toLocaleDateString("en-US", { month: "long", year: "numeric" });
  const shift = (n: number) => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + n, 1));

  return (
    <>
      <PageHeader title="Tasks" subtitle="Due dates at a glance. Select a day to see and complete its tasks."
        actions={<><ViewToggle view={view} setView={setView} /><Button variant="primary" onClick={() => setCreating(true)}><Plus className="h-4 w-4" aria-hidden /> New task</Button></>} />
      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2" padded={false}
          title={<span aria-live="polite">{monthLabel}</span>}
          action={<div className="flex items-center gap-1">
            <Button size="sm" onClick={() => shift(-1)} aria-label="Previous month"><ChevronLeft className="h-4 w-4" aria-hidden /></Button>
            <Button size="sm" onClick={() => { const n = new Date(); setCursor(new Date(n.getFullYear(), n.getMonth(), 1)); setSelected(todayISO()); }}>Today</Button>
            <Button size="sm" onClick={() => shift(1)} aria-label="Next month"><ChevronRight className="h-4 w-4" aria-hidden /></Button>
          </div>}>
          {q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : (
            <div role="grid" aria-label={`Tasks in ${monthLabel}`}>
              <div role="row" className="grid grid-cols-7 border-b border-slate-100 text-center text-xs font-semibold uppercase text-slate-600">
                {WEEKDAYS.map((w) => <div key={w} role="columnheader" className="py-2">{w}</div>)}
              </div>
              <div className="grid grid-cols-7">
                {days.map((d) => {
                  const iso = toISODate(d);
                  const tasks = byDay.get(iso) ?? [];
                  const open = tasks.filter((t) => t.status === "open");
                  const overdue = open.some((t) => t.is_overdue);
                  const inMonth = d.getMonth() === cursor.getMonth();
                  return (
                    <button key={iso} type="button" role="gridcell" onClick={() => setSelected(iso)} aria-selected={selected === iso}
                      aria-label={`${d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}: ${tasks.length} task${tasks.length === 1 ? "" : "s"}`}
                      className={clsx("flex min-h-[3.5rem] flex-col items-start gap-1 border-b border-r border-slate-100 p-1.5 text-left hover:bg-slate-50 sm:min-h-[5.5rem]", !inMonth && "bg-slate-50/60", selected === iso && "bg-brand-50 ring-2 ring-inset ring-brand-600")}>
                      <span className={clsx("flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium", iso === today ? "bg-brand-600 text-white" : inMonth ? "text-slate-900" : "text-slate-500")}>{d.getDate()}</span>
                      <span className="hidden w-full space-y-0.5 sm:block">
                        {tasks.slice(0, 2).map((t) => (
                          <span key={t.id} className={clsx("block truncate rounded px-1 py-0.5 text-[11px] font-medium", t.status === "done" ? "bg-slate-100 text-slate-600 line-through" : t.is_overdue ? "bg-rose-100 text-rose-900" : "bg-brand-100 text-brand-800")}>{t.title}</span>
                        ))}
                        {tasks.length > 2 && <span className="block text-[11px] text-slate-700">+{tasks.length - 2} more</span>}
                      </span>
                      {tasks.length > 0 && <span className={clsx("h-2 w-2 rounded-full sm:hidden", overdue ? "bg-rose-700" : "bg-brand-600")} aria-hidden />}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </Card>
        <Card title={`${formatDate(selected)} · ${relativeDay(selected)}`}>
          {q.isLoading ? <Spinner /> : selectedTasks.length === 0 ? (
            <EmptyState title="Nothing due" hint="Enjoy the quiet, or add a task for this day." />
          ) : (
            <ul className="space-y-3">{selectedTasks.map((t) => <TaskRow key={t.id} t={t} onToggle={toggle} />)}</ul>
          )}
        </Card>
      </div>
      {creating && <FormModal title="New task" fields={fields} initial={{ title: "", due_date: selected, priority: "medium", description: "", assignee: user?.id ?? "" }} submitLabel="Create task" onClose={() => setCreating(false)}
        onSubmit={async (v) => { await save.mutateAsync({ data: v }); toast.success("Task created."); }} />}
    </>
  );
}

export function TasksPage() {
  const { isPrivileged, user } = useAuth();
  const [view, setView] = useState<"list" | "calendar">("list");
  const toggle = useToggleTask();
  const users = useOptions<User>("users");
  const fields = useTaskFields();

  if (view === "calendar") return <Calendar view={view} setView={setView} />;

  const columns: Column<Task>[] = [
    { key: "done", header: "Done", render: (t) => (
      <input type="checkbox" checked={t.status === "done"} onChange={() => void toggle(t)} className="h-4 w-4 rounded text-brand-600" aria-label={t.status === "done" ? `Reopen ${t.title}` : `Complete ${t.title}`} />
    ) },
    { key: "title", header: "Task", sortKey: "title", render: (t) => (
      <span className="flex flex-wrap items-center gap-2"><span className={t.status === "done" ? "text-slate-500 line-through" : "font-medium text-slate-900"}>{t.title}</span>
        {t.auto_created && <Badge tone="bg-violet-100 text-violet-900 ring-violet-300">Auto</Badge>}</span>
    ) },
    { key: "due", header: "Due", sortKey: "due_date", render: (t) => (
      <span className="inline-flex flex-wrap items-center gap-1.5"><span className={t.is_overdue ? "font-semibold text-rose-800" : undefined}>{formatDate(t.due_date)}</span>{t.is_overdue && <Badge tone={OVERDUE_TONE}>Overdue</Badge>}</span>
    ) },
    { key: "priority", header: "Priority", render: (t) => <Badge tone={PRIORITY_TONE[t.priority]}>{t.priority_label}</Badge>, hideOnMobile: true },
    { key: "related", header: "Related to", hideOnMobile: true, render: (t) => t.lead ? <Link className="text-brand-700 hover:underline" to={`/leads/${t.lead}`}>{t.lead_name}</Link> : t.deal ? <Link className="text-brand-700 hover:underline" to={`/deals/${t.deal}`}>{t.deal_title}</Link> : t.contact ? <Link className="text-brand-700 hover:underline" to={`/contacts/${t.contact}`}>{t.contact_name}</Link> : "-" },
    ...(isPrivileged ? [{ key: "assignee", header: "Assignee", render: (t: Task) => t.assignee_name, hideOnMobile: true } as Column<Task>] : []),
  ];
  return (
    <ResourceList<Task>
      title="Tasks" subtitle="Reminders and follow-ups. Tasks for new leads are created automatically." resource="tasks" noun="task" columns={columns}
      fields={fields} newValues={{ title: "", due_date: todayISO(), priority: "medium", description: "", assignee: user?.id ?? "" }}
      rowLabel={(t) => t.title} defaultOrdering="due_date" searchPlaceholder="Search tasks..." extraActions={<ViewToggle view={view} setView={setView} />}
      filters={[
        { kind: "select", key: "status", label: "Status", options: [{ value: "open", label: "Open" }, { value: "done", label: "Done" }] },
        { kind: "select", key: "priority", label: "Priority", options: PRIORITIES },
        ...(isPrivileged ? [{ kind: "select" as const, key: "assignee", label: "Assignee", options: (users.data ?? []).map((u) => ({ value: u.id, label: u.full_name })) }] : []),
        { kind: "toggle", key: "overdue", label: "Overdue only" },
      ]}
      emptyHint="Tasks are reminders with a due date. Add one, or create a lead to get an automatic follow-up."
    />
  );
}
