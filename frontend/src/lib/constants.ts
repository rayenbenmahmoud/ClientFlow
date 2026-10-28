import type { DealStage, InteractionType, LeadSource, LeadStatus, TaskPriority } from "../api/types";

export const STAGES: { value: DealStage; label: string }[] = [
  { value: "new", label: "New" },
  { value: "qualified", label: "Qualified" },
  { value: "proposal", label: "Proposal" },
  { value: "negotiation", label: "Negotiation" },
  { value: "won", label: "Won" },
  { value: "lost", label: "Lost" },
];
export const OPEN_STAGES: DealStage[] = ["new", "qualified", "proposal", "negotiation"];

/** Mirrors Deal.ALLOWED_TRANSITIONS on the server. Used only for UI hints; the API is the authority. */
export const ALLOWED_TRANSITIONS: Record<DealStage, DealStage[]> = {
  new: ["qualified", "lost"],
  qualified: ["new", "proposal", "lost"],
  proposal: ["qualified", "negotiation", "lost"],
  negotiation: ["proposal", "won", "lost"],
  won: [],
  lost: ["new"],
};

export const stageLabel = (s: DealStage) => STAGES.find((x) => x.value === s)?.label ?? s;

export const LEAD_STATUSES: { value: LeadStatus; label: string }[] = [
  { value: "new", label: "New" },
  { value: "contacted", label: "Contacted" },
  { value: "qualified", label: "Qualified" },
  { value: "unqualified", label: "Unqualified" },
  { value: "converted", label: "Converted" },
];
export const LEAD_SOURCES: { value: LeadSource; label: string }[] = [
  { value: "website", label: "Website" },
  { value: "referral", label: "Referral" },
  { value: "cold_outreach", label: "Cold outreach" },
  { value: "event", label: "Event" },
  { value: "social", label: "Social media" },
  { value: "partner", label: "Partner" },
  { value: "other", label: "Other" },
];
export const PRIORITIES: { value: TaskPriority; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];
export const INTERACTION_TYPES: { value: InteractionType; label: string }[] = [
  { value: "call", label: "Call" },
  { value: "meeting", label: "Meeting" },
  { value: "email", label: "Email" },
  { value: "note", label: "Note" },
];

/** Badge palettes: every pairing is >= 4.5:1 contrast (Tailwind 100 background with 800/900 text). */
export const STAGE_TONE: Record<DealStage, string> = {
  new: "bg-slate-100 text-slate-800 ring-slate-300",
  qualified: "bg-sky-100 text-sky-900 ring-sky-300",
  proposal: "bg-violet-100 text-violet-900 ring-violet-300",
  negotiation: "bg-amber-100 text-amber-900 ring-amber-300",
  won: "bg-emerald-100 text-emerald-900 ring-emerald-300",
  lost: "bg-rose-100 text-rose-900 ring-rose-300",
};
export const STAGE_BAR: Record<DealStage, string> = {
  new: "#64748b",
  qualified: "#0284c7",
  proposal: "#7c3aed",
  negotiation: "#d97706",
  won: "#059669",
  lost: "#e11d48",
};
export const LEAD_TONE: Record<LeadStatus, string> = {
  new: "bg-slate-100 text-slate-800 ring-slate-300",
  contacted: "bg-sky-100 text-sky-900 ring-sky-300",
  qualified: "bg-emerald-100 text-emerald-900 ring-emerald-300",
  unqualified: "bg-rose-100 text-rose-900 ring-rose-300",
  converted: "bg-violet-100 text-violet-900 ring-violet-300",
};
export const PRIORITY_TONE: Record<TaskPriority, string> = {
  low: "bg-slate-100 text-slate-800 ring-slate-300",
  medium: "bg-amber-100 text-amber-900 ring-amber-300",
  high: "bg-rose-100 text-rose-900 ring-rose-300",
};
export const SOURCE_COLORS = ["#4f46e5", "#0284c7", "#059669", "#d97706", "#e11d48", "#7c3aed", "#64748b"];
