// RAG (RAGAS-style)
export type RagKey =
  | 'rag.faithfulness'
  | 'rag.answer_relevancy'
  | 'rag.context_precision'
  | 'rag.context_recall'
  | 'rag.answer_correctness'
  | 'rag.answer_similarity'
  | 'rag.context_entities_recall'
  | 'rag.context_relevancy'
  | 'rag.prompt_robustness'
  | 'bundle.gte8'; // composite "Ground Truth Evaluation (8 Metrics)"

// Red Team
export type RedTeamKey =
  | 'red.prompt_injection'
  | 'red.context_manipulation'
  | 'red.data_exfiltration'
  | 'red.jailbreak'
  | 'red.social_engineering';

// Safety
export type SafetyKey =
  | 'safety.toxicity'
  | 'safety.hate'
  | 'safety.violence'
  | 'safety.adult'
  | 'safety.misinformation';

// Performance
export type PerfKey =
  | 'perf.cold_start'
  | 'perf.warm'
  | 'perf.throughput'
  | 'perf.stress'
  | 'perf.memory';

export type MetricKey = RagKey | RedTeamKey | SafetyKey | PerfKey;

// RAG Presets
export const NO_GT_REQUIRED: RagKey[] = [
  'rag.faithfulness',
  'rag.context_precision',
  'rag.answer_relevancy' // 3
];

export const GT_REQUIRED: RagKey[] = [
  'rag.faithfulness',
  'rag.context_precision',
  'rag.answer_relevancy',
  'rag.context_recall' // 4
];

export const GT_ADVANCED: RagKey[] = [
  'rag.answer_correctness',
  'rag.answer_similarity',
  'rag.context_entities_recall',
  'rag.context_relevancy' // +4 => total 8
];

export const RAG_OPTIONAL: RagKey[] = ['rag.prompt_robustness']; // off by default, user can add

export const RED_TEAM_ALL: RedTeamKey[] = [
  'red.prompt_injection',
  'red.context_manipulation',
  'red.data_exfiltration',
  'red.jailbreak',
  'red.social_engineering'
];

export const SAFETY_ALL: SafetyKey[] = [
  'safety.toxicity',
  'safety.hate',
  'safety.violence',
  'safety.adult',
  'safety.misinformation'
];

export const PERF_ALL: PerfKey[] = [
  'perf.cold_start',
  'perf.warm',
  'perf.throughput',
  'perf.stress',
  'perf.memory'
];

// Composite bundle expands to the 8 atomic GT metrics (do NOT run both)
export const BUNDLE_GTE8: RagKey = 'bundle.gte8';
export const BUNDLE_GTE8_EXPANDS_TO: RagKey[] = [...GT_REQUIRED, ...GT_ADVANCED];

// Selection normalization & dedupe (shared by UI and orchestrator)
export function normalizeSelected(keys: MetricKey[]): Exclude<MetricKey, 'bundle.gte8'>[] {
  const out = new Set<Exclude<MetricKey, 'bundle.gte8'>>();
  const hasBundle = keys.includes('bundle.gte8' as MetricKey);
  if (hasBundle) BUNDLE_GTE8_EXPANDS_TO.forEach(k => out.add(k));
  keys.forEach(k => { if (k !== 'bundle.gte8') out.add(k as Exclude<MetricKey, 'bundle.gte8'>); });
  return Array.from(out);
}

// Data requirements for each suite
export interface DataRequirements {
  passages: boolean;
  qaSet: boolean;
  attacks: boolean;
}

export const SUITE_DATA_REQUIREMENTS: Record<string, Partial<DataRequirements>> = {
  rag_no_gt: { passages: true },
  rag_with_gt: { passages: true, qaSet: true },
  red_team: { attacks: true },
  safety: {},
  performance: {}
};
