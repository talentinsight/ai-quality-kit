import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, BarChart3, Shield, ShieldCheck, Zap, TrendingUp, Layers, CheckSquare, Square, AlertTriangle, Clock, Database } from 'lucide-react';

interface TestDefinition {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  required?: boolean; // Some tests might be mandatory
  estimatedDuration?: string;
  dependencies?: string[]; // Other test IDs this test depends on
}

interface TestSuite {
  id: string;
  name: string;
  description: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  color: string;
  enabled: boolean;
  expanded: boolean;
  tests: TestDefinition[];
}

interface TestSuiteSelectorProps {
  onSelectionChange: (selectedTests: Record<string, string[]>) => void;
  onSuiteConfigChange: (suiteId: string, config: any) => void;
}

const TestSuiteSelector: React.FC<TestSuiteSelectorProps> = ({
  onSelectionChange,
  onSuiteConfigChange
}) => {
  const [testSuites, setTestSuites] = useState<TestSuite[]>([
    {
      id: 'rag_quality',
      name: 'RAG Quality',
      description: 'Retrieval-Augmented Generation evaluation',
      icon: BarChart3,
      color: 'blue',
      enabled: true,
      expanded: false,
      tests: [
        {
          id: 'basic_faithfulness',
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
          enabled: false,
          estimatedDuration: '3-7 min',
        },
        {
          id: 'ground_truth_evaluation',
          name: 'Ground Truth Evaluation (6 Metrics)',
          description: 'Comprehensive evaluation with uploaded ground truth data',
          enabled: false,
          estimatedDuration: '5-15 min',
          dependencies: ['basic_faithfulness', 'context_recall']
        },
        {
          id: 'context_precision',
          name: 'Context Precision',
          description: 'Measures how relevant the retrieved contexts are to the question',
          enabled: false,
          estimatedDuration: '3-7 min',
        },
        {
          id: 'answer_correctness',
          name: 'Answer Correctness',
          description: 'Measures the accuracy of the answer compared to ground truth',
          enabled: false,
          estimatedDuration: '4-8 min',
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
          id: 'bias_detection',
          name: 'Bias Detection',
          description: 'Tests for discriminatory or biased outputs',
          enabled: false,
          estimatedDuration: '4-8 min',
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
    }
  ]);

  // Calculate selected tests and notify parent
  useEffect(() => {
    const selectedTests: Record<string, string[]> = {};
    testSuites.forEach(suite => {
      if (suite.enabled) {
        selectedTests[suite.id] = suite.tests
          .filter(test => test.enabled)
          .map(test => test.id);
      }
    });
    onSelectionChange(selectedTests);
  }, [testSuites, onSelectionChange]);

  const toggleSuite = (suiteId: string) => {
    setTestSuites(prev => prev.map(suite => {
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
    }));
  };

  const toggleSuiteExpansion = (suiteId: string) => {
    setTestSuites(prev => prev.map(suite =>
      suite.id === suiteId ? { ...suite, expanded: !suite.expanded } : suite
    ));
  };

  const toggleTest = (suiteId: string, testId: string) => {
    setTestSuites(prev => prev.map(suite => {
      if (suite.id === suiteId) {
        return {
          ...suite,
          tests: suite.tests.map(test => {
            if (test.id === testId && !test.required) {
              return { ...test, enabled: !test.enabled };
            }
            return test;
          })
        };
      }
      return suite;
    }));
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
            enabled: test.required || false
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
            Select test suites and choose specific tests to run
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

      {/* Test Suites */}
      <div className="space-y-3">
        {testSuites.map((suite) => {
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
                      <p className={`text-sm ${
                        suite.enabled 
                          ? 'text-slate-600 dark:text-slate-400' 
                          : 'text-slate-400 dark:text-slate-500'
                      }`}>
                        {suite.description}
                      </p>
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
                      key={test.id}
                      className={`flex items-start space-x-3 p-3 rounded-lg border transition-all ${
                        test.enabled
                          ? 'border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800'
                          : 'border-slate-100 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50'
                      }`}
                    >
                      <div className="flex items-center mt-1">
                        {test.required ? (
                          <CheckSquare 
                            size={16} 
                            className="text-blue-600 dark:text-blue-400" 
                          />
                        ) : (
                          <button
                            onClick={() => toggleTest(suite.id, test.id)}
                            className="hover:bg-slate-100 dark:hover:bg-slate-700 rounded p-1"
                          >
                            {test.enabled ? (
                              <CheckSquare size={16} className="text-blue-600 dark:text-blue-400" />
                            ) : (
                              <Square size={16} className="text-slate-400" />
                            )}
                          </button>
                        )}
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
                        </div>
                        <p className={`text-sm ${
                          test.enabled 
                            ? 'text-slate-600 dark:text-slate-400' 
                            : 'text-slate-400 dark:text-slate-500'
                        }`}>
                          {test.description}
                        </p>
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

      {/* Quick Actions */}
      <div className="flex items-center justify-between pt-4 border-t border-slate-200 dark:border-slate-700">
        <div className="flex space-x-2">
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
    </div>
  );
};

export default TestSuiteSelector;
