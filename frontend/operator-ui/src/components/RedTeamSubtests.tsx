import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, Info } from 'lucide-react';
import clsx from 'clsx';
import type { RedTeamCategory, RedTeamSubtests } from '../types';

interface RedTeamSubtestsProps {
  category: RedTeamCategory;
  selectedSubtests: string[];
  onSubtestsChange: (category: RedTeamCategory, subtests: string[]) => void;
  availableSubtests?: string[]; // Dynamic subtests from dataset
  className?: string;
}

// Default subtest taxonomy as specified
const DEFAULT_SUBTESTS: Record<RedTeamCategory, string[]> = {
  prompt_injection: ["direct", "indirect", "passage_embedded", "metadata_embedded"],
  jailbreak: ["role_play", "system_override"],
  data_extraction: ["system_prompt", "api_key", "base64"],
  context_poisoning: ["ignore_citations", "contradict_retrieval", "spoof_citations"],
  social_engineering: ["authority", "urgency", "scarcity", "reciprocity", "sympathy"]
};

// Tooltip descriptions for subtests
const SUBTEST_TOOLTIPS: Record<string, string> = {
  // Prompt Injection
  direct: "Direct injection attempts through user input",
  indirect: "Indirect injection through task confusion",
  passage_embedded: "Injects adversarial instructions inside retrieved passages (RAG)",
  metadata_embedded: "Adversarial payload hidden in document metadata (title/alt/etc.)",
  
  // Jailbreak
  role_play: "Role-playing scenarios to bypass constraints",
  system_override: "Direct attempts to override system instructions",
  
  // Data Extraction
  system_prompt: "Attempts to extract system prompts and instructions",
  api_key: "Attempts to extract API keys and credentials",
  base64: "Base64 encoding attempts to bypass filters",
  
  // Context Poisoning
  ignore_citations: "Instructions to ignore retrieved context",
  contradict_retrieval: "Force contradiction of retrieved information",
  spoof_citations: "Inject false authoritative claims",
  
  // Social Engineering
  authority: "Authority impersonation attacks",
  urgency: "Urgency-based pressure tactics",
  scarcity: "Scarcity-based manipulation",
  reciprocity: "Reciprocity-based emotional manipulation",
  sympathy: "Sympathy-based emotional manipulation"
};

const RedTeamSubtests: React.FC<RedTeamSubtestsProps> = ({
  category,
  selectedSubtests,
  onSubtestsChange,
  availableSubtests: providedSubtests,
  className
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Use provided subtests from dataset, fallback to default taxonomy
  const availableSubtests = providedSubtests || DEFAULT_SUBTESTS[category] || [];
  
  // Check if Red Team UI subtests are enabled
  const subtestsEnabled = import.meta.env.VITE_REDTEAM_UI_SUBTESTS_ENABLED !== 'false';
  
  // Initialize with all subtests selected (backward compatible)
  useEffect(() => {
    if (selectedSubtests.length === 0 && availableSubtests.length > 0) {
      onSubtestsChange(category, availableSubtests);
    }
  }, [category, selectedSubtests.length, availableSubtests, onSubtestsChange]);
  
  // If subtests are disabled, don't render anything
  if (!subtestsEnabled) {
    return null;
  }

  const handleSubtestToggle = (subtest: string) => {
    const newSubtests = selectedSubtests.includes(subtest)
      ? selectedSubtests.filter(s => s !== subtest)
      : [...selectedSubtests, subtest];
    onSubtestsChange(category, newSubtests);
  };

  const handleSelectAll = () => {
    onSubtestsChange(category, availableSubtests);
  };

  const handleSelectNone = () => {
    onSubtestsChange(category, []);
  };

  const formatSubtestName = (subtest: string) => {
    return subtest.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };

  if (availableSubtests.length === 0) {
    return null;
  }

  return (
    <div className={clsx("mt-2", className)}>
      {/* Subtests Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center space-x-1 text-xs text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
          aria-expanded={isExpanded}
          aria-controls={`subtests-${category}`}
        >
          {isExpanded ? (
            <ChevronDown size={12} />
          ) : (
            <ChevronRight size={12} />
          )}
          <span>Subtests</span>
        </button>
        
        <div className="flex items-center space-x-2">
          <span className="text-xs text-slate-500 dark:text-slate-400">
            ({selectedSubtests.length} selected)
          </span>
          {!isExpanded && (
            <div className="flex space-x-1">
              {selectedSubtests.slice(0, 3).map(subtest => (
                <span
                  key={subtest}
                  className="px-1.5 py-0.5 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded"
                  title={SUBTEST_TOOLTIPS[subtest]}
                >
                  {formatSubtestName(subtest)}
                </span>
              ))}
              {selectedSubtests.length > 3 && (
                <span className="px-1.5 py-0.5 text-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded">
                  +{selectedSubtests.length - 3}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Expanded Subtests */}
      {isExpanded && (
        <div 
          id={`subtests-${category}`}
          className="mt-2 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-200 dark:border-slate-700"
        >
          {/* Select All/None Controls */}
          <div className="flex justify-between items-center mb-3">
            <div className="flex space-x-2">
              <button
                onClick={handleSelectAll}
                className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200 underline"
              >
                Select All
              </button>
              <button
                onClick={handleSelectNone}
                className="text-xs text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 underline"
              >
                Select None
              </button>
            </div>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {selectedSubtests.length}/{availableSubtests.length} selected
            </span>
          </div>

          {/* Subtest Chips */}
          <div className="flex flex-wrap gap-2">
            {availableSubtests.map(subtest => {
              const isSelected = selectedSubtests.includes(subtest);
              return (
                <button
                  key={subtest}
                  onClick={() => handleSubtestToggle(subtest)}
                  className={clsx(
                    "group relative flex items-center space-x-1 px-3 py-1.5 text-xs rounded-full border transition-all duration-200",
                    "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1",
                    isSelected
                      ? "bg-blue-100 dark:bg-blue-900/30 border-blue-300 dark:border-blue-700 text-blue-800 dark:text-blue-200"
                      : "bg-white dark:bg-slate-700 border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:border-blue-300 dark:hover:border-blue-600"
                  )}
                  aria-pressed={isSelected}
                  title={SUBTEST_TOOLTIPS[subtest]}
                >
                  <span>{formatSubtestName(subtest)}</span>
                  {SUBTEST_TOOLTIPS[subtest] && (
                    <Info size={10} className="opacity-60 group-hover:opacity-100" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Keyboard Accessibility Note */}
          <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            Use Space or Enter to toggle subtests. Tab to navigate.
          </div>
        </div>
      )}
    </div>
  );
};

export default RedTeamSubtests;
