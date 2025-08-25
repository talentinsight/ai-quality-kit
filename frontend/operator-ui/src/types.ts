export type Provider = "openai"|"anthropic"|"gemini"|"custom_rest"|"mock";

export type TestSuite =
  | "rag_quality"
  | "red_team"
  | "safety"
  | "performance"
  | "regression"
  | "resilience"
  | "compliance_smoke"
  | "bias_smoke";

export interface ProviderLimits {
  requests_per_minute?: number;
  tokens_per_minute?: number;
  max_concurrent?: number;
  tier?: string;
  auto_detect?: boolean;
}

export interface ResilienceOptions {
  mode: "synthetic" | "passive";
  samples: number;
  timeout_ms: number;
  retries: number;
  concurrency: number;
  queue_depth: number;
  circuit: {
    fails: number;
    reset_s: number;
  };
  provider_limits?: ProviderLimits;
}

export interface ComplianceSmokeOptions {
  pii_patterns_file: string;
  scan_fields: string[];
  rbac_matrix: {
    [role: string]: string[];
  };
}

export interface BiasSmokeOptions {
  groups: string[][];
  max_pairs: number;
  parity_metric: "refusal_rate" | "length_delta";
  parity_threshold: number;
}

export interface OrchestratorRequest {
  target_mode: "api"|"mcp";
  api_base_url?: string;
  api_bearer_token?: string;
  mcp_server_url?: string;
  suites: TestSuite[];
  thresholds?: Record<string, number|string|boolean>;
  options?: { 
    provider?: Provider; 
    model?: string; 
    top_k?: number;
    qa_sample_size?: number;
    attack_mutators?: number;
    perf_repeats?: number;
    resilience?: ResilienceOptions;
    compliance_smoke?: ComplianceSmokeOptions;
    bias_smoke?: BiasSmokeOptions;
  };
  testdata_id?: string;
  use_expanded?: boolean;
  run_id?: string;  // For cancel functionality
  shards?: number;
  shard_id?: number;
}

export interface OrchestratorResult {
  run_id: string;
  artifacts: { json_path: string; xlsx_path: string };
  summary?: Record<string, unknown>;
  counts?: Record<string, unknown>;
}

// Test Data Intake types
export type ArtifactType = 'passages' | 'qaset' | 'attacks' | 'schema';

export interface TestDataUploadResponse {
  testdata_id: string;
  artifacts: string[];
  counts: Record<string, number>;
}

export interface TestDataUrlRequest {
  urls: Partial<Record<ArtifactType, string>>;
}

export interface TestDataPasteRequest {
  passages?: string;
  qaset?: string;
  attacks?: string;
  schema?: string;
}

export interface ArtifactInfo {
  present: boolean;
  count?: number;
  sha256?: string;
}

export interface TestDataMeta {
  testdata_id: string;
  created_at: string;
  expires_at: string;
  artifacts: Record<ArtifactType, ArtifactInfo>;
}

export interface ApiError {
  detail: string;
  validation_errors?: Array<{
    artifact: string;
    error: {
      field: string;
      message: string;
      line_number?: number;
    };
  }>;
}
