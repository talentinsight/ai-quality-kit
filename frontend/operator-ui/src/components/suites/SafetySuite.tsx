import React, { useState } from 'react';
import { ChevronDown, ChevronRight, ShieldCheck, AlertCircle, Settings, Database } from 'lucide-react';

interface SafetySuiteProps {
  isEnabled: boolean;
  onToggle: (enabled: boolean) => void;
  toxMax: string;
  onToxMaxChange: (value: string) => void;
  attackMutators: string;
}

const SafetySuite: React.FC<SafetySuiteProps> = ({
  isEnabled,
  onToggle,
  toxMax,
  onToxMaxChange,
  attackMutators
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const availableTests = [
    {
      id: 'toxicity_detection',
      name: 'Toxicity Detection',
      description: 'Tests for harmful, toxic, or offensive content generation',
      enabled: true,
      categories: ['Hate speech', 'Harassment', 'Violence', 'Self-harm']
    },
    {
      id: 'content_policy',
      name: 'Content Policy Compliance',
      description: 'Tests adherence to content policies and guidelines',
      enabled: true,
      categories: ['Adult content', 'Violence', 'Illegal activities', 'Misinformation']
    },
    {
      id: 'harmful_content',
      name: 'Harmful Content Detection',
      description: 'Tests for malicious code, illegal activities, and dangerous instructions',
      enabled: true,
      categories: ['Malicious code', 'Illegal activities', 'Dangerous instructions', 'Privacy violations']
    }
  ];

  const estimatedTests = Math.min(50, Math.max(5, parseInt(attackMutators) * 5));

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
              <ShieldCheck size={18} className="text-green-600 dark:text-green-400" />
              <span className="font-medium text-slate-900 dark:text-slate-100">
                Safety
              </span>
            </div>
            <span className="text-sm text-slate-500 dark:text-slate-400">
              Content safety and policy compliance
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
              <span>Safety Categories</span>
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
                          onChange={() => {}} // For now, all are enabled
                          disabled={true}
                        />
                        <span className="font-medium text-slate-900 dark:text-slate-100">
                          {test.name}
                        </span>
                        <AlertCircle size={14} className="text-amber-500" />
                      </div>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
                        {test.description}
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {test.categories.map((category) => (
                          <span
                            key={category}
                            className="px-2 py-1 text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded"
                          >
                            {category}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Configuration */}
          <div>
            <h4 className="font-medium text-slate-900 dark:text-slate-100 mb-3 flex items-center space-x-2">
              <Database size={16} />
              <span>Configuration</span>
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Toxicity Max
                </label>
                <input
                  type="text"
                  className="input"
                  value={toxMax}
                  onChange={(e) => onToxMaxChange(e.target.value)}
                />
                <small className="text-slate-500 dark:text-slate-400">
                  Maximum allowed toxicity score (0-1)
                </small>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Test Variations
                </label>
                <input
                  type="text"
                  className="input"
                  value={attackMutators}
                  disabled
                />
                <small className="text-slate-500 dark:text-slate-400">
                  Based on attack mutators setting
                </small>
              </div>
            </div>
          </div>

          {/* Test Summary */}
          <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4">
            <h5 className="font-medium text-slate-900 dark:text-slate-100 mb-2">Test Summary</h5>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-slate-600 dark:text-slate-400">Categories:</span>
                <span className="ml-2 font-medium">{availableTests.length}</span>
              </div>
              <div>
                <span className="text-slate-600 dark:text-slate-400">Max Toxicity:</span>
                <span className="ml-2 font-medium">{toxMax}</span>
              </div>
              <div>
                <span className="text-slate-600 dark:text-slate-400">Est. Tests:</span>
                <span className="ml-2 font-medium">~{estimatedTests}</span>
              </div>
              <div>
                <span className="text-slate-600 dark:text-slate-400">Policy:</span>
                <span className="ml-2 font-medium text-green-600 dark:text-green-400">Zero violations</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SafetySuite;
