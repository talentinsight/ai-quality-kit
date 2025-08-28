import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Zap, Clock, Settings, Database } from 'lucide-react';

interface PerformanceSuiteProps {
  isEnabled: boolean;
  onToggle: (enabled: boolean) => void;
  perfRepeats: string;
  onPerfRepeatsChange: (value: string) => void;
}

const PerformanceSuite: React.FC<PerformanceSuiteProps> = ({
  isEnabled,
  onToggle,
  perfRepeats,
  onPerfRepeatsChange
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const availableTests = [
    {
      id: 'cold_start_latency',
      name: 'Cold Start Latency',
      description: 'Measures initial response time for first requests',
      enabled: true,
      metrics: ['First response time', 'Initialization overhead', 'Cold start frequency']
    },
    {
      id: 'warm_performance',
      name: 'Warm Performance',
      description: 'Measures response time for subsequent requests',
      enabled: true,
      metrics: ['Average response time', 'P95 latency', 'P99 latency']
    },
    {
      id: 'throughput_testing',
      name: 'Throughput Testing',
      description: 'Measures system capacity under load',
      enabled: true,
      metrics: ['Requests per second', 'Concurrent capacity', 'Resource utilization']
    }
  ];

  const estimatedTests = parseInt(perfRepeats) || 2;

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
              <Zap size={18} className="text-yellow-600 dark:text-yellow-400" />
              <span className="font-medium text-slate-900 dark:text-slate-100">
                Performance
              </span>
            </div>
            <span className="text-sm text-slate-500 dark:text-slate-400">
              Response latency and throughput testing
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
              <span>Performance Tests</span>
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
                        <Clock size={14} className="text-blue-500" />
                      </div>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
                        {test.description}
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {test.metrics.map((metric) => (
                          <span
                            key={metric}
                            className="px-2 py-1 text-xs bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300 rounded"
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

          {/* Configuration */}
          <div>
            <h4 className="font-medium text-slate-900 dark:text-slate-100 mb-3 flex items-center space-x-2">
              <Database size={16} />
              <span>Configuration</span>
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Performance Repeats
                </label>
                <input
                  type="text"
                  className="input"
                  value={perfRepeats}
                  onChange={(e) => onPerfRepeatsChange(e.target.value)}
                />
                <small className="text-slate-500 dark:text-slate-400">
                  Number of performance test iterations
                </small>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Cold Window
                </label>
                <input
                  type="text"
                  className="input"
                  value="120s"
                  disabled
                />
                <small className="text-slate-500 dark:text-slate-400">
                  Time window to consider cold start
                </small>
              </div>
            </div>
          </div>

          {/* Performance Thresholds */}
          <div>
            <h4 className="font-medium text-slate-900 dark:text-slate-100 mb-3">Performance Thresholds</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3">
                <div className="text-sm font-medium text-slate-700 dark:text-slate-300">P95 Latency</div>
                <div className="text-lg font-bold text-slate-900 dark:text-slate-100">&lt; 2000ms</div>
              </div>
              <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3">
                <div className="text-sm font-medium text-slate-700 dark:text-slate-300">Cold Start</div>
                <div className="text-lg font-bold text-slate-900 dark:text-slate-100">&lt; 5000ms</div>
              </div>
              <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3">
                <div className="text-sm font-medium text-slate-700 dark:text-slate-300">Warm Avg</div>
                <div className="text-lg font-bold text-slate-900 dark:text-slate-100">&lt; 1000ms</div>
              </div>
            </div>
          </div>

          {/* Test Summary */}
          <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4">
            <h5 className="font-medium text-slate-900 dark:text-slate-100 mb-2">Test Summary</h5>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-slate-600 dark:text-slate-400">Test Types:</span>
                <span className="ml-2 font-medium">{availableTests.length}</span>
              </div>
              <div>
                <span className="text-slate-600 dark:text-slate-400">Repeats:</span>
                <span className="ml-2 font-medium">{perfRepeats}</span>
              </div>
              <div>
                <span className="text-slate-600 dark:text-slate-400">Total Tests:</span>
                <span className="ml-2 font-medium">{estimatedTests}</span>
              </div>
              <div>
                <span className="text-slate-600 dark:text-slate-400">Focus:</span>
                <span className="ml-2 font-medium text-yellow-600 dark:text-yellow-400">Latency</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PerformanceSuite;
