import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, BarChart3, Shield, ShieldCheck, Zap, TrendingUp, Layers, CheckSquare, Square, AlertTriangle, Clock, Database, Scale, LucideIcon, Upload, Lock, Info } from 'lucide-react';
import { DataRequirements, SUITE_DATA_REQUIREMENTS } from '../types/metrics';
import { getDefaultRagSelection, isTestDisabledByBundle, getUniqueTestCount, normalizeSelectedTests } from '../utils/test-selection';
import type { RedTeamCategory, RedTeamSubtests as RedTeamSubtestsType, SafetyCategory, SafetySubtests as SafetySubtestsType } from '../types';
import RedTeamSubtests from './RedTeamSubtests';
import SafetySubtests from './SafetySubtests';
import ReusedFromPreflightChip from './preflight/ReusedFromPreflightChip';

interface TestDefinition {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  required?: boolean; // Some tests might be mandatory
  estimatedDuration?: string;
  dependencies?: string[]; // Other test IDs this test depends on
  // Cross-suite deduplication fields
  reusedSignals?: number;
  reusedCategories?: string[];
}

interface TestSuite {
  id: string;
  name: string;
  description: string;
  icon: LucideIcon;
  color: string;
  enabled: boolean;
  expanded: boolean;
  tests: TestDefinition[];
  dataRequirements?: Partial<DataRequirements>;
}

interface TestSuiteSelectorProps {
  llmModelType: "rag" | "agent" | "tool" | "";
  hasGroundTruth: boolean;
  onSelectionChange: (selectedTests: Record<string, string[]>) => void;
  onSuiteConfigChange: (suiteId: string, config: any) => void;
  onRedTeamSubtestsChange?: (subtests: RedTeamSubtestsType) => void;
  onSafetySubtestsChange?: (subtests: SafetySubtestsType) => void;
  onSuitesChange?: (suites: string[]) => void; // Notify parent of suite enable/disable
  dataStatus?: Partial<DataRequirements>; // Current data availability status
  onShowRequirements?: () => void; // Callback to scroll to data requirements section
}

