export type Role = "admin" | "manager" | "sales_rep";
export type DealStage = "new" | "qualified" | "proposal" | "negotiation" | "won" | "lost";
export type LeadStatus = "new" | "contacted" | "qualified" | "unqualified" | "converted";
export type LeadSource = "website" | "referral" | "cold_outreach" | "event" | "social" | "partner" | "other";
export type TaskPriority = "low" | "medium" | "high";
export type InteractionType = "call" | "meeting" | "email" | "note";

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: Role;
  is_active: boolean;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Tag { id: number; name: string; color: string }

export interface Company {
  id: number;
  name: string;
  industry: string;
  website: string;
  email: string;
  phone: string;
  address: string;
  city: string;
  country: string;
  notes: string;
  owner: number | null;
  owner_name: string | null;
  contact_count?: number;
  deal_count?: number;
  created_at: string;
}

export interface Contact {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone: string;
  job_title: string;
  company: number | null;
  company_name: string | null;
  notes: string;
  tags: Tag[];
  owner: number | null;
  owner_name: string | null;
  created_at: string;
}

export interface Lead {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone: string;
  company_name: string;
  job_title: string;
  source: LeadSource;
  source_label: string;
  status: LeadStatus;
  status_label: string;
  owner: number;
  owner_name: string;
  follow_up_date: string | null;
  estimated_value: string | null;
  notes: string;
  is_overdue: boolean;
  overdue_flagged_at: string | null;
  converted_deal: number | null;
  created_at: string;
}

export interface Deal {
  id: number;
  title: string;
  amount: string;
  stage: DealStage;
  stage_label: string;
  expected_close_date: string | null;
  owner: number;
  owner_name: string;
  company: number;
  company_name: string;
  contact: number | null;
  contact_name: string | null;
  lost_reason: string;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DealHistoryEntry {
  id: number;
  from_stage: DealStage | "";
  from_stage_label: string;
  to_stage: DealStage;
  to_stage_label: string;
  changed_by_name: string | null;
  changed_at: string;
}

export interface PipelineColumn {
  stage: DealStage;
  label: string;
  count: number;
  total: string;
  deals: Deal[];
}

export interface Task {
  id: number;
  title: string;
  description: string;
  due_date: string;
  status: "open" | "done";
  status_label: string;
  priority: TaskPriority;
  priority_label: string;
  assignee: number;
  assignee_name: string;
  lead: number | null;
  lead_name: string | null;
  deal: number | null;
  deal_title: string | null;
  contact: number | null;
  contact_name: string | null;
  is_overdue: boolean;
  completed_at: string | null;
  auto_created: boolean;
}

export interface Interaction {
  id: number;
  type: InteractionType;
  type_label: string;
  subject: string;
  notes: string;
  occurred_at: string;
  contact: number | null;
  contact_name: string | null;
  company: number | null;
  company_name: string | null;
  deal: number | null;
  deal_title: string | null;
  lead: number | null;
  lead_name: string | null;
  created_by: number | null;
  created_by_name: string | null;
  is_system: boolean;
}

export interface AppNotification {
  id: number;
  kind: string;
  title: string;
  message: string;
  link: string;
  is_read: boolean;
  created_at: string;
}

export interface Dashboard {
  scope: "all" | "mine";
  kpis: {
    open_leads: number;
    overdue_leads: number;
    active_deals: number;
    pipeline_value: string;
    won_this_month_value: string;
    won_this_month_count: number;
    tasks_due_today: number;
    tasks_overdue: number;
    tasks_open: number;
  };
  pipeline: { stage: DealStage; label: string; count: number; value: string }[];
  leads_by_source: { source: LeadSource; label: string; count: number }[];
  upcoming_tasks: Task[];
  overdue_leads: Lead[];
  recent_activities: Interaction[];
}
