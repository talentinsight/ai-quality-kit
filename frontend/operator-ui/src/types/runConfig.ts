export type TargetMode = 'api' | 'mcp';
export type Provider = 'openai' | 'anthropic' | 'gemini' | 'custom_rest' | 'synthetic' | 'mock';

export interface Thresholds {
  faithfulness_min?: number;
  context_recall_min?: number;
  toxicity_max?: number;
}

export interface Volumes {
  qa_sample_size?: number;
  attack_mutators?: number;
  perf_repeats?: number;
  profile?: 'smoke' | 'full' | 'red_team_heavy' | null;
}

export interface ResilienceOptions {
  mode?: 'passive' | 'active';
  samples?: number;
  timeout_ms?: number;
  retries?: number;
  concurrency?: number;
  queue_depth?: number;
  circuit_fails?: number;
  circuit_reset_s?: number;
  provider_rate_limits?: {
    auto_detect_limits?: boolean;
    requests_per_min?: number | null;
    tokens_per_min?: number | null;
    max_concurrent?: number | null;
    provider_tier?: string | null;
  };
}

export interface ComplianceOptions {
  pii_patterns_file?: string | null;
  enable_pii_scanning?: boolean;
}

export interface BiasOptions {
  max_pairs?: number;
  groups_csv?: string; // "female|male;young|elderly"
}

export interface IntakeBlob {
  source: 'upload' | 'url' | 'paste' | 'zip';
  payload: string; // raw text or URL; for zip use base64
}

export interface TestDataIntake {
  passages?: IntakeBlob | null;
  qaset?: IntakeBlob | null;
  attacks?: IntakeBlob | null;
  schema?: IntakeBlob | null;
}

export interface RunConfig {
  target_mode: TargetMode | null;
  url?: string;               // unified URL for both API and MCP
  bearer_token?: string;
  provider?: Provider | null; // required only when target_mode==='api'
  model?: string | null;      // required for openai/anthropic/gemini/mock
  test_suites: string[];      // ['rag_quality','red_team','safety','performance','regression','resilience','compliance_smoke','bias_smoke']
  thresholds?: Thresholds;
  volumes?: Volumes;
  resilience?: ResilienceOptions;
  compliance?: ComplianceOptions;
  bias?: BiasOptions;
  testdata_id?: string | null;
  test_data?: TestDataIntake | null;
}

export type StepId =
  | 'mode' | 'base' | 'auth'
  | 'provider' | 'model'
  | 'suites' | 'thresholds' | 'volumes'
  | 'resilience' | 'compliance' | 'bias'
  | 'testdataId' | 'testData' | 'summary';

export interface Message {
  id: string;
  type: 'assistant' | 'user';
  content: string;
  timestamp: Date;
}

export interface ValidationError {
  field: string;
  message: string;
}
