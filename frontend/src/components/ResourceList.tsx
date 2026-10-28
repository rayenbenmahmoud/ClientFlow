import clsx from "clsx";
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Download, Plus, Search } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ApiError, downloadCsv } from "../api/client";
import { useList, useRemove, useSave } from "../api/hooks";
import { FormModal, type FieldDef, type Option } from "./FormModal";
import { useToast } from "./Toast";
import { Button, Card, ConfirmDialog, EmptyState, ErrorState, PageHeader, Spinner } from "./ui";

export interface Column<T> {
  key: string;
  header: string;
  sortKey?: string;
  render: (row: T) => ReactNode;
  hideOnMobile?: boolean;
  className?: string;
}
export type FilterDef =
  | { kind: "select"; key: string; label: string; options: Option[] }
  | { kind: "toggle"; key: string; label: string };

interface Props<T extends { id: number }> {
  title: string;
  subtitle?: string;
  resource: string;
  noun: string; // singular, for messages ("contact")
  columns: Column<T>[];
  filters?: FilterDef[];
  fields: FieldDef[];
  editFields?: FieldDef[]; // defaults to `fields`
  newValues: Record<string, unknown>;
  toFormValues?: (row: T) => Record<string, unknown>;
  detailPath?: (row: T) => string;
  canDelete?: (row: T) => boolean;
  canEdit?: (row: T) => boolean;
  defaultOrdering?: string;
  baseParams?: Record<string, string | number | boolean | undefined>;
  searchPlaceholder?: string;
  emptyHint?: string;
  rowLabel: (row: T) => string;
  extraActions?: ReactNode;
  rowActions?: (row: T) => ReactNode;
}

const PAGE_SIZE = 15;

