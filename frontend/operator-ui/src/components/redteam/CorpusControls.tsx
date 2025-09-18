/**
 * Red Team Corpus Controls component for managing attack corpus settings
 */

import React, { useState } from 'react';
import { Shield, Database, Shuffle, Filter, Info, AlertTriangle } from 'lucide-react';
import clsx from 'clsx';

interface CorpusInfo {
  builtin_available: boolean;
  builtin_version: string;
  builtin_hash: string;
  builtin_count: number;
  families: string[];
  mutators: string[];
  taxonomy_version: string;
}

interface MutatorConfig {
  enabled: boolean;
  mutators: string[];
  max_variants_per_item: number;
}

interface SamplingConfig {
  enabled: boolean;
  qa_sample_size?: number;
}

interface CorpusControlsProps {
  corpusInfo: CorpusInfo;
  mutatorConfig: MutatorConfig;
  samplingConfig: SamplingConfig;
  userCorpusAttached: boolean;
  reusedCount: number;
  onMutatorConfigChange: (config: MutatorConfig) => void;
  onSamplingConfigChange: (config: SamplingConfig) => void;
  className?: string;
}

const MUTATOR_DESCRIPTIONS = {
  'insert_zero_width': 'Insert zero-width spaces between words',
  'unicode_confusables_swap': 'Replace characters with Unicode confusables',
  'add_roleplay_wrappers': 'Wrap prompts in roleplay scenarios',
  'wrap_in_markdown': 'Wrap prompts in markdown code blocks',
  'translate_en_tr': 'Translate common phrases EN↔TR',
  'obfuscate_base64': 'Encode prompts in Base64',
  'obfuscate_hex': 'Encode prompts in hexadecimal',
  'obfuscate_rot': 'Apply ROT13/ROT47 encoding',
  'add_polite_preface': 'Add polite prefaces to prompts',
  'double_prompting': 'Apply double prompting technique'
};