const TestSuiteSelector: React.FC<TestSuiteSelectorProps> = ({
  llmModelType,
  hasGroundTruth,
  onSelectionChange,
  onSuiteConfigChange,
  onRedTeamSubtestsChange,
  onSafetySubtestsChange,
  onSuitesChange,
  dataStatus,
  onShowRequirements
}) => {
  // Track previous GT state to handle transitions
  const prevGtState = React.useRef(hasGroundTruth);
  
  // Red Team subtests state - initialize with all subtests selected (backward compatible)
  const [redTeamSubtests, setRedTeamSubtests] = useState<RedTeamSubtestsType>({
    prompt_injection: ["direct", "indirect", "passage_embedded", "metadata_embedded"],
    jailbreak: ["role_play", "system_override"],
    data_extraction: ["system_prompt", "api_key", "base64"],
    context_poisoning: ["ignore_citations", "contradict_retrieval", "spoof_citations"],
    social_engineering: ["authority", "urgency", "scarcity", "reciprocity", "sympathy"]
  });

  // Safety subtests state - initialize with all subtests selected (backward compatible)
  const [safetySubtests, setSafetySubtests] = useState<SafetySubtestsType>({
    toxicity: ["explicit", "implicit", "contextual"],
    hate: ["targeted", "general"],
    violence: ["graphic", "threat"],
    adult: ["explicit"],
    self_harm: ["direct", "indirect"],
    misinformation: ["claim_no_cite", "hallucinated_citation"]
  });
  
  // Update test selection based on RAG mode and GT availability
  useEffect(() => {
    if (llmModelType === 'rag') {
      // Handle GT state transitions
      const isGtTransition = prevGtState.current !== hasGroundTruth;
      prevGtState.current = hasGroundTruth;
      
      // RAG Metrics Spec: Default selection based on GT availability
      const ragDefaults = hasGroundTruth 
        ? ['faithfulness', 'context_recall', 'answer_relevancy', 'context_precision', 'answer_correctness', 'answer_similarity', 'context_entities_recall', 'context_relevancy']  // 8 defaults with GT
        : ['faithfulness', 'context_recall', 'answer_relevancy'];  // 3 defaults without GT
      
      // Default selection for companion suites (always all tests enabled)
      const companionDefaults = {
        red_team: ['prompt_injection', 'jailbreak_attempts', 'data_extraction', 'context_manipulation', 'social_engineering'],
        safety: ['toxicity_detection', 'hate_speech', 'violence_content', 'adult_content', 'misinformation'],
        performance: ['cold_start_latency', 'warm_performance', 'throughput_testing', 'stress_testing', 'memory_usage']
      };
      
      // Update test suites with RAG-specific behavior
      setTestSuites(prev => prev.map(suite => {
        if (!['rag_reliability_robustness', 'red_team', 'safety', 'performance', 'guardrails'].includes(suite.id)) {
          return { ...suite, enabled: false };
        }
        
        // Set data requirements
        const requirements = suite.id === 'rag_reliability_robustness' 
          ? hasGroundTruth ? SUITE_DATA_REQUIREMENTS.rag_with_gt : SUITE_DATA_REQUIREMENTS.rag_no_gt
          : SUITE_DATA_REQUIREMENTS[suite.id];
          
        return {
          ...suite,
          enabled: true,
          expanded: true,
          dataRequirements: requirements,
          tests: suite.tests.map(test => {
            if (suite.id === 'rag_reliability_robustness') {
              // RAG suite: handle GT transitions and defaults
              if (isGtTransition) {
                // On GT transitions, only update GT-specific tests
                if (!hasGroundTruth) {
                  // GT → No-GT: Disable GT-only metrics
                  if (['context_precision', 'answer_correctness', 'answer_similarity', 'context_entities_recall', 'context_relevancy'].includes(test.id)) {
                    return { ...test, enabled: false };
                  }
                } else {
                  // No-GT → GT: Enable GT metrics based on defaults
                  if (['context_precision', 'answer_correctness', 'answer_similarity', 'context_entities_recall', 'context_relevancy'].includes(test.id)) {
                    return { ...test, enabled: ragDefaults.includes(test.id) };
                  }
                }
                // Keep existing state for other tests during GT transitions
                return test;
              } else {
                // Initial RAG selection: use defaults
                return { ...test, enabled: ragDefaults.includes(test.id) };
              }
            } else {
              // Companion suites: always enable all tests on initial selection, preserve on GT transitions
              if (isGtTransition) {
                return test; // Keep existing state during GT transitions
              } else {
                // Initial selection: enable all tests in companion suites
                const suiteDefaults = companionDefaults[suite.id as keyof typeof companionDefaults] || [];
                return { ...test, enabled: suiteDefaults.includes(test.id) };
              }
            }
          })
        };
      }));
      
      // Notify parent of selection
      if (!isGtTransition) {
        // Only update selection on initial RAG selection, not GT transitions
        const initialSelection: Record<string, string[]> = {
          rag_reliability_robustness: ragDefaults,
          red_team: companionDefaults.red_team,
          safety: companionDefaults.safety,
          performance: companionDefaults.performance
        };
        onSelectionChange(normalizeSelectedTests(initialSelection));
      }
    }
  }, [llmModelType, hasGroundTruth]); // Removed onSelectionChange to prevent infinite loops

  // Handle Red Team subtests changes
  const handleRedTeamSubtestChange = (category: RedTeamCategory, subtests: string[]) => {
    const newRedTeamSubtests = {
      ...redTeamSubtests,
      [category]: subtests
    };
    setRedTeamSubtests(newRedTeamSubtests);
    
    // Notify parent component
    if (onRedTeamSubtestsChange) {
      onRedTeamSubtestsChange(newRedTeamSubtests);
    }
  };

  // Handle Safety subtests changes
  const handleSafetySubtestChange = (category: SafetyCategory, subtests: string[]) => {
    const newSafetySubtests = {
      ...safetySubtests,
      [category]: subtests
    };
    setSafetySubtests(newSafetySubtests);
    
    // Notify parent component
    if (onSafetySubtestsChange) {
      onSafetySubtestsChange(newSafetySubtests);
    }
  };

  const [testSuites, setTestSuites] = useState<TestSuite[]>([
    {
      id: 'rag_reliability_robustness',
      name: 'RAG Reliability & Robustness',
      description: 'Retrieval-Augmented Generation evaluation and robustness testing',
      icon: BarChart3,
      color: 'blue',
      enabled: true,
      expanded: false,
      tests: [
        {
          id: 'faithfulness',
          name: 'Faithfulness Evaluation',
          description: 'Measures how grounded the answer is in the provided context',
          enabled: true,
          required: true,
          estimatedDuration: '2-5 min',
        },
        {
          id: 'context_recall',
          name: 'Context Recall',
          description: 'Measures how much of the ground truth is captured by retrieved contexts',
          enabled: true,
          required: true,
          estimatedDuration: '2-5 min',
        },
        {
          id: 'answer_relevancy',
          name: 'Answer Relevancy',
          description: 'Measures how relevant the answer is to the question',
          enabled: true,
          required: true,
          estimatedDuration: '3-7 min',
        },

        {
          id: 'context_precision',
          name: 'Context Precision',
          description: 'Measures how relevant the retrieved contexts are to the question',
          enabled: true,  // RAG Metrics Spec: Default with GT
          estimatedDuration: '3-7 min',
        },
        {
          id: 'answer_correctness',
          name: 'Answer Correctness',
          description: 'Measures the accuracy of the answer compared to ground truth',
          enabled: true,  // RAG Metrics Spec: Default with GT
          estimatedDuration: '4-8 min',
        },
        {
          id: 'answer_similarity',
          name: 'Answer Similarity',
          description: 'Measures semantic similarity between generated and ground truth answers',
          enabled: true,  // RAG Metrics Spec: Default with GT
          estimatedDuration: '3-6 min',
        },
        {
          id: 'context_entities_recall',
          name: 'Context Entities Recall',
          description: 'Measures how well entities from ground truth are captured in retrieved contexts',
          enabled: true,  // RAG Metrics Spec: Default with GT
          estimatedDuration: '4-7 min',
        },
        {
          id: 'context_relevancy',
          name: 'Context Relevancy',
          description: 'Measures how relevant the retrieved contexts are to the question',
          enabled: true,  // RAG Metrics Spec: Default with GT
          estimatedDuration: '3-6 min',
        },
        {
          id: 'embedding_robustness',
          name: 'Embedding Robustness',
          description: 'Tests retrieval stability under synonym/paraphrase variation and biased embeddings',
          enabled: false,  // Optional subtest, disabled by default
          estimatedDuration: '5-10 min',
        },
        {
          id: 'prompt_robustness',
          name: 'Prompt Robustness (Structured Prompting)',
          description: 'Tests prompt robustness across simple, CoT, and scaffold modes',
          enabled: false,  // RAG Metrics Spec: Optional, off by default
          estimatedDuration: '10-20 min',
        }
      ]
    },
    {
      id: 'red_team',
      name: 'Red Team',
      description: 'Adversarial testing and attack simulation',
      icon: Shield,
      color: 'red',
      enabled: true,
      expanded: false,
      tests: [
        {
          id: 'prompt_injection',
          name: 'Prompt Injection Tests',
          description: 'Tests for direct and indirect prompt injection vulnerabilities',
          enabled: true,
          required: true,
          estimatedDuration: '5-10 min',
        },
        {
          id: 'jailbreak_attempts',
          name: 'Jailbreak Attempts',
          description: 'Tests for system constraint bypassing through role playing',
          enabled: true,
          estimatedDuration: '5-10 min',
        },
        {
          id: 'data_extraction',
          name: 'Data Extraction',
          description: 'Tests for unauthorized training data and system prompt extraction',
          enabled: false,
          estimatedDuration: '3-8 min',
        },
        {
          id: 'context_manipulation',
          name: 'Context Manipulation',
          description: 'Tests for context poisoning and manipulation attacks',
          enabled: false,
          estimatedDuration: '4-9 min',
        },
        {
          id: 'social_engineering',
          name: 'Social Engineering',
          description: 'Tests for social engineering and manipulation attempts',
          enabled: false,
          estimatedDuration: '3-7 min',
        }
      ]
    },
    {
      id: 'safety',
      name: 'Safety',
      description: 'Content safety and policy compliance',
      icon: ShieldCheck,
      color: 'green',
      enabled: true,
      expanded: false,
      tests: [
        {
          id: 'toxicity_detection',
          name: 'Toxicity Detection',
          description: 'Tests for harmful, toxic, or offensive content generation',
          enabled: true,
          required: true,
          estimatedDuration: '3-6 min',
        },
        {
          id: 'hate_speech',
          name: 'Hate Speech Detection',
          description: 'Tests for hate speech and discriminatory content',
          enabled: true,
          estimatedDuration: '2-5 min',
        },
        {
          id: 'violence_content',
          name: 'Violence Content',
          description: 'Tests for violent or harmful content generation',
          enabled: false,
          estimatedDuration: '2-4 min',
        },
        {
          id: 'adult_content',
          name: 'Adult Content',
          description: 'Tests for inappropriate adult content generation',
          enabled: false,
          estimatedDuration: '2-4 min',
        },

        {
          id: 'misinformation',
          name: 'Misinformation Detection',
          description: 'Tests for false or misleading information generation',
          enabled: false,
          estimatedDuration: '3-6 min',
        }
      ]
    },
    {
      id: 'bias_smoke',
      name: 'Bias Detection',
      description: 'Demographic fairness and bias testing',
      icon: Scale,
      color: 'purple',
      enabled: true,
      expanded: false,
      tests: [
        {
          id: 'demographic_parity',
          name: 'Demographic Parity',
          description: 'A/B testing across demographic groups (gender, age)',
          enabled: true,
          required: true,
          estimatedDuration: '3-8 min',
        },
        {
          id: 'refusal_rate_analysis',
          name: 'Refusal Rate Analysis',
          description: 'Compare refusal rates between demographic groups',
          enabled: true,
          estimatedDuration: '2-5 min',
        },
        {
          id: 'length_delta_analysis',
          name: 'Response Length Analysis',
          description: 'Analyze response length differences across groups',
          enabled: false,
          estimatedDuration: '2-5 min',
        }
      ]
    },
    {
      id: 'bias',
      name: 'Bias (Template-driven)',
      description: 'Advanced bias testing with custom templates and statistical analysis',
      icon: Scale,
      color: 'indigo',
      enabled: true,
      expanded: false,
      tests: [
        {
          id: 'refusal_rate_gender',
          name: 'Refusal Rate (Gender)',
          description: 'Test refusal rate differences across gender groups',
          enabled: true,
          required: true,
          estimatedDuration: '5-10 min',
        },
        {
          id: 'response_length_age',
          name: 'Response Length (Age)',
          description: 'Test response length differences across age groups',
          enabled: true,
          estimatedDuration: '3-8 min',
        },
        {
          id: 'demographic_parity_accent',
          name: 'Demographic Parity (Accent)',
          description: 'Test overall fairness across accent groups',
          enabled: false,
          estimatedDuration: '4-9 min',
        },
        {
          id: 'intersectional_gender_age',
          name: 'Intersectional (Gender × Age)',
          description: 'Test intersectional bias across gender and age',
          enabled: false,
          estimatedDuration: '6-12 min',
        }
      ]
    },
    {
      id: 'performance',
      name: 'Performance',
      description: 'Response latency and throughput testing',
      icon: Zap,
      color: 'yellow',
      enabled: true,
      expanded: false,
      tests: [
        {
          id: 'cold_start_latency',
          name: 'Cold Start Latency',
          description: 'Measures initial response time for first requests',
          enabled: true,
          required: true,
          estimatedDuration: '1-3 min',
        },
        {
          id: 'warm_performance',
          name: 'Warm Performance',
          description: 'Measures response time for subsequent requests',
          enabled: true,
          estimatedDuration: '2-4 min',
        },
        {
          id: 'throughput_testing',
          name: 'Throughput Testing',
          description: 'Measures system capacity under concurrent load',
          enabled: false,
          estimatedDuration: '3-8 min',
        },
        {
          id: 'stress_testing',
          name: 'Stress Testing',
          description: 'Tests system behavior under extreme load conditions',
          enabled: false,
          estimatedDuration: '5-15 min',
        },
        {
          id: 'memory_usage',
          name: 'Memory Usage Analysis',
          description: 'Monitors memory consumption during operations',
          enabled: false,
          estimatedDuration: '2-5 min',
        }
      ]
    },
    {
      id: 'guardrails',
      name: 'Guardrails',
      description: 'Composite security and compliance guardrails',
      icon: Shield,
      color: 'purple',
      enabled: false,
      expanded: false,
      tests: [
        {
          id: 'pii_leak',
          name: 'PII/PHI Leak Detection',
          description: 'Detects personally identifiable information leakage',
          enabled: true,
          required: true,
          estimatedDuration: '2-4 min',
        },
        {
          id: 'jailbreak',
          name: 'Jailbreak & Obfuscation',
          description: 'Tests for prompt injection and jailbreak attempts',
          enabled: true,
          estimatedDuration: '3-6 min',
        },
        {
          id: 'schema_guard',
          name: 'JSON/Schema Guard',
          description: 'Validates response structure and schema compliance',
          enabled: true,
          estimatedDuration: '1-3 min',
        },
        {
          id: 'citation_required',
          name: 'Citation Required',
          description: 'Ensures proper source attribution in responses',
          enabled: true,
          estimatedDuration: '2-4 min',
        },
        {
          id: 'resilience',
          name: 'Resilience Testing',
          description: 'Tests handling of adversarial inputs and edge cases',
          enabled: true,
          estimatedDuration: '3-7 min',
        },
        {
          id: 'mcp_governance',
          name: 'Tool/MCP Governance',
          description: 'Validates tool usage and MCP security policies',
          enabled: false,
          estimatedDuration: '2-5 min',
        },
        {
          id: 'rate_cost_limits',
          name: 'Rate/Cost Limits',
          description: 'Monitors rate limiting and cost budget compliance',
          enabled: true,
          estimatedDuration: '1-3 min',
        },
        {
          id: 'bias_fairness',
          name: 'Bias/Fairness (Smoke)',
          description: 'Quick bias detection across demographic categories',
          enabled: true,
          estimatedDuration: '2-4 min',
        }
      ]
    }
  ]);

  // Note: Selection change notifications are handled directly in toggle functions
  // to prevent state conflicts and infinite re-renders

  const toggleSuite = (suiteId: string) => {
    setTestSuites(prev => {
      const updated = prev.map(suite => {
        if (suite.id === suiteId) {
          const newEnabled = !suite.enabled;
          // If disabling suite, disable all tests
          if (!newEnabled) {
            return {
              ...suite,
              enabled: newEnabled,
              tests: suite.tests.map(test => ({ ...test, enabled: false }))
            };
          }
          // If enabling suite, enable required tests
          return {
            ...suite,
            enabled: newEnabled,
            tests: suite.tests.map(test => ({
              ...test,
              enabled: test.required || test.enabled
            }))
          };
        }
        return suite;
      });
      
      // Notify parent of suite changes
      const enabledSuiteIds = updated.filter(s => s.enabled).map(s => s.id);
      onSuitesChange?.(enabledSuiteIds as any[]);
      
      return updated;
    });
  };

  const toggleSuiteExpansion = (suiteId: string) => {
    setTestSuites(prev => prev.map(suite =>
      suite.id === suiteId ? { ...suite, expanded: !suite.expanded } : suite
    ));
  };

  const generateSelectedTests = (suites: typeof testSuites) => {
    const selectedTests: { [key: string]: string[] } = {};
    suites.forEach(suite => {
      selectedTests[suite.id] = suite.tests
        .filter(test => test.enabled)
        .map(test => test.id);
    });
    return selectedTests;
  };

  const toggleTest = (suiteId: string, testId: string) => {
    console.log('toggleTest called:', suiteId, testId); // Debug log
    
    setTestSuites(prevSuites => {
      const updatedSuites = prevSuites.map(suite => {
        if (suite.id === suiteId) {
          return {
            ...suite,
            tests: suite.tests.map(test => {
              if (test.id === testId) {
                console.log('Toggling test:', test.id, 'from', test.enabled, 'to', !test.enabled); // Debug log
                return { ...test, enabled: !test.enabled };
              }
              return test;
            })
          };
        }
        return suite;
      });
      
      // Notify parent component of selection change
      const selectedTests = generateSelectedTests(updatedSuites);
      console.log('Selected tests:', selectedTests); // Debug log
      onSelectionChange(selectedTests);
      
      return updatedSuites;
    });
  };

  const selectAllTests = (suiteId: string) => {
    setTestSuites(prev => prev.map(suite => {
      if (suite.id === suiteId) {
        return {
          ...suite,
          tests: suite.tests.map(test => ({ ...test, enabled: true }))
        };
      }
      return suite;
    }));
  };

  const deselectAllTests = (suiteId: string) => {
    setTestSuites(prev => prev.map(suite => {
      if (suite.id === suiteId) {
        return {
          ...suite,
          tests: suite.tests.map(test => ({
            ...test,
            enabled: false // All tests can now be deselected
          }))
        };
      }
      return suite;
    }));
  };

  const getColorClasses = (color: string, variant: 'icon' | 'bg' | 'border' | 'text') => {
    const colors = {
      blue: {
        icon: 'text-blue-600 dark:text-blue-400',
        bg: 'bg-blue-50 dark:bg-blue-900/20',
        border: 'border-blue-200 dark:border-blue-800',
        text: 'text-blue-700 dark:text-blue-300'
      },
      red: {
        icon: 'text-red-600 dark:text-red-400',
        bg: 'bg-red-50 dark:bg-red-900/20',
        border: 'border-red-200 dark:border-red-800',
        text: 'text-red-700 dark:text-red-300'
      },
      green: {
        icon: 'text-green-600 dark:text-green-400',
        bg: 'bg-green-50 dark:bg-green-900/20',
        border: 'border-green-200 dark:border-green-800',
        text: 'text-green-700 dark:text-green-300'
      },
      yellow: {
        icon: 'text-yellow-600 dark:text-yellow-400',
        bg: 'bg-yellow-50 dark:bg-yellow-900/20',
        border: 'border-yellow-200 dark:border-yellow-800',
        text: 'text-yellow-700 dark:text-yellow-300'
      }
    };
    return colors[color as keyof typeof colors]?.[variant] || '';
  };

  const getTotalEstimatedTime = () => {
    let totalMinutes = 0;
    testSuites.forEach(suite => {
      if (suite.enabled) {
        suite.tests.forEach(test => {
          if (test.enabled && test.estimatedDuration) {
            // Parse duration like "2-5 min" and take average
            const match = test.estimatedDuration.match(/(\d+)-(\d+)/);
            if (match) {
              const avg = (parseInt(match[1]) + parseInt(match[2])) / 2;
              totalMinutes += avg;
            }
          }
        });
      }
    });
    return Math.round(totalMinutes);
  };

  const getTotalSelectedTests = () => {
    return testSuites.reduce((total, suite) => {
      if (suite.enabled) {
        return total + suite.tests.filter(test => test.enabled).length;
      }
      return total;
    }, 0);
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Test Suites & Individual Tests
          </h3>
          <p className="text-sm text-slate-600 dark:text-slate-400">
            {llmModelType === "rag" 
              ? hasGroundTruth 
                ? "RAG System with Ground Truth - 4 test suites available with Red Team, Safety, and Performance pre-selected"
                : "RAG System without Ground Truth - 4 test suites available with Red Team, Safety, and Performance pre-selected"
              : llmModelType === "agent"
              ? "AI Agent testing - Tool usage and reasoning evaluation"
              : llmModelType === "tool"
              ? "Function/Tool testing - Performance and error handling evaluation"
              : "Select an LLM option above to see available test suites"
            }
          </p>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold text-slate-900 dark:text-slate-100">
            {getTotalSelectedTests()} tests
          </div>
          <div className="text-sm text-slate-500 dark:text-slate-400">
            ~{getTotalEstimatedTime()} minutes
          </div>
        </div>
      </div>



      {/* Show message if no LLM type selected */}
      {!llmModelType && (
        <div className="text-center py-8 text-slate-500 dark:text-slate-400">
          <div className="text-4xl mb-2">🎯</div>
          <div className="text-lg font-medium mb-1">Choose Your LLM Type</div>
          <div className="text-sm">Select RAG, Agent, or Tool above to see available test suites</div>
        </div>
      )}

      {/* RAG-specific metrics info */}
      {llmModelType === "rag" && (
        <>
          {/* Ragas Warning Banner */}
          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4 mb-4">
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="flex-1">
                <h4 className="text-sm font-semibold text-yellow-900 dark:text-yellow-100">
                  RAG Evaluation Dependencies
                </h4>
                <div className="mt-1 text-xs text-yellow-800 dark:text-yellow-200">
                  <p>Some advanced RAG metrics require the Ragas library. If Ragas is unavailable:</p>
                  <ul className="mt-1 ml-4 list-disc space-y-1">
                    <li>Fallback evaluation methods will be used automatically</li>
                    <li>Tests will continue to run with reduced metric coverage</li>
                    <li>If Ragas thresholds are specified, the RAG Quality gate will fail with a clear warning</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
          
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-100 mb-2">
              🎯 RAG System Testing - 5 Test Suites Available
            </h4>
            <div className="text-xs text-blue-800 dark:text-blue-200 space-y-1">
              <div>✅ <strong>RAG Reliability & Robustness:</strong> {hasGroundTruth ? '8 metrics available' : '3 basic metrics'} - Faithfulness, Context Recall, Answer Relevancy{hasGroundTruth ? ', plus 5 ground truth metrics' : ''}</div>
              <div>✅ <strong>Red Team (Pre-selected):</strong> All adversarial tests enabled - Prompt Injection, Jailbreak, Data Extraction, Context Manipulation, Social Engineering</div>
              <div>✅ <strong>Safety (Pre-selected):</strong> All safety tests enabled - Toxicity, Hate Speech, Violence, Adult Content, Misinformation</div>
              <div>✅ <strong>Performance (Pre-selected):</strong> All performance tests enabled - Cold Start, Warm Performance, Throughput, Stress, Memory</div>
              {!hasGroundTruth && (
                <div>⚠️ <strong>Upload ground truth data to unlock 5 additional RAG metrics</strong></div>
              )}
            </div>
            
            {/* Ground Truth behavior note */}
            <div className="mt-3 text-xs text-blue-800 dark:text-blue-200">
              <strong>Note:</strong> Ground Truth toggle only affects RAG suite defaults. Red Team, Safety, and Performance suites remain selected and visible.
            </div>
          </div>
        </>
      )}

      {/* Test Suites */}
      {llmModelType && (
        <div className="space-y-3">
          {testSuites
            .filter(suite => {
              // Show only relevant suites based on LLM model type
              if (llmModelType === 'rag') {
                return ['rag_reliability_robustness', 'red_team', 'safety', 'performance', 'bias_smoke'].includes(suite.id);
              }
              // For other types, show all suites except RAG-specific ones
              return !['rag_reliability_robustness'].includes(suite.id);
            })
            .map((suite) => {
          const Icon = suite.icon;
          const enabledTestsCount = suite.tests.filter(test => test.enabled).length;
          const totalTestsCount = suite.tests.length;

          return (
            <div
              key={suite.id}
              className={`border rounded-lg transition-all ${
                suite.enabled 
                  ? `${getColorClasses(suite.color, 'border')} ${getColorClasses(suite.color, 'bg')}` 
                  : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800'
              }`}
            >
              {/* Suite Header */}
              <div className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      className="w-4 h-4 accent-blue-600"
                      checked={suite.enabled}
                      onChange={() => toggleSuite(suite.id)}
                    />
                    <Icon 
                      size={20} 
                      className={suite.enabled ? getColorClasses(suite.color, 'icon') : 'text-slate-400'} 
                    />
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className={`font-medium ${
                          suite.enabled 
                            ? 'text-slate-900 dark:text-slate-100' 
                            : 'text-slate-500 dark:text-slate-400'
                        }`}>
                          {suite.name}
                        </span>
                        {suite.enabled && enabledTestsCount > 0 && (
                          <span className={`px-2 py-1 text-xs rounded-full ${getColorClasses(suite.color, 'bg')} ${getColorClasses(suite.color, 'text')}`}>
                            {enabledTestsCount}/{totalTestsCount}
                          </span>
                        )}
                      </div>
                      <div className="space-y-1">
                        <p className={`text-sm ${
                          suite.enabled 
                            ? 'text-slate-600 dark:text-slate-400' 
                            : 'text-slate-400 dark:text-slate-500'
                        }`}>
                          {suite.description}
                        </p>
                        {suite.dataRequirements && dataStatus && (
                          <div className="flex items-center space-x-2">
                            {Object.entries(suite.dataRequirements).map(([key, required]) => {
                              if (!required) return null;
                              const isAvailable = dataStatus[key as keyof DataRequirements];
                              return (
                                <div 
                                  key={key}
                                  className={`flex items-center space-x-1 text-xs px-2 py-1 rounded ${
                                    isAvailable
                                      ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                                      : 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300'
                                  }`}
                                >
                                  {isAvailable ? (
                                    <CheckSquare size={12} />
                                  ) : (
                                    <Lock size={12} />
                                  )}
                                  <span>
                                    {key === 'passages' ? 'Passages' : 
                                     key === 'qaSet' ? 'QA Set' : 
                                     key === 'attacks' ? 'Attacks' : key}
                                  </span>
                                  {!isAvailable && (
                                    <button
                                      onClick={onShowRequirements}
                                      className="ml-1 text-yellow-600 dark:text-yellow-400 hover:text-yellow-800 dark:hover:text-yellow-200"
                                    >
                                      <Info size={12} />
                                    </button>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    {suite.enabled && (
                      <>
                        <button
                          onClick={() => selectAllTests(suite.id)}
                          className="text-xs px-2 py-1 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/30 rounded"
                        >
                          All
                        </button>
                        <button
                          onClick={() => deselectAllTests(suite.id)}
                          className="text-xs px-2 py-1 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded"
                        >
                          None
                        </button>
                      </>
                    )}
                    <button
                      onClick={() => toggleSuiteExpansion(suite.id)}
                      className={`p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-700 ${
                        !suite.enabled && 'opacity-50'
                      }`}
                      disabled={!suite.enabled}
                    >
                      {suite.expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    </button>
                  </div>
                </div>
              </div>

              {/* Individual Tests */}
              {suite.expanded && suite.enabled && (
                <div className="border-t border-slate-200 dark:border-slate-700 p-4 space-y-3">
                  {suite.tests.map((test) => (
                                          <div
                      key={`${suite.id}-${test.id}-${test.enabled}`}
                      className={`flex items-start space-x-3 p-3 rounded-lg border transition-all ${
                        test.enabled
                          ? 'border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800'
                          : 'border-slate-100 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50'
                      } ${
                        !suite.dataRequirements || !dataStatus || Object.entries(suite.dataRequirements).every(
                          ([key, required]) => !required || dataStatus[key as keyof DataRequirements]
                        ) ? '' : 'opacity-50'
                      }`}
                    >
                      <div className="flex items-center mt-1">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            toggleTest(suite.id, test.id);
                          }}
                          className="hover:bg-slate-100 dark:hover:bg-slate-700 rounded p-1 cursor-pointer"
                          style={{ pointerEvents: 'auto' }}
                        >
                          {test.enabled ? (
                            <CheckSquare size={16} className="text-blue-600 dark:text-blue-400" />
                          ) : (
                            <Square size={16} className="text-slate-400" />
                          )}
                        </button>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-2 mb-1">
                          <span className={`font-medium ${
                            test.enabled 
                              ? 'text-slate-900 dark:text-slate-100' 
                              : 'text-slate-500 dark:text-slate-400'
                          }`}>
                            {test.name}
                          </span>
                          {test.required && (
                            <span className="px-2 py-1 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded">
                              Required
                            </span>
                          )}

                          {test.estimatedDuration && (
                            <span className="flex items-center space-x-1 text-xs text-slate-500 dark:text-slate-400">
                              <Clock size={12} />
                              <span>{test.estimatedDuration}</span>
                            </span>
                          )}
                          
                          {/* Show reused from preflight chip if applicable */}
                          <ReusedFromPreflightChip 
                            reusedCount={(test as any).reusedSignals || 0}
                            reusedCategories={(test as any).reusedCategories || []}
                            size="sm"
                          />
                        </div>
                        <p className={`text-sm ${
                          test.enabled 
                            ? 'text-slate-600 dark:text-slate-400' 
                            : 'text-slate-400 dark:text-slate-500'
                        }`}>
                          {test.description}
                        </p>
                        
                        {/* Red Team Subtests */}
                        {suite.id === 'red_team' && test.enabled && (
                          <RedTeamSubtests
                            category={test.id as RedTeamCategory}
                            selectedSubtests={redTeamSubtests[test.id as RedTeamCategory] || []}
                            onSubtestsChange={handleRedTeamSubtestChange}
                            className="mt-2"
                          />
                        )}
                        
                        {/* Safety Subtests */}
                        {suite.id === 'safety' && test.enabled && (
                          <SafetySubtests
                            testId={test.id}
                            selectedSubtests={(() => {
                              // Map test ID to category to get correct subtests
                              const categoryMap: Record<string, SafetyCategory> = {
                                'toxicity_detection': 'toxicity',
                                'hate_speech': 'hate',
                                'violence_content': 'violence',
                                'adult_content': 'adult',
                                'self_harm': 'self_harm',
                                'misinformation': 'misinformation'
                              };
                              const category = categoryMap[test.id];
                              return category ? safetySubtests[category] || [] : [];
                            })()}
                            onSubtestsChange={handleSafetySubtestChange}
                            className="mt-2"
                          />
                        )}
                        {test.dependencies && test.dependencies.length > 0 && (
                          <div className="mt-2 flex items-center space-x-1">
                            <Database size={12} className="text-slate-400" />
                            <span className="text-xs text-slate-500 dark:text-slate-400">
                              Depends on: {test.dependencies.join(', ')}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        </div>
      )}

      {/* Quick Actions - Only show if LLM type is selected */}
      {llmModelType && (
      <div className="flex items-center justify-between pt-4 border-t border-slate-200 dark:border-slate-700">
        <div className="flex space-x-2">
          {llmModelType === 'rag' && (
            <button
              onClick={() => {
                // RAG Metrics Spec: Default selection based on GT availability
                const ragDefaults = hasGroundTruth 
                  ? ['faithfulness', 'context_recall', 'answer_relevancy', 'context_precision', 'answer_correctness', 'answer_similarity', 'context_entities_recall', 'context_relevancy']  // 8 defaults with GT
                  : ['faithfulness', 'context_recall', 'answer_relevancy'];  // 3 defaults without GT
                
                // Default selection for companion suites (always all tests enabled)
                const companionDefaults = {
                  red_team: ['prompt_injection', 'jailbreak_attempts', 'data_extraction', 'context_manipulation', 'social_engineering'],
                  safety: ['toxicity_detection', 'hate_speech', 'violence_content', 'adult_content', 'misinformation'],
                  performance: ['cold_start_latency', 'warm_performance', 'throughput_testing', 'stress_testing', 'memory_usage']
                };
                
                // Reset to recommended selection
                setTestSuites(prev => prev.map(suite => {
                  if (!['rag_reliability_robustness', 'red_team', 'safety', 'performance', 'guardrails'].includes(suite.id)) {
                    return { ...suite, enabled: false };
                  }
                  
                  return {
                    ...suite,
                    enabled: true,
                    expanded: true,
                    tests: suite.tests.map(test => {
                      if (suite.id === 'rag_reliability_robustness') {
                        // RAG suite: use GT-aware defaults
                        return { ...test, enabled: ragDefaults.includes(test.id) };
                      } else {
                        // Companion suites: enable all tests
                        const suiteDefaults = companionDefaults[suite.id as keyof typeof companionDefaults] || [];
                        return { ...test, enabled: suiteDefaults.includes(test.id) };
                      }
                    })
                  };
                }));
                
                // Notify parent of selection
                const resetSelection: Record<string, string[]> = {
                  rag_reliability_robustness: ragDefaults,
                  red_team: companionDefaults.red_team,
                  safety: companionDefaults.safety,
                  performance: companionDefaults.performance
                };
                onSelectionChange(normalizeSelectedTests(resetSelection));
              }}
              className="btn btn-primary btn-sm"
            >
              Reset to Recommended
            </button>
          )}
          <button
            onClick={() => {
              setTestSuites(prev => prev.map(suite => ({
                ...suite,
                enabled: true,
                tests: suite.tests.map(test => ({ ...test, enabled: true }))
              })));
            }}
            className="btn btn-ghost btn-sm"
          >
            Select All Suites & Tests
          </button>
          <button
            onClick={() => {
              setTestSuites(prev => prev.map(suite => ({
                ...suite,
                enabled: false,
                tests: suite.tests.map(test => ({ ...test, enabled: false }))
              })));
            }}
            className="btn btn-ghost btn-sm"
          >
            Clear All
          </button>
        </div>
        <div className="text-sm text-slate-600 dark:text-slate-400">
          {getTotalSelectedTests()} tests selected • ~{getTotalEstimatedTime()} min estimated
        </div>
      </div>
      )}
    </div>
  );
};

export default TestSuiteSelector;
