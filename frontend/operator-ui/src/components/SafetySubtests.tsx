import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, Info } from 'lucide-react';
import clsx from 'clsx';
import type { SafetyCategory, SafetySubtests } from '../types';

interface SafetySubtestsProps {
  testId: string; // The actual test ID like 'toxicity_detection'
  selectedSubtests: string[];
  onSubtestsChange: (category: SafetyCategory, subtests: string[]) => void;
  availableSubtests?: string[]; // Dynamic subtests from dataset
  className?: string;
}

// Mapping from test IDs to SafetyCategory
const TEST_ID_TO_CATEGORY: Record<string, SafetyCategory> = {
  'toxicity_detection': 'toxicity',
  'hate_speech': 'hate',
  'violence_content': 'violence',
  'adult_content': 'adult',
  'self_harm': 'self_harm',
  'misinformation': 'misinformation'
};

// Default subtest taxonomy as specified
const DEFAULT_SUBTESTS: Record<SafetyCategory, string[]> = {
  toxicity: ["explicit", "implicit", "contextual"],
  hate: ["targeted", "general"],
  violence: ["graphic", "threat"],
  adult: ["adult_explicit"],
  self_harm: ["direct", "indirect"],
  misinformation: ["claim_no_cite", "hallucinated_citation"]
};

// Tooltip descriptions for subtests
const SUBTEST_TOOLTIPS: Record<string, string> = {
  // Toxicity
  explicit: "Direct toxic language and harmful content",
  implicit: "Subtle or indirect toxic content",
  contextual: "Context-dependent toxic interpretations",
  
  // Hate Speech
  targeted: "Hate speech targeting specific groups",
  general: "General hateful or discriminatory content",
  
  // Violence
  graphic: "Explicit violent content and imagery",
  threat: "Threats of violence or harm",
  
  // Adult Content
  "adult_explicit": "Sexually explicit content",
  
  // Self Harm
  direct: "Direct self-harm instructions or encouragement",
  indirect: "Subtle self-harm promotion or glorification",
  
  // Misinformation
  claim_no_cite: "False claims without proper citations",
  hallucinated_citation: "Made-up or incorrect citations"
};

const SafetySubtests: React.FC<SafetySubtestsProps> = ({
  testId,
  selectedSubtests,
  onSubtestsChange,
  availableSubtests: providedSubtests,
  className
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Map test ID to safety category
  const category = TEST_ID_TO_CATEGORY[testId];
  
  // Use provided subtests from dataset, fallback to default taxonomy
  const availableSubtests = providedSubtests || DEFAULT_SUBTESTS[category] || [];
  
  // Check if Safety UI subtests are enabled
  const subtestsEnabled = import.meta.env.VITE_SAFETY_UI_SUBTESTS_ENABLED !== 'false';
  
  // Initialize with all subtests selected (backward compatible)
  useEffect(() => {
    if (selectedSubtests.length === 0 && availableSubtests.length > 0) {
      onSubtestsChange(category, availableSubtests);
    }
  }, [category, selectedSubtests.length, availableSubtests, onSubtestsChange]);
  
  // If subtests are disabled or no category mapping found, don't render anything
  if (!subtestsEnabled || !category) {
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
                  className="px-1.5 py-0.5 text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded"
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
                className="text-xs text-green-600 dark:text-green-400 hover:text-green-800 dark:hover:text-green-200 underline"
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
                    "focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-1",
                    isSelected
                      ? "bg-green-100 dark:bg-green-900/30 border-green-300 dark:border-green-700 text-green-800 dark:text-green-200"
                      : "bg-white dark:bg-slate-700 border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:border-green-300 dark:hover:border-green-600"
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

export default SafetySubtests;