export default function CorpusControls({
  corpusInfo,
  mutatorConfig,
  samplingConfig,
  userCorpusAttached,
  reusedCount,
  onMutatorConfigChange,
  onSamplingConfigChange,
  className = ""
}: CorpusControlsProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleMutatorToggle = (mutator: string) => {
    const newMutators = mutatorConfig.mutators.includes(mutator)
      ? mutatorConfig.mutators.filter(m => m !== mutator)
      : [...mutatorConfig.mutators, mutator];
    
    onMutatorConfigChange({
      ...mutatorConfig,
      mutators: newMutators
    });
  };

  const handleMutatorEnabledChange = (enabled: boolean) => {
    onMutatorConfigChange({
      ...mutatorConfig,
      enabled
    });
  };

  const handleSamplingEnabledChange = (enabled: boolean) => {
    onSamplingConfigChange({
      ...samplingConfig,
      enabled
    });
  };

  const handleSampleSizeChange = (size: number) => {
    onSamplingConfigChange({
      ...samplingConfig,
      qa_sample_size: size
    });
  };

  return (
    <div className={clsx("bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700", className)}>
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database size={20} className="text-red-600 dark:text-red-400" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Attack Corpus
            </h3>
          </div>
          
          <div className="flex items-center gap-2">
            {reusedCount > 0 && (
              <div className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                <Shuffle size={12} />
                Reused from Preflight: {reusedCount}
              </div>
            )}
            
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              {showAdvanced ? 'Hide Advanced' : 'Show Advanced'}
            </button>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Corpus Status */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Built-in Corpus</h4>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                {corpusInfo.builtin_available ? (
                  <Shield size={16} className="text-green-600 dark:text-green-400" />
                ) : (
                  <AlertTriangle size={16} className="text-red-600 dark:text-red-400" />
                )}
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {corpusInfo.builtin_available ? 'Available' : 'Unavailable'}
                </span>
              </div>
              
              {corpusInfo.builtin_available && (
                <>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Version: {corpusInfo.builtin_version}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Items: {corpusInfo.builtin_count.toLocaleString()}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Families: {corpusInfo.families.length}
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">User Corpus</h4>
            <div className="flex items-center gap-2">
              {userCorpusAttached ? (
                <Shield size={16} className="text-blue-600 dark:text-blue-400" />
              ) : (
                <Info size={16} className="text-gray-400" />
              )}
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {userCorpusAttached ? 'Attached' : 'None'}
              </span>
            </div>
          </div>
        </div>

        {/* Sampling Controls */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={samplingConfig.enabled}
                onChange={(e) => handleSamplingEnabledChange(e.target.checked)}
                className="rounded border-gray-300 text-red-600 focus:ring-red-500"
              />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Enable Sampling
              </span>
            </label>
            
            <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
              <Filter size={12} />
              Limit corpus size for faster execution
            </div>
          </div>

          {samplingConfig.enabled && (
            <div className="ml-6 space-y-2">
              <label className="block text-sm text-gray-600 dark:text-gray-400">
                Sample Size
              </label>
              <input
                type="number"
                min="1"
                max="1000"
                value={samplingConfig.qa_sample_size || ''}
                onChange={(e) => handleSampleSizeChange(parseInt(e.target.value) || 0)}
                placeholder="e.g., 50"
                className="w-24 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-red-500 focus:border-red-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
              />
              <div className="text-xs text-gray-500 dark:text-gray-400">
                Items to test (ensures family diversity)
              </div>
            </div>
          )}
        </div>

        {/* Mutator Controls */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={mutatorConfig.enabled}
                onChange={(e) => handleMutatorEnabledChange(e.target.checked)}
                className="rounded border-gray-300 text-red-600 focus:ring-red-500"
              />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Enable Mutators
              </span>
            </label>
            
            <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
              <Shuffle size={12} />
              Generate attack variants
            </div>
          </div>

          {mutatorConfig.enabled && (
            <div className="ml-6 space-y-3">
              <div className="flex items-center gap-4">
                <label className="text-sm text-gray-600 dark:text-gray-400">
                  Max variants per item:
                </label>
                <input
                  type="number"
                  min="1"
                  max="5"
                  value={mutatorConfig.max_variants_per_item}
                  onChange={(e) => onMutatorConfigChange({
                    ...mutatorConfig,
                    max_variants_per_item: parseInt(e.target.value) || 1
                  })}
                  className="w-16 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-red-500 focus:border-red-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                />
              </div>

              {showAdvanced && (
                <div className="space-y-2">
                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Available Mutators
                  </div>
                  
                  <div className="grid grid-cols-1 gap-2 max-h-48 overflow-y-auto">
                    {corpusInfo.mutators.map((mutator) => (
                      <label key={mutator} className="flex items-start gap-2 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700">
                        <input
                          type="checkbox"
                          checked={mutatorConfig.mutators.includes(mutator)}
                          onChange={() => handleMutatorToggle(mutator)}
                          className="mt-0.5 rounded border-gray-300 text-red-600 focus:ring-red-500"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
                            {mutator.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                          </div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            {MUTATOR_DESCRIPTIONS[mutator as keyof typeof MUTATOR_DESCRIPTIONS] || 'Advanced text transformation'}
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Advanced Info */}
        {showAdvanced && corpusInfo.builtin_available && (
          <div className="pt-3 border-t border-gray-200 dark:border-gray-700">
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Corpus Details
              </h4>
              
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <div className="text-gray-500 dark:text-gray-400">Hash</div>
                  <div className="font-mono text-gray-700 dark:text-gray-300 truncate">
                    {corpusInfo.builtin_hash.split(':').pop()?.substring(0, 16)}...
                  </div>
                </div>
                
                <div>
                  <div className="text-gray-500 dark:text-gray-400">Taxonomy</div>
                  <div className="text-gray-700 dark:text-gray-300">
                    v{corpusInfo.taxonomy_version}
                  </div>
                </div>
              </div>
              
              <div>
                <div className="text-gray-500 dark:text-gray-400 text-xs mb-1">
                  Attack Families ({corpusInfo.families.length})
                </div>
                <div className="flex flex-wrap gap-1">
                  {corpusInfo.families.slice(0, 8).map((family) => (
                    <span
                      key={family}
                      className="inline-block px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded"
                    >
                      {family.replace(/_/g, ' ')}
                    </span>
                  ))}
                  {corpusInfo.families.length > 8 && (
                    <span className="inline-block px-2 py-1 text-xs text-gray-500 dark:text-gray-400">
                      +{corpusInfo.families.length - 8} more
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