function useDebounced<V>(value: V, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function ResourceList<T extends { id: number }>(p: Props<T>) {
  const toast = useToast();
  const [search, setSearch] = useState("");
  const q = useDebounced(search);
  const [page, setPage] = useState(1);
  const [ordering, setOrdering] = useState(p.defaultOrdering ?? "");
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<T | "new" | null>(null);
  const [deleting, setDeleting] = useState<T | null>(null);
  const [exporting, setExporting] = useState(false);

  const params = { ...p.baseParams, ...filterValues, search: q, ordering, page, page_size: PAGE_SIZE };
  // Reset to page 1 whenever the query changes (done in the handlers below, not an effect, to avoid a double fetch).
  const list = useList<T>(p.resource, params);
  const save = useSave<T>(p.resource);
  const remove = useRemove(p.resource);

  const setFilter = (key: string, value: string) => {
    setFilterValues((f) => ({ ...f, [key]: value }));
    setPage(1);
  };
  const toggleSort = (key: string) => {
    setOrdering((o) => (o === key ? `-${key}` : key));
    setPage(1);
  };

  const rows = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const pages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const filtered = Boolean(q || Object.values(filterValues).some(Boolean));

  async function doExport() {
    setExporting(true);
    try {
      await downloadCsv(p.resource, { ...p.baseParams, ...filterValues, search: q, ordering });
      toast.success("CSV export downloaded.");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Export failed.");
    } finally {
      setExporting(false);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    try {
      await remove.mutateAsync(deleting.id);
      toast.success(`${p.noun[0].toUpperCase()}${p.noun.slice(1)} deleted.`);
      setDeleting(null);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Delete failed.");
      setDeleting(null);
    }
  }

  return (
    <>
      <PageHeader
        title={p.title}
        subtitle={p.subtitle}
        actions={
          <>
            {p.extraActions}
            <Button onClick={doExport} loading={exporting}><Download className="h-4 w-4" aria-hidden /> Export CSV</Button>
            <Button variant="primary" onClick={() => setEditing("new")}><Plus className="h-4 w-4" aria-hidden /> New {p.noun}</Button>
          </>
        }
      />
      <Card padded={false}>
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 p-3">
          <div className="relative min-w-[12rem] flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-500" aria-hidden />
            <input
              type="search" value={search} aria-label={`Search ${p.title.toLowerCase()}`}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder={p.searchPlaceholder ?? "Search..."}
              className="block w-full rounded-lg border-0 py-2 pl-9 pr-3 text-sm ring-1 ring-inset ring-slate-300 placeholder:text-slate-500 focus:ring-2 focus:ring-brand-600"
            />
          </div>
          {p.filters?.map((f) =>
            f.kind === "select" ? (
              <select key={f.key} aria-label={f.label} value={filterValues[f.key] ?? ""} onChange={(e) => setFilter(f.key, e.target.value)}
                className="rounded-lg border-0 py-2 pl-3 pr-8 text-sm ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-brand-600">
                <option value="">{f.label}: all</option>
                {f.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            ) : (
              <label key={f.key} className="inline-flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm ring-1 ring-inset ring-slate-300">
                <input type="checkbox" checked={filterValues[f.key] === "true"} onChange={(e) => setFilter(f.key, e.target.checked ? "true" : "")} className="h-4 w-4 rounded text-brand-600" />
                {f.label}
              </label>
            ),
          )}
        </div>

        {list.isLoading ? <Spinner /> : list.isError ? <ErrorState error={list.error} onRetry={() => list.refetch()} /> : rows.length === 0 ? (
          filtered ? (
            <EmptyState title={`No ${p.title.toLowerCase()} match your filters`} hint="Try a different search or clear the filters."
              action={<Button onClick={() => { setSearch(""); setFilterValues({}); setPage(1); }}>Clear filters</Button>} />
          ) : (
            <EmptyState title={`No ${p.title.toLowerCase()} yet`} hint={p.emptyHint} action={<Button variant="primary" onClick={() => setEditing("new")}><Plus className="h-4 w-4" aria-hidden /> Add the first {p.noun}</Button>} />
          )
        ) : (
          <div className={clsx("relative overflow-x-auto", list.isFetching && "opacity-70 transition-opacity")}>
            <table className="min-w-full text-left text-sm">
              <caption className="sr-only">{p.title}</caption>
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                <tr>
                  {p.columns.map((c) => (
                    <th key={c.key} scope="col" className={clsx("px-4 py-2.5 font-semibold", c.hideOnMobile && "hidden md:table-cell", c.className)}
                      aria-sort={c.sortKey && (ordering === c.sortKey ? "ascending" : ordering === `-${c.sortKey}` ? "descending" : "none") || undefined}>
                      {c.sortKey ? (
                        <button type="button" onClick={() => toggleSort(c.sortKey!)} className="inline-flex items-center gap-1 uppercase hover:text-slate-900">
                          {c.header}
                          {ordering === c.sortKey ? <ChevronUp className="h-3.5 w-3.5" aria-hidden /> : ordering === `-${c.sortKey}` ? <ChevronDown className="h-3.5 w-3.5" aria-hidden /> : null}
                        </button>
                      ) : c.header}
                    </th>
                  ))}
                  <th scope="col" className="px-4 py-2.5 text-right"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50">
                    {p.columns.map((c, i) => (
                      <td key={c.key} className={clsx("px-4 py-3 align-middle", c.hideOnMobile && "hidden md:table-cell", c.className)}>
                        {i === 0 && p.detailPath ? <Link to={p.detailPath(row)} className="font-medium text-brand-700 hover:underline">{c.render(row)}</Link> : c.render(row)}
                      </td>
                    ))}
                    <td className="whitespace-nowrap px-4 py-3 text-right">
                      <div className="flex justify-end gap-1">
                        {p.rowActions?.(row)}
                        {(p.canEdit?.(row) ?? true) && <Button size="sm" variant="ghost" onClick={() => setEditing(row)} aria-label={`Edit ${p.rowLabel(row)}`}>Edit</Button>}
                        {(p.canDelete?.(row) ?? true) && <Button size="sm" variant="ghost" className="text-rose-800" onClick={() => setDeleting(row)} aria-label={`Delete ${p.rowLabel(row)}`}>Delete</Button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {count > 0 && (
          <nav aria-label="Pagination" className="flex items-center justify-between gap-3 border-t border-slate-100 px-4 py-3 text-sm text-slate-700">
            <span>{(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, count)} of {count}</span>
            <div className="flex items-center gap-2">
              <Button size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" aria-hidden /></Button>
              <span aria-live="polite">Page {page} of {pages}</span>
              <Button size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" aria-hidden /></Button>
            </div>
          </nav>
        )}
      </Card>

      {editing && (
        <FormModal
          title={editing === "new" ? `New ${p.noun}` : `Edit ${p.noun}`}
          fields={editing === "new" ? p.fields : (p.editFields ?? p.fields)}
          initial={editing === "new" ? p.newValues : (p.toFormValues ?? ((r) => r as unknown as Record<string, unknown>))(editing)}
          submitLabel={editing === "new" ? `Create ${p.noun}` : "Save changes"}
          onClose={() => setEditing(null)}
          onSubmit={async (values) => {
            await save.mutateAsync({ id: editing === "new" ? undefined : editing.id, data: values });
            toast.success(editing === "new" ? `${p.noun[0].toUpperCase()}${p.noun.slice(1)} created.` : "Changes saved.");
          }}
        />
      )}
      {deleting && (
        <ConfirmDialog
          title={`Delete ${p.noun}?`}
          message={<>This will permanently delete <strong>{p.rowLabel(deleting)}</strong>. This action cannot be undone.</>}
          onCancel={() => setDeleting(null)} onConfirm={confirmDelete} loading={remove.isPending}
        />
      )}
    </>
  );
}
