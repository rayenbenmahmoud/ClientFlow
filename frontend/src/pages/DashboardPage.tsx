import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarCheck, Handshake, Target, Trophy, Wallet } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ApiError } from "../api/client";
import type { Dashboard } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { Badge, Button, Card, EmptyState, ErrorState, OVERDUE_TONE, PageHeader, Spinner } from "../components/ui";
import { InteractionItem, TaskRow } from "../components/widgets";
import { SOURCE_COLORS, STAGE_BAR, STAGE_TONE } from "../lib/constants";
import { formatDate, money, relativeDay } from "../lib/format";
import { useAction } from "../api/hooks";
import { useMutation, useQueryClient } from "@tanstack/react-query";

function Kpi({ icon, label, value, sub, to, alert }: { icon: ReactNode; label: string; value: ReactNode; sub?: ReactNode; to: string; alert?: boolean }) {
  return (
    <Link to={to} className="group rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200 transition hover:ring-brand-600">
      <div className="flex items-center justify-between text-slate-600"><span className="text-sm font-medium">{label}</span><span aria-hidden>{icon}</span></div>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-900">{value}</p>
      {sub && <p className={alert ? "mt-1 text-xs font-semibold text-rose-800" : "mt-1 text-xs text-slate-600"}>{sub}</p>}
    </Link>
  );
}

