// Shapes of the graph state the UI shows (mirrors agent/handoffs.py). RunDetail.state is open-ended
// in OpenAPI because it is a LangGraph checkpoint, so these are declared here.

export interface Evidence {
  evidence_id?: string;
  type: string;
  title: string;
  date?: string | null;
  outcome?: string | null;
  project_id?: string | null;
  text: string;
}

export interface RequirementFit {
  requirement: string;
  coverage: "strong" | "partial" | "missing";
  evidence_ids: string[];
  reason: string;
}

export interface FitReport {
  score: number;
  matched_skills: string[];
  missing_skills: string[];
  evidence_ids: string[];
  requirements: RequirementFit[];
}

export interface RiskReport {
  score: number;
  flags: string[];
  explanation: string;
  client_summary: string;
}

export interface JobSpec {
  title: string;
  deliverables: string[];
  requirements: string[];
  hidden_needs: string[];
  red_flags: string[];
  screening_questions: string[];
  timeline?: string | null;
  budget_min?: number | null;
  budget_max?: number | null;
  payment_type?: string | null;
}

export interface PriceQuote {
  amount: number;
  unit: "usd_total" | "usd_per_hour";
  band_low: number;
  band_high: number;
  connects_cost: number;
  worth_connects: boolean;
  rationale: string;
}

export interface Claim {
  claim: string;
  evidence_ids: string[];
  verdict: "supported" | "partly_supported" | "unsupported";
  note: string;
}

export interface Critique {
  verdict: "pass" | "revise" | "unavailable";
  scores: Record<string, number> | null;
  issues: string[];
}

export interface ProposalDraft {
  cover_letter: string;
  screening_answers: string[];
  evidence_ids: string[];
  bid_amount?: number | null;
  version: number;
  unsupported_before?: number;
  claims_total?: number;
}

export interface Preview {
  dry_run: boolean;
  sent: boolean;
  cover_letter: string;
  screening_answers: string[];
  bid_amount: number;
  bid_type: string;
  connects_cost: number;
  balance_before: number;
  balance_after: number;
  policy_violations: { rule_id: string; description: string }[];
}

export interface ProposalApproval {
  kind: "proposal_approval";
  job: { job_id: string; title: string; budget_min?: number | null; budget_max?: number | null; payment_type?: string };
  draft: ProposalDraft;
  claims: Claim[];
  evidence: Record<string, Evidence>;
  risk: RiskReport;
  fit: FitReport;
  price: PriceQuote;
  compliance: { status: string; violations: string[]; reason: string } | null;
  preview: Preview;
}

export interface MessageApproval {
  kind: "message_approval";
  thread_id: string;
  job_title: string;
  messages: { sender: "client" | "freelancer"; body: string; at: string }[];
  intent: { intent: string; wants_call: boolean; summary: string; flags: string[] };
  draft: { body: string; intent: string; offered_slots: { start_local: string; start_utc: string }[]; version: number };
  compliance: { status: string; fixed: string[] } | null;
}

export interface BidState {
  job?: { job_id: string; title: string; description: string; category?: string; client_id: string };
  job_spec?: JobSpec;
  risk_report?: RiskReport;
  fit_report?: FitReport;
  evidence?: Record<string, Evidence>;
  decision?: { action: string; reasons: string[] };
  price_quote?: PriceQuote;
  proposal_draft?: ProposalDraft;
  claims?: Claim[];
  critiques?: Critique[];
  compliance_verdict?: { status: string; violations: string[]; reason: string };
  submission?: { status: string; connects_cost: number; balance_after: number };
  status?: string;
  status_reason?: string;
  steps?: number;
  tokens?: number;
  errors?: string[];
}

export interface RunEvent {
  thread_id: string;
  type: "node" | "awaiting_approval" | "finished";
  node?: string;
  summary?: string;
  ms?: number;
  tokens?: number;
  status?: string | null;
  status_reason?: string | null;
  at?: string;
}
