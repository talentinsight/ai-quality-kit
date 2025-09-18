import { MetricKey, NO_GT_REQUIRED, GT_REQUIRED, GT_ADVANCED, RED_TEAM_ALL, SAFETY_ALL, PERF_ALL, normalizeSelected } from '../types/metrics';

// Convert internal test IDs to metric keys
const TEST_ID_TO_METRIC: Record<string, MetricKey> = {
  // RAG - RAG Metrics Spec compliant IDs
  'faithfulness': 'rag.faithfulness',
  'context_recall': 'rag.context_recall',
  'answer_relevancy': 'rag.answer_relevancy',
  'context_precision': 'rag.context_precision',
  'answer_correctness': 'rag.answer_correctness',
  'answer_similarity': 'rag.answer_similarity',
  'context_entities_recall': 'rag.context_entities_recall',
  'context_relevancy': 'rag.context_relevancy',
  'prompt_robustness': 'rag.prompt_robustness',

  
  // Red Team
  'prompt_injection': 'red.prompt_injection',
  'context_manipulation': 'red.context_manipulation',
  'data_extraction': 'red.data_exfiltration',
  'jailbreak_attempts': 'red.jailbreak',
  'social_engineering': 'red.social_engineering',
  
  // Safety
  'toxicity_detection': 'safety.toxicity',
  'hate_speech': 'safety.hate',
  'violence_content': 'safety.violence',
  'adult_content': 'safety.adult',
  'misinformation': 'safety.misinformation',
  
  // Performance
  'cold_start_latency': 'perf.cold_start',
  'warm_performance': 'perf.warm',
  'throughput_testing': 'perf.throughput',
  'stress_testing': 'perf.stress',
  'memory_usage': 'perf.memory'
};

// Convert metric keys to internal test IDs
const METRIC_TO_TEST_ID: Record<MetricKey, string> = Object.entries(TEST_ID_TO_METRIC).reduce(
  (acc, [testId, metricKey]) => ({ ...acc, [metricKey]: testId }),
  {} as Record<MetricKey, string>
);

// Convert selected test IDs to metric keys
export function convertTestIdsToMetrics(selectedTests: Record<string, string[]>): MetricKey[] {
  const metrics: MetricKey[] = [];
  Object.values(selectedTests).flat().forEach(testId => {
    const metric = TEST_ID_TO_METRIC[testId];
    if (metric) metrics.push(metric);
  });
  return metrics;
}

// Convert metric keys to test IDs
export function convertMetricsToTestIds(metrics: MetricKey[]): Record<string, string[]> {
  const testIds: Record<string, string[]> = {
    rag_reliability_robustness: [],
    red_team: [],
    safety: [],
    performance: []
  };
  
  metrics.forEach(metric => {
    const testId = METRIC_TO_TEST_ID[metric];
    if (!testId) return;
    
    // Map to appropriate suite
    if (metric.startsWith('rag.')) {
      testIds.rag_reliability_robustness.push(testId);
    } else if (metric.startsWith('red.')) {
      testIds.red_team.push(testId);
    } else if (metric.startsWith('safety.')) {
      testIds.safety.push(testId);
    } else if (metric.startsWith('perf.')) {
      testIds.performance.push(testId);
    }
  });
  
  return testIds;
}

// Get default test selection based on RAG mode and GT availability
export function getDefaultRagSelection(hasGroundTruth: boolean): MetricKey[] {
  const ragMetrics = hasGroundTruth 
    ? [...GT_REQUIRED, ...GT_ADVANCED]  // 8 metrics with GT
    : NO_GT_REQUIRED;                   // 3 metrics without GT
    
  // Always include all tests from other suites
  return [
    ...ragMetrics,
    ...RED_TEAM_ALL,
    ...SAFETY_ALL,
    ...PERF_ALL
  ];
}

// Check if a test should be disabled due to bundle selection
// Note: Bundle functionality removed, this function now always returns false
export function isTestDisabledByBundle(testId: string, selectedTests: Record<string, string[]>): boolean {
  return false; // No bundle logic - all tests are individually selectable
}

// Get test count excluding duplicates from bundle
export function getUniqueTestCount(selectedTests: Record<string, string[]>): number {
  const metrics = convertTestIdsToMetrics(selectedTests);
  return normalizeSelected(metrics).length;
}

// Normalize selected tests to avoid duplicates
export function normalizeSelectedTests(selectedTests: Record<string, string[]>): Record<string, string[]> {
  const metrics = convertTestIdsToMetrics(selectedTests);
  const normalizedMetrics = normalizeSelected(metrics);
  return convertMetricsToTestIds(normalizedMetrics);
}
