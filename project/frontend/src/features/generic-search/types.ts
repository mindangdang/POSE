export type Criterion = {
  id: string;
  attribute: string;
  operator: string;
  value: string | number | boolean | string[];
  weight: number;
  confidence: number;
  is_hard_constraint: boolean;
  source: 'explicit' | 'inferred' | 'user_memory' | 'session_context';
};

export type Preference = {
  id: string;
  attribute: string;
  value: string;
  polarity: 'positive' | 'negative';
  weight: number;
  confidence: number;
  scope: 'session' | 'domain' | 'global';
  domain?: string | null;
  source: 'explicit' | 'inferred';
};

export type Result = {
  document: {
    document_id: string;
    canonical_url: string;
    title: string;
    snippet: string;
    content: string;
    source: string;
    metadata: Record<string, unknown>;
  };
  rank: number;
  score: number;
  verified: boolean;
  reason: string;
  satisfied_criteria: string[];
  uncertain_criteria: string[];
  evaluations: Array<{
    criterion_id: string;
    status: 'satisfied' | 'violated' | 'unknown';
    evidence_excerpt?: string | null;
  }>;
};

export type SearchState = {
  search_id: string;
  status: string;
  intent?: {
    objective: string;
    rewritten_query: string;
    criteria: Criterion[];
    exclusions: Criterion[];
    unresolved_information: string[];
    clarification_required: boolean;
  };
  preferences_used?: string[];
  verified_results?: Result[];
  unverified_results?: Result[];
  excluded_result_count?: number;
  errors?: string[];
  warnings?: string[];
  events?: Array<{ type: string; search_id: string; sequence: number }>;
};

export const FEEDBACK_REASONS = [
  '검색 목적과 맞지 않음',
  '특정 조건 불충족',
  '이미 알고 있는 정보',
  '신뢰하기 어려운 정보',
  '개인 취향과 맞지 않음',
  '기타',
];
