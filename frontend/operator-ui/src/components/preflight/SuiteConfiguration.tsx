import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Settings, ChevronDown, ChevronRight, Plus, X } from 'lucide-react';
import { usePreflightStore } from '../../stores/preflightStore';

interface SuiteConfigurationProps {
  suiteId: string;
}

export default function SuiteConfiguration({ suiteId }: SuiteConfigurationProps) {
  const { suiteConfigs, updateSuiteConfig, thresholds, updateThreshold } = usePreflightStore();
  const [showConfig, setShowConfig] = useState(false);
  const [showThresholds, setShowThresholds] = useState(false);
  
  const config = suiteConfigs?.[suiteId as keyof typeof suiteConfigs];
  
  // Don't show config for suites that don't have configurations
  if (!config) return null;

  const renderResilienceConfig = () => {
    const resConfig = config as any;
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Mode
            </label>
            <select
              value={resConfig.mode || 'passive'}
              onChange={(e) => updateSuiteConfig(suiteId, { mode: e.target.value })}
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
            >
              <option value="passive">Passive</option>
              <option value="synthetic">Synthetic</option>
            </select>
          </div>
          
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Samples
            </label>
            <input
              type="number"
              value={resConfig.samples || 10}
              onChange={(e) => updateSuiteConfig(suiteId, { samples: parseInt(e.target.value) || 10 })}
              min="1"
              max="100"
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
            />
          </div>
          
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Timeout (ms)
            </label>
            <input
              type="number"
              value={resConfig.timeout_ms || 20000}
              onChange={(e) => updateSuiteConfig(suiteId, { timeout_ms: parseInt(e.target.value) || 20000 })}
              min="1000"
              max="60000"
              step="1000"
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
            />
          </div>
          
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Retries
            </label>
            <input
              type="number"
              value={resConfig.retries || 0}
              onChange={(e) => updateSuiteConfig(suiteId, { retries: parseInt(e.target.value) || 0 })}
              min="0"
              max="10"
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
            />
          </div>
          
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Concurrency
            </label>
            <input
              type="number"
              value={resConfig.concurrency || 10}
              onChange={(e) => updateSuiteConfig(suiteId, { concurrency: parseInt(e.target.value) || 10 })}
              min="1"
              max="50"
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
            />
          </div>
          
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Queue Depth
            </label>
            <input
              type="number"
              value={resConfig.queue_depth || 50}
              onChange={(e) => updateSuiteConfig(suiteId, { queue_depth: parseInt(e.target.value) || 50 })}
              min="10"
              max="200"
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
            />
          </div>
        </div>
        
        {/* Circuit Breaker */}
        <div>
          <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Circuit Breaker</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Failure Threshold
              </label>
              <input
                type="number"
                value={resConfig.circuit?.fails || 5}
                onChange={(e) => updateSuiteConfig(suiteId, { 
                  circuit: { 
                    ...resConfig.circuit, 
                    fails: parseInt(e.target.value) || 5 
                  } 
                })}
                min="1"
                max="20"
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Reset Time (seconds)
              </label>
              <input
                type="number"
                value={resConfig.circuit?.reset_s || 30}
                onChange={(e) => updateSuiteConfig(suiteId, { 
                  circuit: { 
                    ...resConfig.circuit, 
                    reset_s: parseInt(e.target.value) || 30 
                  } 
                })}
                min="5"
                max="300"
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
              />
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderRedTeamConfig = () => {
    const redConfig = config as any;
    const availableSubtests = [
      'prompt_injection', 'jailbreak_attempts', 'data_extraction', 
      'context_manipulation', 'social_engineering', 'adversarial_prompts'
    ];
    
    return (
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">
            Attack Subtests
          </label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {availableSubtests.map(subtest => (
              <label key={subtest} className="flex items-center gap-2 px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-sm">
                <input
                  type="checkbox"
                  checked={redConfig.subtests?.includes(subtest) || false}
                  onChange={(e) => {
                    const currentSubtests = redConfig.subtests || [];
                    const newSubtests = e.target.checked
                      ? [...currentSubtests, subtest]
                      : currentSubtests.filter((s: string) => s !== subtest);
                    updateSuiteConfig(suiteId, { subtests: newSubtests });
                  }}
                  className="w-4 h-4 text-blue-600 rounded"
                />
                {subtest.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </label>
            ))}
          </div>
        </div>
        
        <div>
          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
            Attack Mutators
          </label>
          <input
            type="number"
            value={redConfig.mutators || 5}
            onChange={(e) => updateSuiteConfig(suiteId, { mutators: parseInt(e.target.value) || 5 })}
            min="1"
            max="20"
            className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
          />
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Number of variations to generate for each attack template
          </p>
        </div>
      </div>
    );
  };

  const renderSafetyConfig = () => {
    const safetyConfig = config as any;
    const availableCategories = [
      'toxicity', 'hate_speech', 'violence', 'adult_content', 
      'misinformation', 'harassment', 'self_harm'
    ];
    
    return (
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">
            Content Categories
          </label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {availableCategories.map(category => (
              <label key={category} className="flex items-center gap-2 px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-sm">
                <input
                  type="checkbox"
                  checked={safetyConfig.categories?.includes(category) || false}
                  onChange={(e) => {
                    const currentCategories = safetyConfig.categories || [];
                    const newCategories = e.target.checked
                      ? [...currentCategories, category]
                      : currentCategories.filter((c: string) => c !== category);
                    updateSuiteConfig(suiteId, { categories: newCategories });
                  }}
                  className="w-4 h-4 text-blue-600 rounded"
                />
                {category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </label>
            ))}
          </div>
        </div>
        
        <div>
          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
            Detection Threshold
          </label>
          <input
            type="number"
            value={safetyConfig.threshold || 0.8}
            onChange={(e) => updateSuiteConfig(suiteId, { threshold: parseFloat(e.target.value) || 0.8 })}
            min="0"
            max="1"
            step="0.1"
            className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
          />
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Confidence threshold for flagging unsafe content (0.0 - 1.0)
          </p>
        </div>
      </div>
    );
  };

  const renderPerformanceConfig = () => {
    const perfConfig = config as any;
    
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Test Repeats
            </label>
            <input
              type="number"
              value={perfConfig.repeats || 3}
              onChange={(e) => updateSuiteConfig(suiteId, { repeats: parseInt(e.target.value) || 3 })}
              min="1"
              max="10"
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
            />
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Number of times to repeat each performance test
            </p>
          </div>
          
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Latency Limit (ms)
            </label>
            <input
              type="number"
              value={perfConfig.latency_limit || 5000}
              onChange={(e) => updateSuiteConfig(suiteId, { latency_limit: parseInt(e.target.value) || 5000 })}
              min="100"
              max="30000"
              step="100"
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
            />
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Maximum acceptable response time
            </p>
          </div>
        </div>
      </div>
    );
  };

  const renderBiasConfig = () => {
    const biasConfig = config as any;
    const [newGroup, setNewGroup] = useState(['', '']);
    
    return (
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">
            Demographic Groups
          </label>
          <div className="space-y-2">
            {(biasConfig.groups || []).map((group: string[], index: number) => (
              <div key={index} className="flex items-center gap-2 p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                <span className="text-sm text-slate-700 dark:text-slate-300">
                  {group[0]} vs {group[1]}
                </span>
                <button
                  onClick={() => {
                    const newGroups = biasConfig.groups.filter((_: any, i: number) => i !== index);
                    updateSuiteConfig(suiteId, { groups: newGroups });
                  }}
                  className="p-1 text-red-500 hover:text-red-700 transition-colors"
                >
                  <X size={14} />
                </button>
              </div>
            ))}
            
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={newGroup[0]}
                onChange={(e) => setNewGroup([e.target.value, newGroup[1]])}
                placeholder="Group A"
                className="flex-1 px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:border-blue-500 focus:outline-none transition-colors duration-200"
              />
              <span className="text-slate-500">vs</span>
              <input
                type="text"
                value={newGroup[1]}
                onChange={(e) => setNewGroup([newGroup[0], e.target.value])}
                placeholder="Group B"
                className="flex-1 px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:border-blue-500 focus:outline-none transition-colors duration-200"
              />
              <button
                onClick={() => {
                  if (newGroup[0].trim() && newGroup[1].trim()) {
                    const currentGroups = biasConfig.groups || [];
                    updateSuiteConfig(suiteId, { groups: [...currentGroups, newGroup] });
                    setNewGroup(['', '']);
                  }
                }}
                disabled={!newGroup[0].trim() || !newGroup[1].trim()}
                className="p-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-400 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
              >
                <Plus size={14} />
              </button>
            </div>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Max Pairs
            </label>
            <input
              type="number"
              value={biasConfig.max_pairs || 10}
              onChange={(e) => updateSuiteConfig(suiteId, { max_pairs: parseInt(e.target.value) || 10 })}
              min="1"
              max="50"
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
            />
          </div>
          
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
              Parity Threshold
            </label>
            <input
              type="number"
              value={biasConfig.parity_threshold || 0.25}
              onChange={(e) => updateSuiteConfig(suiteId, { parity_threshold: parseFloat(e.target.value) || 0.25 })}
              min="0"
              max="1"
              step="0.05"
              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
            />
          </div>
        </div>
        
        <div>
          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
            Parity Metric
          </label>
          <select
            value={biasConfig.parity_metric || 'refusal_rate'}
            onChange={(e) => updateSuiteConfig(suiteId, { parity_metric: e.target.value })}
            className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
          >
            <option value="refusal_rate">Refusal Rate</option>
            <option value="response_quality">Response Quality</option>
            <option value="sentiment_score">Sentiment Score</option>
          </select>
        </div>
      </div>
    );
  };

  const getThresholdKeys = (suiteId: string): Array<{key: string, label: string, min: number, max: number, step: number, unit?: string}> => {
    switch (suiteId) {
      case 'rag_reliability_robustness':
        return [
          { key: 'faithfulness_min', label: 'Faithfulness Min', min: 0, max: 1, step: 0.1 },
          { key: 'context_recall_min', label: 'Context Recall Min', min: 0, max: 1, step: 0.1 },
          { key: 'answer_relevancy_min', label: 'Answer Relevancy Min', min: 0, max: 1, step: 0.1 },
          { key: 'context_precision_min', label: 'Context Precision Min', min: 0, max: 1, step: 0.1 },
          { key: 'answer_correctness_min', label: 'Answer Correctness Min', min: 0, max: 1, step: 0.1 },
          { key: 'answer_similarity_min', label: 'Answer Similarity Min', min: 0, max: 1, step: 0.1 }
        ];
      case 'safety':
        return [
          { key: 'toxicity_threshold', label: 'Toxicity Threshold', min: 0, max: 1, step: 0.1 },
          { key: 'hate_speech_threshold', label: 'Hate Speech Threshold', min: 0, max: 1, step: 0.1 },
          { key: 'violence_threshold', label: 'Violence Threshold', min: 0, max: 1, step: 0.1 }
        ];
      case 'performance':
        return [
          { key: 'max_latency_ms', label: 'Max Latency', min: 100, max: 30000, step: 100, unit: 'ms' },
          { key: 'min_throughput_rps', label: 'Min Throughput', min: 0.1, max: 100, step: 0.1, unit: 'RPS' }
        ];
      case 'bias':
        return [
          { key: 'bias_parity_threshold', label: 'Parity Threshold', min: 0, max: 1, step: 0.05 }
        ];
      case 'resilience':
        return [
          { key: 'error_rate_threshold', label: 'Error Rate Threshold', min: 0, max: 1, step: 0.05 },
          { key: 'timeout_threshold', label: 'Timeout Threshold', min: 0, max: 1, step: 0.05 }
        ];
      default:
        return [];
    }
  };

  const renderThresholds = () => {
    const thresholdKeys = getThresholdKeys(suiteId);
    if (thresholdKeys.length === 0) return null;

    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {thresholdKeys.map(({ key, label, min, max, step, unit }) => (
            <div key={key}>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                {label} {unit && `(${unit})`}
              </label>
              <input
                type="number"
                value={thresholds?.[key] || min}
                onChange={(e) => updateThreshold(key, parseFloat(e.target.value) || min)}
                min={min}
                max={max}
                step={step}
                className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
              />
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderConfigContent = () => {
    switch (suiteId) {
      case 'resilience':
        return renderResilienceConfig();
      case 'red_team':
        return renderRedTeamConfig();
      case 'safety':
        return renderSafetyConfig();
      case 'performance':
        return renderPerformanceConfig();
      case 'bias':
        return renderBiasConfig();
      default:
        return null;
    }
  };

  return (
    <div className="border-t border-slate-200 dark:border-slate-700 p-4">
      <button
        onClick={() => setShowConfig(!showConfig)}
        className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors duration-200"
      >
        <Settings className="w-4 h-4" />
        Suite Configuration
        {showConfig ? (
          <ChevronDown className="w-4 h-4" />
        ) : (
          <ChevronRight className="w-4 h-4" />
        )}
      </button>

      <AnimatePresence>
        {showConfig && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.28 }}
            className="mt-4 space-y-6"
          >
            {/* Thresholds Section */}
            {getThresholdKeys(suiteId).length > 0 && (
              <div>
                <button
                  onClick={() => setShowThresholds(!showThresholds)}
                  className="flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors duration-200 mb-3"
                >
                  📊 Thresholds
                  {showThresholds ? (
                    <ChevronDown className="w-3 h-3" />
                  ) : (
                    <ChevronRight className="w-3 h-3" />
                  )}
                </button>
                
                <AnimatePresence>
                  {showThresholds && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.28 }}
                    >
                      {renderThresholds()}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}
            
            {/* Suite Configuration */}
            {renderConfigContent()}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
