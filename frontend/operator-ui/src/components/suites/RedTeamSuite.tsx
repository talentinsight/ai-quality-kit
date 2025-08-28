import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Shield, AlertTriangle, Settings, Database } from 'lucide-react';

interface RedTeamSuiteProps {
  isEnabled: boolean;
  onToggle: (enabled: boolean) => void;
  attackMutators: string;
  onAttackMutatorsChange: (value: string) => void;
}

const RedTeamSuite: React.FC<RedTeamSuiteProps> = ({
  isEnabled,
  onToggle,
  attackMutators,
  onAttackMutatorsChange
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const availableTests = [
    {
      id: 'prompt_injection',
      name: 'Prompt Injection',
      description: 'Tests for prompt injection vulnerabilities',
      enabled: true,
      attackTypes: ['Direct injection', 'Indirect injection', 'Context manipulation']
    },
    {
      id: 'jailbreak_attempts',
      name: 'Jailbreak Attempts',
      description: 'Tests for system constraint bypassing',
      enabled: true,
      attackTypes: ['Role playing', 'Hypothetical scenarios', 'System override']
    },
    {
      id: 'data_extraction',
      name: 'Data Extraction',
      description: 'Tests for unauthorized data access',
      enabled: true,
      attackTypes: ['Training data extraction', 'System prompt leakage', 'Context extraction']
    }
  ];

  const estimatedTests = Math.max(10, parseInt(attackMutators) * 10);

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
              <Shield size={18} className="text-red-600 dark:text-red-400" />
              <span className="font-medium text-slate-900 dark:text-slate-100">
                Red Team
              </span>
            </div>
            <span className="text-sm text-slate-500 dark:text-slate-400">
              Adversarial testing and attack simulation
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
              <span>Attack Categories</span>
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
                        <AlertTriangle size={14} className="text-orange-500" />
                      </div>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
                        {test.description}
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {test.attackTypes.map((type) => (
                          <span
                            key={type}
                            className="px-2 py-1 text-xs bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded"
                          >
                            {type}
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
                  Attack Mutators
                </label>
                <input
                  type="text"
                  className="input"
                  value={attackMutators}
                  onChange={(e) => onAttackMutatorsChange(e.target.value)}
                />
                <small className="text-slate-500 dark:text-slate-400">
                  Number of attack variations per base attack
                </small>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Success Threshold
                </label>
                <input
                  type="text"
                  className="input"
                  value="0%"
                  disabled
                />
                <small className="text-slate-500 dark:text-slate-400">
                  Zero-tolerance policy for successful attacks
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
                <span className="text-slate-600 dark:text-slate-400">Mutators:</span>
                <span className="ml-2 font-medium">{attackMutators}</span>
              </div>
              <div>
                <span className="text-slate-600 dark:text-slate-400">Est. Tests:</span>
                <span className="ml-2 font-medium">~{estimatedTests}</span>
              </div>
              <div>
                <span className="text-slate-600 dark:text-slate-400">Policy:</span>
                <span className="ml-2 font-medium text-red-600 dark:text-red-400">Zero tolerance</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RedTeamSuite;
