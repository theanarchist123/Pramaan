// Mirrors backend/app/schemas.py — keep in sync (Phase 6 generates these from OpenAPI).

export type ClaimStatus = "self" | "web" | "document" | "human" | "issuer";
export type ProfileStatus = "draft" | "pending_review" | "approved" | "rejected";

export interface Evidence {
  id: string;
  kind: "chat" | "web" | "document";
  url: string;
  quote: string;
}

export interface Claim {
  id: string;
  field: string;
  value: string;
  year: number | null;
  status: ClaimStatus;
  confidence: number;
  evidence: Evidence[];
}

export interface Profile {
  id: string;
  slug: string;
  full_name: string;
  headline: string;
  sector: string;
  state: string;
  city: string;
  bio: string;
  languages: string[];
  institutions: string[];
  photo_url: string;
  custom: Record<string, unknown>;
  status: ProfileStatus;
  /** How an approval was reached; the banner is worded from this, never from free text. */
  decision_basis?: "" | "automation" | "reviewer";
  wikidata_qid?: string;
  is_demo: boolean;
  created_at: string;
  claims: Claim[];
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: "person" | "delegate" | "admin";
  email_verified?: boolean;
}

export interface TurnOut {
  reply: string;
  detected_language: string;
  profile: Profile;
  new_claims: Claim[];
  missing: string[];
  ready_to_submit: boolean;
  run_id: string;
}

export interface DraftClaim {
  field: string;
  value: string;
  year: number | null;
  source_quote: string;
}

export interface DiscoveryDraft {
  chosen_index: number;
  confidence: number;
  headline: string;
  sector: string;
  state: string;
  city: string;
  claims: DraftClaim[];
  reason: string;
}

export interface DiscoveryResult {
  found: boolean;
  source_title: string;
  source_url: string;
  draft: DiscoveryDraft | null;
  run_id: string;
}

export interface AgentEvent {
  id: number | null;
  run_id: string;
  workflow: string;
  profile_id: string | null;
  agent: string;
  kind: "thought" | "tool" | "result" | "handoff" | "warning" | "error" | "run_finished";
  message: string;
  data: Record<string, unknown>;
  confidence: number | null;
  ts: string;
}

export interface AgentInfo {
  name: string;
  kind?: "llm" | "hybrid" | "service";
  role: string;
  does: string;
  replaces: string;
}

export interface DocumentResult {
  document_id: string;
  sent_to_review?: boolean;
  extracted: {
    doc_type: string;
    holder_name: string;
    issuer: string;
    title: string;
    issued_year: number | null;
    legibility: number;
    notes: string;
  };
  match_score: number;
  flags: string[];
  claims_verified_by_document: number;
}
