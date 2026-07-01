export type ContradictionKind = "intra_source" | "inter_source" | "legal";

export type ContradictionSeverity = "low" | "medium" | "high";

export interface Contradiction {
  kind: ContradictionKind;
  confidence: number;
  severity: ContradictionSeverity;
  claim_excerpt: string;
  claim_source: string;
  conflicts_with_excerpt: string;
  conflicts_with_source: string;
  explanation: string;
}

export interface ContradictionClaim {
  id: string;
  source: string;
  speaker: string;
  excerpt: string;
}

export interface ContradictionThread {
  id: string;
  kind: ContradictionKind;
  severity: ContradictionSeverity;
  from_claim_id: string;
  to_claim_id: string;
  from_excerpt: string;
  to_excerpt: string;
  explanation: string;
  confidence: number;
}

export interface ContradictionResult {
  contradictions: Contradiction[];
  claims: ContradictionClaim[];
  threads: ContradictionThread[];
  total_intra: number;
  total_inter: number;
  total_legal: number;
  summary: string;
  key_claims: string[];
  evidence_count: number;
  entity: string;
}

export const CONTRADICTION_KIND_COLORS: Record<ContradictionKind, string> = {
  intra_source: "#ef4444",
  inter_source: "#eab308",
  legal: "#3b82f6",
};

export const CONTRADICTION_KIND_LABELS: Record<ContradictionKind, string> = {
  intra_source: "Intra-Source",
  inter_source: "Inter-Source",
  legal: "Legal",
};

export const CONTRADICTION_SEVERITY_COLORS: Record<
  ContradictionSeverity,
  string
> = {
  low: "#22c55e",
  medium: "#eab308",
  high: "#ef4444",
};
