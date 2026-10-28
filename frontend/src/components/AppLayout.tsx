import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Bell, Building2, CheckSquare, ContactRound, Handshake, LayoutDashboard, LogOut, Menu, Target, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { AppNotification, Paginated } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { timeAgo } from "../lib/format";
import { Badge, Button } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/leads", label: "Leads", icon: Target },
  { to: "/deals", label: "Deals", icon: Handshake },
  { to: "/contacts", label: "Contacts", icon: ContactRound },
  { to: "/companies", label: "Companies", icon: Building2 },
  { to: "/tasks", label: "Tasks", icon: CheckSquare },
];

const ROLE_LABEL = { admin: "Admin", manager: "Manager", sales_rep: "Sales rep" } as const;

function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2.5 px-2 text-white">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold">CF</span>
      <span className="text-base font-semibold">ClientFlow CRM</span>
    </Link>
  );
}

function NotificationBell() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const count = useQuery({ queryKey: ["notifications", "count"], queryFn: () => api.get<{ unread: number }>("/notifications/unread-count/"), refetchInterval: 30_000 });
  const list = useQuery({ queryKey: ["notifications", "list"], queryFn: () => api.get<Paginated<AppNotification>>("/notifications/", { page_size: 10 }), enabled: open });
  const markAll = useMutation({ mutationFn: () => api.post("/notifications/read-all/"), onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }) });
  const markOne = useMutation({ mutationFn: (id: number) => api.post(`/notifications/${id}/read/`), onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }) });

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open]);

  const unread = count.data?.unread ?? 0;
  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-haspopup="true" aria-expanded={open}
        aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`} className="relative rounded-lg p-2 text-slate-700 hover:bg-slate-100">
        <Bell className="h-5 w-5" aria-hidden />
        {unread > 0 && <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-700 px-1 text-[10px] font-bold text-white">{unread}</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-[min(22rem,calc(100vw-1.5rem))] rounded-xl bg-white shadow-xl ring-1 ring-slate-200">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
            <h2 className="text-sm font-semibold">Notifications</h2>
            <button type="button" disabled={!unread} onClick={() => markAll.mutate()} className="text-xs font-medium text-brand-700 hover:underline disabled:text-slate-500 disabled:no-underline">Mark all read</button>
          </div>
          <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
            {list.isLoading && <li className="p-4 text-sm text-slate-600">Loading...</li>}
            {list.data?.results.length === 0 && <li className="p-6 text-center text-sm text-slate-600">You're all caught up.</li>}
            {list.data?.results.map((n) => (
              <li key={n.id}>
                <button type="button" className={clsx("block w-full px-4 py-3 text-left hover:bg-slate-50", !n.is_read && "bg-brand-50")}
                  onClick={() => { if (!n.is_read) markOne.mutate(n.id); setOpen(false); if (n.link) nav(n.link); }}>
                  <p className="flex items-center gap-2 text-sm font-medium text-slate-900">{!n.is_read && <span className="h-2 w-2 rounded-full bg-brand-600" aria-label="unread" />}{n.title}</p>
                  <p className="mt-0.5 text-xs text-slate-700">{n.message}</p>
                  <p className="mt-1 text-xs text-slate-500">{timeAgo(n.created_at)}</p>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const [drawer, setDrawer] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setDrawer(false), [pathname]);

  const sidebar = (
    <nav aria-label="Main" className="flex h-full flex-col gap-1 px-3 py-4">
      <div className="mb-4 flex items-center justify-between"><Brand />
        <button type="button" className="rounded-md p-1 text-slate-300 hover:bg-slate-800 lg:hidden" onClick={() => setDrawer(false)} aria-label="Close menu"><X className="h-5 w-5" aria-hidden /></button>
      </div>
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end}
          className={({ isActive }) => clsx("flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium", isActive ? "bg-slate-800 text-white" : "text-slate-300 hover:bg-slate-800/60 hover:text-white")}>
          <Icon className="h-[18px] w-[18px]" aria-hidden /> {label}
        </NavLink>
      ))}
      <p className="mt-auto px-3 pt-4 text-xs text-slate-400">Self-initiated portfolio project. All data is fictional.</p>
    </nav>
  );

  return (
    <div className="min-h-full">
      <a href="#main" className="sr-only z-[70] rounded bg-white px-3 py-2 text-sm focus:not-sr-only focus:fixed focus:left-2 focus:top-2">Skip to content</a>
      <aside className="fixed inset-y-0 left-0 hidden w-60 bg-slate-900 lg:block">{sidebar}</aside>
      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setDrawer(false)} aria-hidden />
          <aside className="absolute inset-y-0 left-0 w-64 bg-slate-900 shadow-xl">{sidebar}</aside>
        </div>
      )}
      <div className="lg:pl-60">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur">
          <button type="button" className="rounded-lg p-2 text-slate-700 hover:bg-slate-100 lg:hidden" onClick={() => setDrawer(true)} aria-label="Open menu"><Menu className="h-5 w-5" aria-hidden /></button>
          <div className="flex-1" />
          <NotificationBell />
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium leading-tight text-slate-900">{user?.full_name}</p>
              <p className="text-xs text-slate-600">{user ? ROLE_LABEL[user.role] : ""}</p>
            </div>
            <Badge tone="bg-brand-100 text-brand-800 ring-brand-100" className="sm:hidden">{user ? ROLE_LABEL[user.role] : ""}</Badge>
            <Button size="sm" onClick={() => void logout()} aria-label="Log out"><LogOut className="h-4 w-4" aria-hidden /><span className="hidden sm:inline">Log out</span></Button>
          </div>
        </header>
        <main id="main" className="mx-auto max-w-7xl p-4 sm:p-6"><Outlet /></main>
      </div>
    </div>
  );
}