export function DashboardPage() {
  const { user, isPrivileged } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<Dashboard>("/dashboard/") });
  const complete = useAction("tasks", "complete");
  const runWorkflows = useMutation({
    mutationFn: () => api.post<{ flagged: number; cleared: number }>("/automation/run/"),
    onSuccess: (r) => { toast.success(`Workflow run complete: ${r.flagged} lead(s) flagged, ${r.cleared} cleared.`); void qc.invalidateQueries(); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Workflow run failed."),
  });

  if (q.isLoading) return <Spinner />;
  if (q.isError || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  const k = d.kpis;
  const chart = d.pipeline.filter((p) => p.stage !== "lost").map((p) => ({ ...p, valueNum: Number(p.value) }));
  const totalDeals = d.pipeline.reduce((n, p) => n + p.count, 0);

  return (
    <>
      <PageHeader title={`Welcome back, ${user?.first_name || user?.username}`}
        subtitle={d.scope === "all" ? "Team-wide overview" : "Your personal overview"}
        actions={isPrivileged ? <Button onClick={() => runWorkflows.mutate()} loading={runWorkflows.isPending}>Run workflow rules</Button> : undefined} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Kpi to="/leads" icon={<Target className="h-5 w-5" />} label="Open leads" value={k.open_leads}
          sub={k.overdue_leads ? `${k.overdue_leads} overdue follow-up${k.overdue_leads > 1 ? "s" : ""}` : "No overdue follow-ups"} alert={k.overdue_leads > 0} />
        <Kpi to="/deals" icon={<Handshake className="h-5 w-5" />} label="Active deals" value={k.active_deals} sub="In open stages" />
        <Kpi to="/deals" icon={<Wallet className="h-5 w-5" />} label="Pipeline value" value={money(k.pipeline_value)} sub="Open deals" />
        <Kpi to="/deals" icon={<Trophy className="h-5 w-5" />} label="Won this month" value={money(k.won_this_month_value)} sub={`${k.won_this_month_count} deal${k.won_this_month_count === 1 ? "" : "s"}`} />
        <Kpi to="/tasks" icon={<CalendarCheck className="h-5 w-5" />} label="Tasks due today" value={k.tasks_due_today}
          sub={k.tasks_overdue ? `${k.tasks_overdue} overdue` : `${k.tasks_open} open in total`} alert={k.tasks_overdue > 0} />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Sales pipeline" action={<Link to="/deals" className="text-sm font-medium text-brand-700 hover:underline">Open board</Link>}>
          {totalDeals === 0 ? <EmptyState title="No deals yet" hint="Create a deal to see your pipeline." /> : (
            <>
              <div role="img" aria-label={`Pipeline value by stage: ${chart.map((c) => `${c.label} ${money(c.value)}`).join(", ")}`}>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={chart} layout="vertical" margin={{ left: 8, right: 16 }}>
                    <CartesianGrid horizontal={false} stroke="#e2e8f0" />
                    <XAxis type="number" tickFormatter={(v: number) => (v >= 1000 ? `$${v / 1000}k` : `$${v}`)} tick={{ fill: "#475569", fontSize: 12 }} />
                    <YAxis type="category" dataKey="label" width={92} tick={{ fill: "#334155", fontSize: 12 }} />
                    <Tooltip formatter={(v) => money(Number(v))} cursor={{ fill: "#f1f5f9" }} />
                    <Bar dataKey="valueNum" name="Value" radius={[0, 4, 4, 0]}>
                      {chart.map((c) => <Cell key={c.stage} fill={STAGE_BAR[c.stage]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
                {chart.map((c) => (
                  <li key={c.stage} className="rounded-lg bg-slate-50 p-2.5 text-center">
                    <Badge tone={STAGE_TONE[c.stage]}>{c.label}</Badge>
                    <p className="mt-1 text-lg font-semibold tabular-nums text-slate-900">{c.count}</p>
                    <p className="text-xs tabular-nums text-slate-600">{money(c.value)}</p>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>

        <Card title="Open leads by source">
          {d.leads_by_source.length === 0 ? <EmptyState title="No open leads" /> : (
            <div role="img" aria-label={`Open leads by source: ${d.leads_by_source.map((s) => `${s.label} ${s.count}`).join(", ")}`}>
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={d.leads_by_source} dataKey="count" nameKey="label" innerRadius={55} outerRadius={85} paddingAngle={2}>
                    {d.leads_by_source.map((s, i) => <Cell key={s.source} fill={SOURCE_COLORS[i % SOURCE_COLORS.length]} />)}
                  </Pie>
                  <Tooltip />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card title="Upcoming tasks" action={<Link to="/tasks" className="text-sm font-medium text-brand-700 hover:underline">All tasks</Link>}>
          {d.upcoming_tasks.length === 0 ? <EmptyState title="You're all caught up" hint="No open tasks." /> : (
            <ul className="space-y-3">{d.upcoming_tasks.map((t) => <TaskRow key={t.id} t={t} onToggle={(x) => void complete.mutateAsync({ id: x.id })} busy={complete.isPending} />)}</ul>
          )}
        </Card>
        <Card title={<span className="flex items-center gap-2">Leads needing follow-up {k.overdue_leads > 0 && <AlertTriangle className="h-4 w-4 text-rose-700" aria-hidden />}</span>}>
          {d.overdue_leads.length === 0 ? <EmptyState title="No overdue follow-ups" hint="Every open lead is on schedule." /> : (
            <ul className="divide-y divide-slate-100">
              {d.overdue_leads.map((l) => (
                <li key={l.id} className="flex items-center justify-between gap-2 py-2.5 text-sm">
                  <div className="min-w-0"><Link to={`/leads/${l.id}`} className="font-medium text-brand-700 hover:underline">{l.full_name}</Link><p className="truncate text-xs text-slate-600">{l.company_name || l.source_label}</p></div>
                  <div className="text-right"><Badge tone={OVERDUE_TONE}>{relativeDay(l.follow_up_date!)}</Badge><p className="mt-0.5 text-xs text-slate-600">{formatDate(l.follow_up_date)}</p></div>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Recent activity">
          {d.recent_activities.length === 0 ? <EmptyState title="No activity yet" hint="Log a call or note on any record." /> : (
            <ol className="space-y-4">{d.recent_activities.map((i) => <InteractionItem key={i.id} i={i} showLinks />)}</ol>
          )}
        </Card>
      </div>
    </>
  );
}
