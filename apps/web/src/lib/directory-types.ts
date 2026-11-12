export interface SearchHit {
  id: string;
  slug: string;
  full_name: string;
  headline: string;
  sector: string;
  state: string;
  city: string;
  score: number;
  reasons: string[];
  claims: { value: string; status: "web" | "document" | "self" }[];
  is_demo: boolean;
}

export interface SearchResponse {
  query: string;
  plan: { state: string | null; sector: string | null; semantic_query: string };
  relaxed: boolean;
  embedder: string;
  took_ms: number;
  results: SearchHit[];
}

export interface Summary {
  id: string;
  slug: string;
  full_name: string;
  headline: string;
  sector: string;
  state: string;
  city: string;
}

export interface GraphNode {
  id: string;
  slug: string;
  name: string;
  sector: string;
  state: string;
  headline: string;
  demo: boolean;
}

export interface GraphLink {
  source: string;
  target: string;
  type: "alumni" | "org" | "city" | "sector" | "collab";
  weight: number;
  why: string;
}

export interface MapStats {
  total: number;
  by_state: Record<string, number>;
  by_sector: Record<string, number>;
  by_state_sector: { state: string; sector: string; count: number }[];
}

export const SECTORS = [
  "Science", "Technology", "Healthcare", "Education", "Arts & Culture", "Literature", "Sports", "Business",
  "Public Service", "Law", "Media", "Social Work", "Agriculture", "Energy", "Other",
];

export const EXAMPLE_QUERIES = [
  "clean-energy innovators in Karnataka who have collaborated with academic institutions",
  "someone who teaches classical dance to underprivileged children",
  "journalists investigating river pollution",
  "सौर ऊर्जा वैज्ञानिक",
];
