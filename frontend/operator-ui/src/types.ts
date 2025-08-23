export type Provider = "openai"|"anthropic"|"gemini"|"custom_rest"|"mock";

export type TestSuite =
  | "rag_quality"
  | "red_team"
  | "safety"
  | "performance"
  | "regression"
  | "gibberish";

export interface OrchestratorRequest {
  target_mode: "api"|"mcp";
  api_base_url?: string;
  api_bearer_token?: string;
  suites: TestSuite[];
  thresholds?: Record<string, number|string|boolean>;
  options?: { 
    provider?: Provider; 
    model?: string; 
    top_k?: number;
    qa_sample_size?: number;
    attack_mutators?: number;
    perf_repeats?: number;
  };
}

export interface OrchestratorResult {
  run_id: string;
  artifacts: { json_path: string; xlsx_path: string };
  summary?: Record<string, unknown>;
  counts?: Record<string, unknown>;
}
