export type Provider = "openai"|"anthropic"|"gemini"|"custom_rest"|"synthetic"|"mock";

export type TestSuite =
  | "rag_quality"
  | "rag_reliability_robustness"
  | "rag_prompt_robustness"
  | "rag_structure_eval"
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

export interface RagReliabilityRobustnessConfig {
  faithfulness_eval: { enabled: boolean };
  context_recall: { enabled: boolean };
  answer_relevancy: { enabled: boolean };
  context_precision: { enabled: boolean };
  answer_correctness: { enabled: boolean };
  ground_truth_eval: { enabled: boolean };
  prompt_robustness: { 
    enabled: boolean; 
    prompt_source?: string; 
    include_prompts?: boolean;
  };
}

export interface CompareWithConfig {
  enabled: boolean;
  baseline?: {
    preset?: Provider;
    model?: string;
    decoding?: {
      temperature?: number;
      top_p?: number;
      max_tokens?: number;
    };
  };
  auto_select?: {
    enabled: boolean;
    strategy: "same_or_near_tier";
    headroom_run?: boolean;
    hint_tier?: "economy" | "balanced" | "premium";
  };
  carry_over?: {
    use_contexts_from_primary: boolean;
    require_non_empty: boolean;
    max_context_items?: number;
    heading?: string;
    joiner?: string;
  };
  target_display_name?: string;
}

export interface MCPToolConfig {
  name: string;
  arg_mapping: {
    question_key?: string;
    system_key?: string;
    contexts_key?: string;
    topk_key?: string;
  };
  shape: "messages" | "prompt";
  static_args?: Record<string, any>;
}

export interface MCPExtractionConfig {
  output_type: "text" | "json";
  output_jsonpath?: string; // required when output_type === "json"
  contexts_jsonpath?: string;
  request_id_jsonpath?: string;
}

export interface MCPAuthConfig {
  bearer?: string;
  headers?: Record<string, string>;
}

export interface MCPTimeoutConfig {
  connect_ms?: number;
  call_ms?: number;
}

export interface MCPRetryConfig {
  retries?: number;
  backoff_ms?: number;
}

export interface MCPTargetConfig {
  endpoint: string;
  auth?: MCPAuthConfig;
  tool: MCPToolConfig;
  extraction: MCPExtractionConfig;
  timeouts?: MCPTimeoutConfig;
  retry?: MCPRetryConfig;
}

export interface OrchestratorRequest {
  target_mode: "api"|"mcp";
  api_base_url?: string;
  api_bearer_token?: string;
  mcp_server_url?: string;
  provider?: Provider;  // Top-level provider
  model?: string;       // Top-level model
  
  // New structured target configuration
  target?: {
    mode: "api" | "mcp";
    mcp?: MCPTargetConfig;
  };
  suites: TestSuite[];
  thresholds?: Record<string, number|string|boolean>;
  options?: { 
    provider?: Provider; 
    model?: string; 
    top_k?: number;
    qa_sample_size?: number;
    attack_mutators?: number;
    perf_repeats?: number;
    selected_tests?: Record<string, string[]>;
    suite_configs?: Record<string, any>;
    resilience?: ResilienceOptions;
    compliance_smoke?: ComplianceSmokeOptions;
    bias_smoke?: BiasSmokeOptions;
    rag_reliability_robustness?: RagReliabilityRobustnessConfig;
  };
  testdata_id?: string;
  use_expanded?: boolean;
  use_ragas?: boolean;  // Enable Ragas evaluation
  run_id?: string;  // For cancel functionality
  shards?: number;
  shard_id?: number;
  
  // Phase-RAG extensions
  server_url?: string;  // For API mode
  mcp_endpoint?: string;  // For MCP mode
  llm_option?: string;  // Default to RAG
  ground_truth?: string;  // "available" | "not_available"
  determinism?: Record<string, any>;  // temperature, top_p, seed overrides
  volume?: Record<string, any>;  // Volume controls
  
  // Retrieval metrics extension
  retrieval?: {
    contexts_jsonpath?: string;
    top_k?: number;
    note?: string;
  };
  
  // Run profile
  profile?: "smoke" | "full";
  
  // Compare Mode (additive, non-breaking)
  compare_with?: CompareWithConfig;
}

export interface OrchestratorResult {
  run_id: string;
  artifacts: { json_path: string; xlsx_path: string; html_path?: string };
  summary?: Record<string, unknown>;
  counts?: Record<string, unknown>;
}

export interface SubSuitePlan {
  enabled: boolean;
  planned_items: number;
}

export interface OrchestratorPlan {
  suite: string;
  sub_suites: Record<string, SubSuitePlan>;
  total_planned: number;
  skips: Array<{ sub_suite: string; reason: string }>;
  alias_used: boolean;
}

export interface OrchestratorStartResponse {
  run_id: string;
  status: string;
  message: string;
}

// Test Data Intake types
export type ArtifactType = 'passages' | 'qaset' | 'attacks' | 'schema';

export interface TestDataUploadResponse {
  testdata_id: string;
  artifacts: string[];
  counts: Record<string, number>;
  // Enhanced response fields for RAG integration
  manifest?: Record<string, any>;
  stats?: Record<string, any>;
  warnings?: string[];
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
