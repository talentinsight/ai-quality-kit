export type LlmType = 'rag' | 'agent' | 'plain' | 'tools';
export type TargetMode = 'api' | 'mcp';

export type GuardrailCategory =
  | 'pii' | 'jailbreak' | 'toxicity' | 'rateCost'
  | 'latency' | 'schema' | 'resilience' | 'bias';

export interface GuardrailRule {
  id: string;
  category: GuardrailCategory;
  enabled: boolean;
  threshold?: number | string;           // e.g., 0.85 or "medium" or "strict"
  mode: 'advisory' | 'hardGate';
  applicability: 'agnostic' | 'requiresRag' | 'requiresTools';
  source?: 'safety' | 'red_team' | 'rag_reliability' | 'performance' | 'bias'; // badge
}

export interface ConnectionStatus {
  endpoint?: string;
  tokenMasked?: boolean;
  status: 'idle' | 'ok' | 'error';
  latencyMs?: number;
}

export interface RunEstimate {
  tests: number;
  p95ms: number;
  costUsd: number;
}

export interface UiPreflightState {
  llmType?: LlmType;
  targetMode?: TargetMode;
  connection?: ConnectionStatus;
  profile: 'quick' | 'standard' | 'deep';
  rules: Record<string, GuardrailRule>;     // editable map
  estimated: RunEstimate;
  dryRun: boolean;
}

export interface PreflightResult {
  status: 'PASS' | 'FAIL';
  summary: string;
  details: {
    pii: number;
    asr: string;
    p95: string;
    costPerTest: string;
  };
}
