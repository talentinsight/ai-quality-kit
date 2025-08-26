import React, { useState } from 'react';
import { RunConfig } from '../types/runConfig';
import { ChevronDown, ChevronUp, Play, Download, Settings, Database, Shield, Zap } from 'lucide-react';

interface InlineDrawerProps {
  config: RunConfig;
  onUpdate: (updates: Partial<RunConfig>) => void;
  onRun: () => void;
  isRunning: boolean;
  onClose: () => void;
}

const InlineDrawer: React.FC<InlineDrawerProps> = ({
  config,
  onUpdate,
  onRun,
  isRunning,
  onClose
}) => {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['basic']));

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(section)) {
      newExpanded.delete(section);
    } else {
      newExpanded.add(section);
    }
    setExpandedSections(newExpanded);
  };

  const isSectionExpanded = (section: string) => expandedSections.has(section);

  const renderBasicSection = () => (
    <div className="space-y-4">
      {/* Target Mode */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Target Mode
        </label>
        <select
          value={config.target_mode || ''}
          onChange={(e) => onUpdate({ target_mode: e.target.value as 'api' | 'mcp' | null })}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Select mode</option>
          <option value="api">API Endpoint</option>
          <option value="mcp">MCP Server</option>
        </select>
      </div>

      {/* Base URL */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {config.target_mode === 'api' ? 'API Base URL' : 'MCP Server URL'}
        </label>
        <input
          type="text"
          value={config.base_url || ''}
          onChange={(e) => onUpdate({ base_url: e.target.value })}
          placeholder={config.target_mode === 'api' ? 'http://localhost:8000' : 'stdio:///path/to/mcp-server'}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Bearer Token */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Bearer Token (Optional)
        </label>
        <input
          type="password"
          value={config.bearer_token || ''}
          onChange={(e) => onUpdate({ bearer_token: e.target.value })}
          placeholder="Bearer token for authentication"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Provider */}
      {config.target_mode === 'api' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            AI Provider
          </label>
          <select
            value={config.provider || ''}
            onChange={(e) => onUpdate({ provider: e.target.value as any })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select provider</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="gemini">Gemini</option>
            <option value="custom_rest">Custom REST</option>
            <option value="mock">Mock</option>
          </select>
        </div>
      )}

      {/* Model */}
      {config.provider && ['openai', 'anthropic', 'gemini', 'mock'].includes(config.provider) && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Model
          </label>
          <input
            type="text"
            value={config.model || ''}
            onChange={(e) => onUpdate({ model: e.target.value })}
            placeholder={config.provider === 'openai' ? 'gpt-4' : config.provider === 'anthropic' ? 'claude-3-opus' : 'gemini-pro'}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      )}
    </div>
  );

  const renderTestSuitesSection = () => (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Test Suites
      </label>
      {[
        { id: 'rag_quality', name: 'RAG Quality', description: 'Faithfulness, context recall' },
        { id: 'red_team', name: 'Red Team', description: 'Adversarial testing' },
        { id: 'safety', name: 'Safety', description: 'Harmful content detection' },
        { id: 'performance', name: 'Performance', description: 'Latency testing' },
        { id: 'regression', name: 'Regression', description: 'Baseline comparison' },
        { id: 'resilience', name: 'Resilience', description: 'Failure handling' },
        { id: 'compliance_smoke', name: 'Compliance', description: 'PII scanning, RBAC' },
        { id: 'bias_smoke', name: 'Bias', description: 'Demographic parity' }
      ].map((suite) => (
        <label key={suite.id} className="flex items-start space-x-3">
          <input
            type="checkbox"
            checked={config.test_suites.includes(suite.id)}
            onChange={(e) => {
              if (e.target.checked) {
                onUpdate({ test_suites: [...config.test_suites, suite.id] });
              } else {
                onUpdate({ test_suites: config.test_suites.filter(s => s !== suite.id) });
              }
            }}
            className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
          />
          <div>
            <span className="text-sm font-medium text-gray-900">{suite.name}</span>
            <p className="text-xs text-gray-500">{suite.description}</p>
          </div>
        </label>
      ))}
    </div>
  );

  const renderThresholdsSection = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Faithfulness Min
        </label>
        <input
          type="number"
          min="0"
          max="1"
          step="0.1"
          value={config.thresholds?.faithfulness_min || ''}
          onChange={(e) => onUpdate({ 
            thresholds: { 
              ...config.thresholds, 
              faithfulness_min: e.target.value ? parseFloat(e.target.value) : undefined 
            } 
          })}
          placeholder="0.8"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Context Recall Min
        </label>
        <input
          type="number"
          min="0"
          max="1"
          step="0.1"
          value={config.thresholds?.context_recall_min || ''}
          onChange={(e) => onUpdate({ 
            thresholds: { 
              ...config.thresholds, 
              context_recall_min: e.target.value ? parseFloat(e.target.value) : undefined 
            } 
          })}
          placeholder="0.7"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Toxicity Max
        </label>
        <input
          type="number"
          min="0"
          max="1"
          step="0.1"
          value={config.thresholds?.toxicity_max || ''}
          onChange={(e) => onUpdate({ 
            thresholds: { 
              ...config.thresholds, 
              toxicity_max: e.target.value ? parseFloat(e.target.value) : undefined 
            } 
          })}
          placeholder="0.1"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
    </div>
  );

  const renderVolumesSection = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          QA Sample Size
        </label>
        <input
          type="number"
          min="1"
          max="100"
          value={config.volumes?.qa_sample_size || ''}
          onChange={(e) => onUpdate({ 
            volumes: { 
              ...config.volumes, 
              qa_sample_size: e.target.value ? parseInt(e.target.value) : undefined 
            } 
          })}
          placeholder="8"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Attack Mutators
        </label>
        <input
          type="number"
          min="1"
          max="10"
          value={config.volumes?.attack_mutators || ''}
          onChange={(e) => onUpdate({ 
            volumes: { 
              ...config.volumes, 
              attack_mutators: e.target.value ? parseInt(e.target.value) : undefined 
            } 
          })}
          placeholder="1"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Performance Repeats
        </label>
        <input
          type="number"
          min="1"
          max="10"
          value={config.volumes?.perf_repeats || ''}
          onChange={(e) => onUpdate({ 
            volumes: { 
              ...config.volumes, 
              perf_repeats: e.target.value ? parseInt(e.target.value) : undefined 
            } 
          })}
          placeholder="2"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
    </div>
  );

  const renderTestDataSection = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Test Data Bundle ID
        </label>
        <input
          type="text"
          value={config.testdata_id || ''}
          onChange={(e) => onUpdate({ testdata_id: e.target.value || null })}
          placeholder="Existing bundle ID or leave empty to create new"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      
      {!config.testdata_id && (
        <div className="text-sm text-gray-600">
          <p>No existing bundle selected. Test data will be created during execution.</p>
        </div>
      )}
    </div>
  );

  const renderResilienceSection = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Resilience Mode
        </label>
        <select
          value={config.resilience?.mode || 'passive'}
          onChange={(e) => onUpdate({ 
            resilience: { 
              ...config.resilience, 
              mode: e.target.value as 'passive' | 'active' 
            } 
          })}
          className="w-full rounded-2xl border px-3 py-2 focus:ring-2 focus:ring-gray-300"
        >
          <option value="passive">Passive</option>
          <option value="active">Active</option>
        </select>
      </div>
    </div>
  );

  const renderComplianceSection = () => (
    <div className="space-y-4">
      <div>
        <label className="flex items-center space-x-2">
          <input
            type="checkbox"
            checked={config.compliance?.enable_pii_scanning || false}
            onChange={(e) => onUpdate({ 
              compliance: { 
                ...config.compliance, 
                enable_pii_scanning: e.target.checked 
              } 
            })}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="text-sm font-medium text-gray-700">Enable PII Scanning</span>
        </label>
      </div>
    </div>
  );

  const renderBiasSection = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Max Bias Test Pairs
        </label>
        <input
          type="number"
          min="1"
          max="100"
          value={config.bias?.max_pairs || 10}
          onChange={(e) => onUpdate({ 
            bias: { 
              ...config.bias, 
              max_pairs: parseInt(e.target.value) || 10 
            } 
          })}
          className="w-full rounded-2xl border px-3 py-2 focus:ring-2 focus:ring-gray-300"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Demographic Groups (CSV)
        </label>
        <input
          type="text"
          value={config.bias?.groups_csv || 'female|male;young|elderly'}
          onChange={(e) => onUpdate({ 
            bias: { 
              ...config.bias, 
              groups_csv: e.target.value 
            } 
          })}
          placeholder="female|male;young|elderly"
          className="w-full rounded-2xl border px-3 py-2 focus:ring-2 focus:ring-gray-300"
        />
      </div>
    </div>
  );

  return (
    <div className="w-96 bg-white border-l border-gray-200 overflow-y-auto">
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-gray-900">Configuration</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-full transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Basic Settings */}
        <div className="mb-6">
          <button
            onClick={() => toggleSection('basic')}
            className="flex items-center justify-between w-full text-left text-sm font-medium text-gray-900 mb-3"
          >
            <span className="flex items-center">
              <Settings className="w-4 h-4 mr-2" />
              Basic Settings
            </span>
            {isSectionExpanded('basic') ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {isSectionExpanded('basic') && renderBasicSection()}
        </div>

        {/* Test Suites */}
        <div className="mb-6">
          <button
            onClick={() => toggleSection('suites')}
            className="flex items-center justify-between w-full text-left text-sm font-medium text-gray-900 mb-3"
          >
            <span className="flex items-center">
              <Zap className="w-4 h-4 mr-2" />
              Test Suites
            </span>
            {isSectionExpanded('suites') ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {isSectionExpanded('suites') && renderTestSuitesSection()}
        </div>

        {/* Thresholds */}
        <div className="mb-6">
          <button
            onClick={() => toggleSection('thresholds')}
            className="flex items-center justify-between w-full text-left text-sm font-medium text-gray-900 mb-3"
          >
            <span className="flex items-center">
              <Shield className="w-4 h-4 mr-2" />
              Thresholds
            </span>
            {isSectionExpanded('thresholds') ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {isSectionExpanded('thresholds') && renderThresholdsSection()}
        </div>

        {/* Volumes */}
        <div className="mb-6">
          <button
            onClick={() => toggleSection('volumes')}
            className="flex items-center justify-between w-full text-left text-sm font-medium text-gray-900 mb-3"
          >
            <span className="flex items-center">
              <Zap className="w-4 h-4 mr-2" />
              Test Volumes
            </span>
            {isSectionExpanded('volumes') ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {isSectionExpanded('volumes') && renderVolumesSection()}
        </div>

        {/* Resilience */}
        <div className="mb-6">
          <button
            onClick={() => toggleSection('resilience')}
            className="flex items-center justify-between w-full text-left text-sm font-medium text-gray-900 mb-3"
          >
            <span className="flex items-center">
              <Zap className="w-4 h-4 mr-2" />
              Resilience Testing
            </span>
            {isSectionExpanded('resilience') ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {isSectionExpanded('resilience') && renderResilienceSection()}
        </div>

        {/* Compliance */}
        <div className="mb-6">
          <button
            onClick={() => toggleSection('compliance')}
            className="flex items-center justify-between w-full text-left text-sm font-medium text-gray-900 mb-3"
          >
            <span className="flex items-center">
              <Shield className="w-4 h-4 mr-2" />
              Compliance
            </span>
            {isSectionExpanded('compliance') ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {isSectionExpanded('compliance') && renderComplianceSection()}
        </div>

        {/* Bias */}
        <div className="mb-6">
          <button
            onClick={() => toggleSection('bias')}
            className="flex items-center justify-between w-full text-left text-sm font-medium text-gray-900 mb-3"
          >
            <span className="flex items-center">
              <Shield className="w-4 h-4 mr-2" />
              Bias Testing
            </span>
            {isSectionExpanded('bias') ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {isSectionExpanded('bias') && renderBiasSection()}
        </div>

        {/* Test Data */}
        <div className="mb-6">
          <button
            onClick={() => toggleSection('testdata')}
            className="flex items-center justify-between w-full text-left text-sm font-medium text-gray-900 mb-3"
          >
            <span className="flex items-center">
              <Database className="w-4 h-4 mr-2" />
              Test Data
            </span>
            {isSectionExpanded('testdata') ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {isSectionExpanded('testdata') && renderTestDataSection()}
        </div>

        {/* Action Buttons */}
        <div className="space-y-3 pt-6 border-t border-gray-200">
          <button
            onClick={onRun}
            disabled={isRunning || !config.target_mode || config.test_suites.length === 0}
            className="w-full flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Play className="w-4 h-4 mr-2" />
            {isRunning ? 'Running Tests...' : 'Run Tests'}
          </button>

          <button
            disabled={true} // TODO: Implement when tests are running
            className="w-full flex items-center justify-center px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Download className="w-4 h-4 mr-2" />
            Download Reports
          </button>
        </div>
      </div>
    </div>
  );
};

export default InlineDrawer;
