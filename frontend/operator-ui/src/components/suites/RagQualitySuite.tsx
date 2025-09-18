import React, { useState } from 'react';
import { ChevronDown, ChevronRight, ShieldCheck, BarChart3, Database, Settings } from 'lucide-react';
import CompactGroundTruthPanel from '../CompactGroundTruthPanel';

interface RagQualitySuiteProps {
  isEnabled: boolean;
  onToggle: (enabled: boolean) => void;
  apiBaseUrl: string;
  token: string;
  // Configuration props
  qaSampleSize: string;
  onQaSampleSizeChange: (value: string) => void;
  faithMin: string;
  onFaithMinChange: (value: string) => void;
  crecMin: string;
  onCrecMinChange: (value: string) => void;
  useGroundTruth: boolean;
  onUseGroundTruthChange: (enabled: boolean) => void;
  // Compare Mode props
  compareEnabled?: boolean;
  onCompareEnabledChange?: (enabled: boolean) => void;
  compareAutoSelect?: boolean;
  onCompareAutoSelectChange?: (enabled: boolean) => void;
  compareManualPreset?: string;
  onCompareManualPresetChange?: (preset: string) => void;
  compareManualModel?: string;
  onCompareManualModelChange?: (model: string) => void;
  compareHintTier?: string;
  onCompareHintTierChange?: (tier: string) => void;
  retrievalJsonPath?: string;
}

