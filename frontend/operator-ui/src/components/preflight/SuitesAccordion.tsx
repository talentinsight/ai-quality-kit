import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Database, Shield, Zap, Scale, ChevronDown, ChevronRight,
  Clock, DollarSign, CheckCircle2, Settings
} from 'lucide-react';
import { usePreflightStore } from '../../stores/preflightStore';
import SpecialistSuites from './SpecialistSuites';
import type { DataRequirements } from '../../types/metrics';

interface SuitesAccordionProps {
  onRagDataClick: () => void;
  dataStatus?: Partial<DataRequirements>;
  onSelectionChange?: (selectedTests: Record<string, string[]>) => void;
  onEphemeralIdsChange?: (ephemeralIds: Record<string, Record<string, string>>) => void;
}

export default function SuitesAccordion({ 
  onRagDataClick, 
  dataStatus = {},
  onSelectionChange,
  onEphemeralIdsChange
}: SuitesAccordionProps) {
  const { llmType, ragOptions, updateRagOptions } = usePreflightStore();
  const [hasGroundTruth, setHasGroundTruth] = useState(false);
  const [showAdvancedRag, setShowAdvancedRag] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}
      className="space-y-4"
    >
      {/* Ground Truth Question - Only for RAG */}
      {llmType === 'rag' && (
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
          <label className="block text-sm font-semibold mb-3 text-slate-900 dark:text-slate-100">
            Ground Truth Data Availability
          </label>
          <div className="flex gap-3">
            <label className="flex items-center gap-2 px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-sm">
              <input 
                type="radio" 
                name="groundTruth" 
                value="no" 
                className="w-4 h-4 text-blue-600" 
                checked={!hasGroundTruth}
                onChange={() => setHasGroundTruth(false)}
              />
              📊 No Ground Truth Available
            </label>
            <label className="flex items-center gap-2 px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-sm">
              <input 
                type="radio" 
                name="groundTruth" 
                value="yes" 
                className="w-4 h-4 text-blue-600" 
                checked={hasGroundTruth}
                onChange={() => setHasGroundTruth(true)}
              />
              🎯 Ground Truth Available
            </label>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
            {hasGroundTruth 
              ? "With ground truth: 8 RAG evaluation metrics available (Faithfulness, Context Recall, Answer Relevancy, Context Precision, Answer Correctness, Answer Similarity, Context Entities Recall, Context Relevancy)"
              : "Without ground truth: 3 basic RAG metrics (Faithfulness, Context Recall, Answer Relevancy)"
            }
          </p>
        </div>
      )}

      {/* Advanced RAG Options - Only for RAG */}
      {llmType === 'rag' && (
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
          <button
            onClick={() => setShowAdvancedRag(!showAdvancedRag)}
            className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100 hover:text-blue-600 dark:hover:text-blue-400 transition-colors duration-200"
          >
            <Settings className="w-4 h-4" />
            Advanced RAG Options
            {showAdvancedRag ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
          </button>

          <AnimatePresence>
            {showAdvancedRag && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.28 }}
                className="mt-4 space-y-4"
              >
                {/* Retrieval Configuration */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">
                      Retrieved Contexts JSONPath
                    </label>
                    <input
                      type="text"
                      value={ragOptions?.retrievalJsonPath || ''}
                      onChange={(e) => updateRagOptions({ retrievalJsonPath: e.target.value })}
                      placeholder="$.contexts[*].text"
                      className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:border-blue-500 focus:outline-none transition-colors duration-200"
                    />
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                      JSONPath to extract retrieved contexts for recall@k, MRR@k, NDCG@k metrics
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">
                      Top-K (for reporting)
                    </label>
                    <input
                      type="number"
                      value={ragOptions?.topK || 5}
                      onChange={(e) => updateRagOptions({ topK: parseInt(e.target.value) || 5 })}
                      min="1"
                      max="20"
                      className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 focus:border-blue-500 focus:outline-none transition-colors duration-200"
                    />
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                      Number of top results to consider for retrieval metrics
                    </p>
                  </div>
                </div>

                {/* Run Profile */}
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">
                    Run Profile
                  </label>
                  <div className="flex gap-3">
                    <label className="flex items-center gap-2 px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-sm">
                      <input 
                        type="radio" 
                        name="runProfile" 
                        value="smoke" 
                        className="w-4 h-4 text-blue-600" 
                        checked={ragOptions?.runProfile === 'smoke'}
                        onChange={() => updateRagOptions({ runProfile: 'smoke' })}
                      />
                      🚀 Smoke (20 samples)
                    </label>
                    <label className="flex items-center gap-2 px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-sm">
                      <input 
                        type="radio" 
                        name="runProfile" 
                        value="full" 
                        className="w-4 h-4 text-blue-600" 
                        checked={ragOptions?.runProfile === 'full'}
                        onChange={() => updateRagOptions({ runProfile: 'full' })}
                      />
                      🎯 Full (all samples)
                    </label>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    Smoke: Quick test with limited samples. Full: Complete evaluation with all data.
                  </p>
                </div>

                {/* Compare Mode */}
                <div>
                  <label className="flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">
                    <input
                      type="checkbox"
                      checked={ragOptions?.compareMode?.enabled || false}
                      onChange={(e) => updateRagOptions({ 
                        compareMode: { 
                          ...ragOptions?.compareMode, 
                          enabled: e.target.checked 
                        } 
                      })}
                      className="w-4 h-4 text-blue-600 rounded"
                    />
                    Enable Compare with Vendor Model
                  </label>
                  
                  {ragOptions?.compareMode?.enabled && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      transition={{ duration: 0.28 }}
                      className="ml-6 space-y-3"
                    >
                      <div className="flex gap-3">
                        <label className="flex items-center gap-2 px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-sm">
                          <input 
                            type="radio" 
                            name="compareSelect" 
                            value="auto" 
                            className="w-4 h-4 text-blue-600" 
                            checked={ragOptions?.compareMode?.autoSelect !== false}
                            onChange={() => updateRagOptions({ 
                              compareMode: { 
                                enabled: ragOptions?.compareMode?.enabled || false,
                                ...ragOptions?.compareMode, 
                                autoSelect: true 
                              } 
                            })}
                          />
                          Auto-select baseline
                        </label>
                        <label className="flex items-center gap-2 px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-sm">
                          <input 
                            type="radio" 
                            name="compareSelect" 
                            value="manual" 
                            className="w-4 h-4 text-blue-600" 
                            checked={ragOptions?.compareMode?.autoSelect === false}
                            onChange={() => updateRagOptions({ 
                              compareMode: { 
                                enabled: ragOptions?.compareMode?.enabled || false,
                                ...ragOptions?.compareMode, 
                                autoSelect: false 
                              } 
                            })}
                          />
                          Manual selection
                        </label>
                      </div>

                      {ragOptions?.compareMode?.autoSelect === false && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                              Manual Preset
                            </label>
                            <input
                              type="text"
                              value={ragOptions?.compareMode?.manualPreset || ''}
                              onChange={(e) => updateRagOptions({ 
                                compareMode: { 
                                  enabled: ragOptions?.compareMode?.enabled || false,
                                  ...ragOptions?.compareMode, 
                                  manualPreset: e.target.value 
                                } 
                              })}
                              placeholder="openai"
                              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:border-blue-500 focus:outline-none transition-colors duration-200"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                              Manual Model
                            </label>
                            <input
                              type="text"
                              value={ragOptions?.compareMode?.manualModel || ''}
                              onChange={(e) => updateRagOptions({ 
                                compareMode: { 
                                  enabled: ragOptions?.compareMode?.enabled || false,
                                  ...ragOptions?.compareMode, 
                                  manualModel: e.target.value 
                                } 
                              })}
                              placeholder="gpt-4"
                              className="w-full px-3 py-2 text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:border-blue-500 focus:outline-none transition-colors duration-200"
                            />
                          </div>
                        </div>
                      )}
                    </motion.div>
                  )}
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    Compare your primary model against a vendor baseline using the same retrieved contexts.
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
      
      <SpecialistSuites
        llmType={llmType || 'plain'}
        hasGroundTruth={hasGroundTruth}
        dataStatus={dataStatus}
        onSelectionChange={onSelectionChange || (() => {})}
        onShowDataRequirements={onRagDataClick}
        onEphemeralIdsChange={onEphemeralIdsChange}
      />
    </motion.div>
  );
}