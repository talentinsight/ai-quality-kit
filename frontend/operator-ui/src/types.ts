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
  testdata_id?: string;
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