const RagQualitySuite: React.FC<RagQualitySuiteProps> = ({
  isEnabled,
  onToggle,
  apiBaseUrl,
  token,
  qaSampleSize,
  onQaSampleSizeChange,
  faithMin,
  onFaithMinChange,
  crecMin,
  onCrecMinChange,
  useGroundTruth,
  onUseGroundTruthChange,
  compareEnabled = false,
  onCompareEnabledChange,
  compareAutoSelect = true,
  onCompareAutoSelectChange,
  compareManualPreset = "",
  onCompareManualPresetChange,
  compareManualModel = "",
  onCompareManualModelChange,
  compareHintTier = "",
  onCompareHintTierChange,
  retrievalJsonPath = ""
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [groundTruthDataCount, setGroundTruthDataCount] = useState(0);

  const availableTests = [
    {
      id: 'basic_rag',
      name: 'Basic RAG Quality',
      description: 'Standard faithfulness and context recall evaluation',
      enabled: true,
      metrics: ['faithfulness', 'context_recall']
    },
    {
      id: 'ground_truth_evaluation',
      name: 'Ground Truth Evaluation',
      description: 'Comprehensive 6-metric evaluation with ground truth data',
      enabled: useGroundTruth,
      metrics: ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall', 'answer_correctness', 'answer_similarity']
    }
  ];

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg">
      {/* Suite Header */}
      <div className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <input
              type="checkbox"
              className="accent-brand-600"
              checked={isEnabled}
              onChange={(e) => onToggle(e.target.checked)}
            />
            <div className="flex items-center space-x-2">
              <BarChart3 size={18} className="text-blue-600 dark:text-blue-400" />
              <span className="font-medium text-slate-900 dark:text-slate-100">
                RAG Quality
              </span>
            </div>
            <span className="text-sm text-slate-500 dark:text-slate-400">
              Retrieval-Augmented Generation evaluation
            </span>
          </div>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="btn btn-ghost p-2"
            disabled={!isEnabled}
          >
            {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </button>
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && isEnabled && (
        <div className="border-t border-slate-200 dark:border-slate-700 p-4 space-y-6">
          
          {/* Available Tests */}
          <div>
            <h4 className="font-medium text-slate-900 dark:text-slate-100 mb-3 flex items-center space-x-2">
              <Settings size={16} />
              <span>Available Tests</span>
            </h4>
            <div className="space-y-3">
              {availableTests.map((test) => (
                <div key={test.id} className="border border-slate-200 dark:border-slate-700 rounded-lg p-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-1">
                        <input
                          type="checkbox"
                          className="accent-brand-600"
                          checked={test.enabled}
                          onChange={(e) => {
                            if (test.id === 'ground_truth_evaluation') {
                              onUseGroundTruthChange(e.target.checked);
                            }
                          }}
                          disabled={test.id === 'basic_rag'} // Always enabled
                        />
                        <span className="font-medium text-slate-900 dark:text-slate-100">
                          {test.name}
                        </span>
                      </div>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
                        {test.description}
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {test.metrics.map((metric) => (
                          <span
                            key={metric}
                            className="px-2 py-1 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded"
                          >
                            {metric}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Ground Truth Configuration */}
          {useGroundTruth && (
            <div>
              <h4 className="font-medium text-slate-900 dark:text-slate-100 mb-3 flex items-center space-x-2">
                <ShieldCheck size={16} />
                <span>Ground Truth Configuration</span>
              </h4>
              <div className="border border-slate-200 dark:border-slate-700 rounded-lg p-4">
                <CompactGroundTruthPanel
                  apiBaseUrl={apiBaseUrl}
                  token={token}
                  onDataLoaded={setGroundTruthDataCount}
                />
              </div>
            </div>
          )}

          {/* Compare Mode Configuration */}
          <div>
            <h4 className="font-medium text-slate-900 dark:text-slate-100 mb-3 flex items-center space-x-2">
              <BarChart3 size={16} />
              <span>Compare Mode (optional)</span>
            </h4>
            <div className="border border-slate-200 dark:border-slate-700 rounded-lg p-4 space-y-4">
              {/* Enable Compare Toggle */}
              <div className="flex items-center space-x-3">
                <input
                  type="checkbox"
                  id="compare-enabled"
                  className="checkbox"
                  checked={compareEnabled}
                  onChange={(e) => onCompareEnabledChange?.(e.target.checked)}
                />
                <label htmlFor="compare-enabled" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  Enable Compare with Vendor Model
                </label>
              </div>

              {compareEnabled && (
                <div className="space-y-4 pl-6 border-l-2 border-blue-200 dark:border-blue-800">
                  {/* Auto-select vs Manual */}
                  <div className="space-y-3">
                    <div className="flex items-center space-x-3">
                      <input
                        type="radio"
                        id="compare-auto"
                        name="compare-mode"
                        className="radio"
                        checked={compareAutoSelect}
                        onChange={() => onCompareAutoSelectChange?.(true)}
                      />
                      <label htmlFor="compare-auto" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                        Auto-select baseline (recommended)
                      </label>
                    </div>
                    {compareAutoSelect && (
                      <div className="ml-6 text-sm text-slate-600 dark:text-slate-400">
                        <p className="mb-2">Strategy: same model if known, else near-tier suggestion.</p>
                        {/* Optional tier hint */}
                        <div className="flex items-center space-x-2">
                          <label className="text-xs font-medium">Tier hint (optional):</label>
                          <select
                            className="input text-xs py-1 px-2"
                            value={compareHintTier}
                            onChange={(e) => onCompareHintTierChange?.(e.target.value)}
                          >
                            <option value="">Auto-detect</option>
                            <option value="economy">Economy (mini, haiku, flash)</option>
                            <option value="balanced">Balanced (sonnet, pro, gpt-4o)</option>
                            <option value="premium">Premium (opus, ultra, o4)</option>
                          </select>
                        </div>
                      </div>
                    )}

                    <div className="flex items-center space-x-3">
                      <input
                        type="radio"
                        id="compare-manual"
                        name="compare-mode"
                        className="radio"
                        checked={!compareAutoSelect}
                        onChange={() => onCompareAutoSelectChange?.(false)}
                      />
                      <label htmlFor="compare-manual" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                        Manual select
                      </label>
                    </div>
                    {!compareAutoSelect && (
                      <div className="ml-6 grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                            Vendor Preset
                          </label>
                          <select
                            className="input text-sm"
                            value={compareManualPreset}
                            onChange={(e) => onCompareManualPresetChange?.(e.target.value)}
                          >
                            <option value="">Select vendor...</option>
                            <option value="openai">OpenAI</option>
                            <option value="anthropic">Anthropic</option>
                            <option value="gemini">Gemini</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                            Model
                          </label>
                          <input
                            type="text"
                            className="input text-sm"
                            placeholder="e.g., gpt-4o-mini"
                            value={compareManualModel}
                            onChange={(e) => onCompareManualModelChange?.(e.target.value)}
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Contexts-only checkbox */}
                  <div className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      id="compare-contexts-only"
                      className="checkbox"
                      checked={true}
                      disabled
                    />
                    <label htmlFor="compare-contexts-only" className="text-sm text-slate-600 dark:text-slate-400">
                      Only compare when contexts are present (required)
                    </label>
                  </div>

                  {/* Warning if no contexts JSONPath */}
                  {!retrievalJsonPath && (
                    <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3">
                      <p className="text-sm text-yellow-800 dark:text-yellow-200">
                        <strong>Warning:</strong> No contexts JSONPath configured; comparison may skip all items.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Basic Configuration */}
          <div>
            <h4 className="font-medium text-slate-900 dark:text-slate-100 mb-3 flex items-center space-x-2">
              <Database size={16} />
              <span>Configuration</span>
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Sample Size
                </label>
                <input
                  type="text"
                  className="input"
                  placeholder="empty = all"
                  value={qaSampleSize}
                  onChange={(e) => onQaSampleSizeChange(e.target.value)}
                />
                <small className="text-slate-500 dark:text-slate-400">
                  Number of QA pairs to evaluate
                </small>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Faithfulness Min
                </label>
                <input
                  type="text"
                  className="input"
                  value={faithMin}
                  onChange={(e) => onFaithMinChange(e.target.value)}
                />
                <small className="text-slate-500 dark:text-slate-400">
                  Minimum faithfulness score (0-1)
                </small>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Context Recall Min
                </label>
                <input
                  type="text"
                  className="input"
                  value={crecMin}
                  onChange={(e) => onCrecMinChange(e.target.value)}
                />
                <small className="text-slate-500 dark:text-slate-400">
                  Minimum context recall score (0-1)
                </small>
              </div>
            </div>
          </div>

          {/* Test Summary */}
          <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4">
            <h5 className="font-medium text-slate-900 dark:text-slate-100 mb-2">Test Summary</h5>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-slate-600 dark:text-slate-400">Basic Tests:</span>
                <span className="ml-2 font-medium">2 metrics</span>
              </div>
              {useGroundTruth && (
                <div>
                  <span className="text-slate-600 dark:text-slate-400">Ground Truth:</span>
                  <span className="ml-2 font-medium">6 metrics</span>
                </div>
              )}
              <div>
                <span className="text-slate-600 dark:text-slate-400">Sample Size:</span>
                <span className="ml-2 font-medium">{qaSampleSize || 'All'}</span>
              </div>
              {groundTruthDataCount > 0 && (
                <div>
                  <span className="text-slate-600 dark:text-slate-400">GT Data:</span>
                  <span className="ml-2 font-medium">{groundTruthDataCount} samples</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RagQualitySuite;
