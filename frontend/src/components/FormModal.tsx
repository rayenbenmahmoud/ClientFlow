import { useState, type FormEvent } from "react";
import clsx from "clsx";
import { ApiError } from "../api/client";
import { Button, Modal } from "./ui";

export interface Option { value: string | number; label: string }
export interface FieldDef {
  name: string;
  label: string;
  type?: "text" | "email" | "tel" | "url" | "number" | "date" | "datetime-local" | "textarea" | "select" | "tags";
  required?: boolean;
  nullable?: boolean; // empty value is sent as null
  options?: Option[];
  placeholder?: string;
  help?: string;
  full?: boolean;
  min?: string | number;
  step?: string;
  maxLength?: number;
  tagColors?: Record<string | number, string>;
}
type Values = Record<string, unknown>;

export const inputClass = "block w-full rounded-lg border-0 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 placeholder:text-slate-500 focus:ring-2 focus:ring-brand-600 disabled:bg-slate-50";

export function FormModal({
  title, fields, initial, submitLabel = "Save", onSubmit, onClose, intro,
}: {
  title: string;
  fields: FieldDef[];
  initial: Values;
  submitLabel?: string;
  onSubmit: (values: Values) => Promise<unknown>;
  onClose: () => void;
  intro?: string;
}) {
  const [values, setValues] = useState<Values>(initial);
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [banner, setBanner] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const set = (name: string, value: unknown) => setValues((v) => ({ ...v, [name]: value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    setBanner([]);
    const payload: Values = {};
    for (const f of fields) {
      const v = values[f.name];
      payload[f.name] = f.type === "tags" ? (v ?? []) : v === "" && f.nullable ? null : v;
      if (f.type === "datetime-local" && typeof v === "string" && v) payload[f.name] = new Date(v).toISOString();
    }
    try {
      await onSubmit(payload);
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        const known = new Set(fields.map((f) => f.name));
        const unknown = Object.entries(err.fieldErrors).filter(([k]) => !known.has(k));
        setErrors(Object.fromEntries(Object.entries(err.fieldErrors).filter(([k]) => known.has(k))));
        setBanner([...err.nonFieldErrors, ...unknown.map(([k, m]) => `${k.replace(/_/g, " ")}: ${m.join(" ")}`)]);
        if (!err.nonFieldErrors.length && !Object.keys(err.fieldErrors).length) setBanner([err.message]);
      } else setBanner(["Unexpected error. Please try again."]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={title} onClose={onClose} wide>
      <form onSubmit={submit} noValidate={false} className="space-y-4">
        {intro && <p className="text-sm text-slate-600">{intro}</p>}
        {banner.length > 0 && (
          <div role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-900 ring-1 ring-rose-300">
            {banner.map((m) => <p key={m}>{m}</p>)}
          </div>
        )}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {fields.map((f, idx) => {
            const id = `f-${f.name}`;
            const err = errors[f.name];
            const common = {
              id, name: f.name, required: f.required, "aria-invalid": err ? true : undefined,
              "aria-describedby": err ? `${id}-err` : f.help ? `${id}-help` : undefined,
              className: clsx(inputClass, err && "ring-rose-500"),
            };
            const v = values[f.name];
            return (
              <div key={f.name} className={clsx((f.full || f.type === "textarea" || f.type === "tags") && "sm:col-span-2")}>
                <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-800">
                  {f.label}{f.required && <span className="text-rose-700" aria-hidden> *</span>}
                </label>
                {f.type === "textarea" ? (
                  <textarea {...common} rows={3} maxLength={f.maxLength} value={String(v ?? "")} onChange={(e) => set(f.name, e.target.value)} placeholder={f.placeholder} />
                ) : f.type === "select" ? (
                  <select {...common} value={String(v ?? "")} onChange={(e) => set(f.name, e.target.value === "" ? "" : isNaN(Number(e.target.value)) || typeof f.options?.[0]?.value === "string" ? e.target.value : Number(e.target.value))}>
                    {!f.required && <option value="">None</option>}
                    {f.required && v === "" && <option value="">Select...</option>}
                    {f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                ) : f.type === "tags" ? (
                  <div id={id} className="flex flex-wrap gap-2" role="group" aria-label={f.label}>
                    {f.options?.length ? f.options.map((o) => {
                      const sel = ((v as number[]) ?? []).includes(o.value as number);
                      return (
                        <button key={o.value} type="button" aria-pressed={sel}
                          onClick={() => set(f.name, sel ? (v as number[]).filter((x) => x !== o.value) : [...((v as number[]) ?? []), o.value])}
                          className={clsx("rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset", sel ? "bg-brand-600 text-white ring-brand-600" : "bg-white text-slate-800 ring-slate-300 hover:bg-slate-50")}>
                          {o.label}
                        </button>
                      );
                    }) : <span className="text-sm text-slate-500">No tags yet.</span>}
                  </div>
                ) : (
                  <input {...common} type={f.type ?? "text"} min={f.min} step={f.step} maxLength={f.maxLength} placeholder={f.placeholder}
                    value={String(v ?? "")} onChange={(e) => set(f.name, e.target.value)} data-autofocus={idx === 0 ? "" : undefined} />
                )}
                {f.help && !err && <p id={`${id}-help`} className="mt-1 text-xs text-slate-600">{f.help}</p>}
                {err && <p id={`${id}-err`} className="mt-1 text-xs text-rose-800">{err.join(" ")}</p>}
              </div>
            );
          })}
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-100 pt-4">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" loading={busy}>{submitLabel}</Button>
        </div>
      </form>
    </Modal>
  );
}
