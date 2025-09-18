import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Shield, Lock, AlertTriangle, DollarSign, Clock, FileCheck, 
  Zap, Scale, ChevronDown, ChevronUp, Settings, Play, 
  CheckCircle2, XCircle, AlertCircle, Info, Plus
} from 'lucide-react';
import { GuardrailCategory, GuardrailRule } from '../../types/preflight';
import { usePreflightStore } from '../../stores/preflightStore';
import { useProviderHealth } from '../../hooks/useProviderHealth';
import ProviderAvailabilityChip, { CategoryAvailabilityChip, ProviderUnavailableWarning } from '../guardrails/ProviderAvailabilityChip';

interface CategoryConfig {
  icon: React.ComponentType<any>;
  title: string;
  description: string;
  detailedDescription?: string;
  color: string;
  thresholdType: 'select' | 'number';
  thresholdOptions?: string[];
  thresholdRange?: [number, number];
}

const CATEGORY_CONFIG: Record<GuardrailCategory, CategoryConfig> = {
  pii: {
    icon: Lock,
    title: 'PII Detection',
    description: 'Detect and prevent sensitive data leaks',
    detailedDescription: 'Uses Microsoft Presidio to detect personally identifiable information (PII) such as names, emails, phone numbers, SSNs, and credit card numbers in both input prompts and LLM outputs. Helps ensure GDPR, HIPAA, and other privacy compliance.',
    color: 'from-red-500 to-pink-500',
    thresholdType: 'select',
    thresholdOptions: ['strict', 'medium', 'lenient']
  },
  jailbreak: {
    icon: Shield,
    title: 'Jailbreak Guard',
    description: 'Prevent prompt injection and jailbreak attempts',
    detailedDescription: 'Uses heuristic pattern matching inspired by Rebuff to detect prompt injection attacks like DAN-style jailbreaks, instruction overrides, system prompt extraction, role-playing attacks, and encoding attempts. Analyzes input prompts for malicious patterns.',
    color: 'from-purple-500 to-indigo-500',
    thresholdType: 'number',
    thresholdRange: [0, 1]
  },
  toxicity: {
    icon: AlertTriangle,
    title: 'Toxicity Filter',
    description: 'Filter harmful and toxic content',
    detailedDescription: 'Uses Detoxify ML model to detect toxic, hateful, threatening, obscene, insulting, and identity-attacking content in LLM outputs. Helps maintain safe and respectful AI interactions by filtering harmful language.',
    color: 'from-orange-500 to-red-500',
    thresholdType: 'number',
    thresholdRange: [0, 1]
  },
  rateCost: {
    icon: DollarSign,
    title: 'Rate/Cost Limits',
    description: 'Monitor API usage and costs',
    detailedDescription: 'Tracks API request rates, token consumption, and estimated costs in real-time. Helps prevent unexpected billing spikes and ensures compliance with rate limits. Can enforce hard limits or provide advisory warnings.',
    color: 'from-green-500 to-emerald-500',
    thresholdType: 'number',
    thresholdRange: [1, 1000]
  },
  latency: {
    icon: Clock,
    title: 'Latency Check',
    description: 'Monitor response times',
    detailedDescription: 'Measures end-to-end response times including network latency, processing time, and queue delays. Helps ensure SLA compliance and identify performance bottlenecks. Tracks P95, P99 latencies and timeout rates.',
    color: 'from-blue-500 to-cyan-500',
    thresholdType: 'number',
    thresholdRange: [100, 10000]
  },
  schema: {
    icon: FileCheck,
    title: 'Schema Validation',
    description: 'Validate response structure',
    detailedDescription: 'Validates LLM outputs against predefined JSON schemas to ensure structured responses meet expected format requirements. Essential for function calling, API integrations, and structured data extraction use cases.',
    color: 'from-teal-500 to-green-500',
    thresholdType: 'select',
    thresholdOptions: ['strict', 'medium', 'lenient']
  },
  resilience: {
    icon: Zap,
    title: 'Resilience',
    description: 'Test system robustness',
    detailedDescription: 'Tests system robustness against various failure modes including unicode confusables, gibberish inputs, very long prompts, repeat tokens, and adversarial inputs. Measures entropy, detects confusable characters, and stress-tests edge cases.',
    color: 'from-yellow-500 to-orange-500',
    thresholdType: 'select',
    thresholdOptions: ['light', 'medium', 'heavy']
  },
  bias: {
    icon: Scale,
    title: 'Bias Detection',
    description: 'Detect unfair or biased responses',
    detailedDescription: 'Analyzes LLM outputs for demographic bias, unfair treatment, and discriminatory language across different groups. Uses statistical parity metrics and fairness indicators to ensure equitable AI behavior across all user demographics.',
    color: 'from-pink-500 to-purple-500',
    thresholdType: 'number',
    thresholdRange: [0, 1]
  }
};

const SOURCE_BADGES = {
  safety: { 
    label: 'Safety', 
    color: 'bg-red-500/20 text-red-300 border-red-500/30',
    description: 'Originated from Safety test suite - content safety and policy compliance checks'
  },
  red_team: { 
    label: 'RedTeam', 
    color: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
    description: 'Originated from Red Team test suite - adversarial testing and attack simulation'
  },
  rag_reliability: { 
    label: 'RAG', 
    color: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
    description: 'Originated from RAG Reliability test suite - retrieval and generation quality checks'
  },
  performance: { 
    label: 'Perf', 
    color: 'bg-green-500/20 text-green-300 border-green-500/30',
    description: 'Originated from Performance test suite - latency, throughput and resource monitoring'
  },
  bias: { 
    label: 'Bias', 
    color: 'bg-pink-500/20 text-pink-300 border-pink-500/30',
    description: 'Originated from Bias Detection test suite - fairness and demographic parity checks'
  }
};

interface GuardrailsSheetProps {
  isOpen: boolean;
  onClose: () => void;
  onRunPreflight: () => void;
}

export default function GuardrailsSheet({ isOpen, onClose, onRunPreflight }: GuardrailsSheetProps) {
  const { 
    profile, setProfile, rules, updateRule, toggleRule, 
    estimated, llmType, resetToProfile, addCustomRule 
  } = usePreflightStore();
  
  const { categoryHealth, isLoading: healthLoading, error: healthError } = useProviderHealth();
  
  const [preflightResult, setPreflightResult] = useState<{
    status: 'PASS' | 'FAIL';
    summary: string;
    details: any;
  } | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [showComposer, setShowComposer] = useState(false);
  const [showSourceLabels, setShowSourceLabels] = useState(false);
  const [showAddRuleModal, setShowAddRuleModal] = useState(false);
  const [showInfoModal, setShowInfoModal] = useState(false);
  const [selectedInfo, setSelectedInfo] = useState<{title: string, description: string} | null>(null);
  const [newRule, setNewRule] = useState({
    id: '',
    category: 'pii' as GuardrailCategory,
    threshold: 0.8,
    mode: 'advisory' as 'advisory' | 'hardGate',
    applicability: 'agnostic' as 'agnostic' | 'requiresRag' | 'requiresTools',
    source: 'safety' as 'safety' | 'red_team' | 'rag_reliability' | 'performance' | 'bias'
  });

  const handleProfileChange = (newProfile: 'quick' | 'standard' | 'deep') => {
    setProfile(newProfile);
    resetToProfile(newProfile);
  };

  const handleRunPreflight = async () => {
    setIsRunning(true);
    
    // Simulate preflight run
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    const enabledRules = Object.values(rules).filter(rule => rule.enabled);
    const failCount = Math.floor(Math.random() * 2); // 0-1 failures for demo
    const status = failCount === 0 ? 'PASS' : 'FAIL';
    
    setPreflightResult({
      status,
      summary: `${enabledRules.length} checks completed`,
      details: {
        pii: 0,
        asr: '3%',
        p95: '2.1s',
        costPerTest: '$0.006'
      }
    });
    
    setIsRunning(false);
    onRunPreflight();
  };

  const isRuleApplicable = (rule: GuardrailRule) => {
    if (rule.applicability === 'agnostic') return true;
    if (rule.applicability === 'requiresRag') return llmType === 'rag';
    if (rule.applicability === 'requiresTools') return llmType === 'tools' || llmType === 'agent';
    return true;
  };

  const renderThresholdInput = (rule: GuardrailRule) => {
    const config = CATEGORY_CONFIG[rule.category];
    
    if (config.thresholdType === 'select') {
      return (
        <select
          value={rule.threshold as string || config.thresholdOptions?.[1]}
          onChange={(e) => updateRule(rule.id, { threshold: e.target.value })}
          className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-sm text-white focus:border-purple-500 focus:outline-none"
        >
          {config.thresholdOptions?.map(option => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      );
    }
    
    return (
      <input
        type="number"
        value={rule.threshold as number || 0}
        onChange={(e) => updateRule(rule.id, { threshold: parseFloat(e.target.value) })}
        min={config.thresholdRange?.[0]}
        max={config.thresholdRange?.[1]}
        step={config.thresholdRange?.[1] === 1 ? 0.01 : 1}
        className="w-20 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-sm text-white focus:border-purple-500 focus:outline-none"
      />
    );
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
          />
          
          {/* Sheet */}
          <motion.div
            initial={{ opacity: 0, y: '100%' }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            className="fixed inset-x-0 bottom-0 z-50 bg-[#0B0D12] border-t border-gray-700 rounded-t-2xl max-h-[90vh] overflow-hidden"
            role="dialog"
            aria-modal="true"
            aria-labelledby="guardrails-sheet-title"
            aria-describedby="guardrails-sheet-description"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-700">
              <div className="flex items-center gap-4">
                <h2 id="guardrails-sheet-title" className="text-xl font-bold text-white">Recommended Guardrails</h2>
                <p id="guardrails-sheet-description" className="sr-only">Configure guardrails for your LLM testing including PII detection, jailbreak protection, and performance monitoring</p>
                
                {/* Source Labels Toggle */}
                <button
                  onClick={() => setShowSourceLabels(!showSourceLabels)}
                  className="flex items-center gap-2 px-3 py-1 text-xs text-gray-400 hover:text-white border border-gray-600 hover:border-gray-500 rounded-lg transition-colors"
                  title={showSourceLabels ? "Hide source suite labels" : "Show source suite labels"}
                >
                  <span>{showSourceLabels ? 'Hide' : 'Show'} Sources</span>
                  <span className="text-xs">({showSourceLabels ? 'ON' : 'OFF'})</span>
                </button>
                
                {/* Profile chips */}
                <div className="flex bg-gray-800 rounded-lg p-1" role="radiogroup" aria-label="Guardrails profile selection">
                  {(['quick', 'standard', 'deep'] as const).map((p) => (
                    <button
                      key={p}
                      onClick={() => handleProfileChange(p)}
                      role="radio"
                      aria-checked={profile === p}
                      className={`
                        px-3 py-1 text-sm rounded-md transition-all duration-200 capitalize focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-gray-800
                        ${profile === p 
                          ? 'bg-purple-600 text-white' 
                          : 'text-gray-400 hover:text-white'
                        }
                      `}
                    >
                      {p}
                    </button>
                  ))}
                </div>
                
                <button
                  onClick={() => setShowComposer(!showComposer)}
                  className="flex items-center gap-1 px-3 py-1 text-sm text-purple-300 hover:text-purple-200 border border-purple-500/30 rounded-md transition-colors duration-200"
                >
                  <Settings className="w-4 h-4" />
                  Customize
                </button>
              </div>
              
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-white transition-colors duration-200"
              >
                <ChevronDown className="w-6 h-6" />
              </button>
            </div>

            {/* Content */}
            <div className="flex h-full max-h-[calc(90vh-80px)]">
              {/* Left column - Categories */}
              <div className="flex-1 p-6 overflow-y-auto">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(rules).map(([ruleId, rule]) => {
                    const config = CATEGORY_CONFIG[rule.category];
                    const Icon = config.icon;
                    const isApplicable = isRuleApplicable(rule);
                    const sourceBadge = SOURCE_BADGES[rule.source || 'safety'];
                    
                    return (
                      <div
                        key={ruleId}
                        className={`
                          relative p-4 border rounded-xl transition-all duration-200
                          ${isApplicable 
                            ? rule.enabled 
                              ? 'border-purple-500/50 bg-purple-500/5' 
                              : 'border-gray-700 bg-gray-800/30 hover:border-gray-600'
                            : 'border-gray-800 bg-gray-900/50 opacity-50'
                          }
                        `}
                      >
                        {/* Applicability tooltip */}
                        {!isApplicable && (
                          <div className="absolute top-2 right-2" title={`Requires ${rule.applicability}`}>
                            <Info className="w-4 h-4 text-gray-500" />
                          </div>
                        )}
                        
                        {/* Header */}
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <div className={`
                              p-2 rounded-lg bg-gradient-to-br ${config.color} bg-opacity-20
                            `}>
                              <Icon className="w-5 h-5 text-white" />
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <h3 className="font-medium text-white">{config.title}</h3>
                                {config.detailedDescription && (
                                  <button 
                                    onClick={() => {
                                      setSelectedInfo({
                                        title: config.title,
                                        description: config.detailedDescription || ''
                                      });
                                      setShowInfoModal(true);
                                    }}
                                    className="cursor-pointer hover:bg-gray-700/50 rounded p-1 transition-colors"
                                    title="Click for detailed information"
                                  >
                                    <Info className="w-4 h-4 text-gray-400 hover:text-blue-400 transition-colors" />
                                  </button>
                                )}
                              </div>
                              <div className="flex items-center gap-2 mt-1">
                                {showSourceLabels && (
                                  <span 
                                    className={`px-2 py-0.5 text-xs border rounded ${sourceBadge.color}`}
                                    title={sourceBadge.description}
                                  >
                                    {sourceBadge.label}
                                  </span>
                                )}
                                {rule.applicability !== 'agnostic' && (
                                  <span className="px-2 py-0.5 text-xs bg-gray-700 text-gray-300 rounded">
                                    {rule.applicability === 'requiresRag' ? 'RAG' : 'Tools'}
                                  </span>
                                )}
                                
                                {/* Provider availability */}
                                {categoryHealth[rule.category] && (
                                  <CategoryAvailabilityChip
                                    category={rule.category}
                                    available={categoryHealth[rule.category].available}
                                    totalProviders={categoryHealth[rule.category].total_providers}
                                    availableProviders={categoryHealth[rule.category].available_providers}
                                  />
                                )}
                              </div>
                            </div>
                          </div>
                          
                          <label className="relative inline-flex items-center cursor-pointer">
                            <input
                              type="checkbox"
                              checked={rule.enabled}
                              onChange={() => toggleRule(ruleId)}
                              disabled={!isApplicable}
                              className="sr-only peer"
                            />
                            <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
                          </label>
                        </div>
                        
                        {/* Description */}
                        <p className="text-sm text-gray-400 mb-3">{config.description}</p>
                        
                        {/* Controls */}
                        {rule.enabled && (
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-400">Threshold:</span>
                              {renderThresholdInput(rule)}
                            </div>
                            
                            <select
                              value={rule.mode}
                              onChange={(e) => updateRule(ruleId, { mode: e.target.value as 'advisory' | 'hardGate' })}
                              className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-xs text-white focus:border-purple-500 focus:outline-none"
                            >
                              <option value="advisory">Advisory</option>
                              <option value="hardGate">Hard Gate</option>
                            </select>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Right column - Composer & Estimator */}
              <div className="w-80 border-l border-gray-700 p-6 space-y-6">
                {/* Estimator */}
                <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
                  <h3 className="font-medium text-white mb-3">Estimate</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Tests:</span>
                      <span className="text-white">{estimated.tests}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">P95 Latency:</span>
                      <span className="text-white">{(estimated.p95ms / 1000).toFixed(1)}s</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Cost/Test:</span>
                      <span className="text-white">${(estimated.costUsd / estimated.tests).toFixed(3)}</span>
                    </div>
                  </div>
                </div>

                {/* Run Preflight */}
                <button
                  onClick={handleRunPreflight}
                  disabled={isRunning}
                  className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:from-gray-600 disabled:to-gray-600 text-white font-medium py-3 rounded-xl transition-all duration-200 min-h-[44px]"
                >
                  {isRunning ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Running...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      Run Preflight
                    </>
                  )}
                </button>

                {/* Preflight Result */}
                {preflightResult && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`
                      border rounded-xl p-4
                      ${preflightResult.status === 'PASS' 
                        ? 'border-green-500/30 bg-green-500/5' 
                        : 'border-red-500/30 bg-red-500/5'
                      }
                    `}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      {preflightResult.status === 'PASS' ? (
                        <CheckCircle2 className="w-5 h-5 text-green-400" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-400" />
                      )}
                      <span className={`font-medium ${
                        preflightResult.status === 'PASS' ? 'text-green-300' : 'text-red-300'
                      }`}>
                        Preflight Gate: {preflightResult.status}
                      </span>
                    </div>
                    
                    <div className="text-sm space-y-1">
                      <div className="text-gray-300">{preflightResult.summary}</div>
                      <div className="text-gray-400">
                        PII({preflightResult.details.pii}) • ASR({preflightResult.details.asr}) • 
                        p95={preflightResult.details.p95} • ${preflightResult.details.costPerTest}/test
                      </div>
                      {preflightResult.details.pi_quickset && (
                        <div className="text-gray-400 mt-1">
                          <span className="inline-flex items-center gap-1">
                            🎯 PI Quickset: {(preflightResult.details.pi_quickset.asr * 100).toFixed(1)}% ASR 
                            ({preflightResult.details.pi_quickset.success}/{preflightResult.details.pi_quickset.total})
                            {preflightResult.details.pi_quickset.families_used?.length > 0 && (
                              <span className="text-xs">
                                • {preflightResult.details.pi_quickset.families_used.join(', ')}
                              </span>
                            )}
                          </span>
                        </div>
                      )}
                      
                      {/* Provider availability summary */}
                      {!healthLoading && Object.keys(categoryHealth).length > 0 && (
                        <div className="text-gray-400 mt-2">
                          <div className="text-xs mb-1">Provider Status:</div>
                          <div className="flex flex-wrap gap-1">
                            {Object.values(categoryHealth).map(category => (
                              <CategoryAvailabilityChip
                                key={category.category}
                                category={category.category}
                                available={category.available}
                                totalProviders={category.total_providers}
                                availableProviders={category.available_providers}
                              />
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                    
                    <button className="text-xs text-purple-300 hover:text-purple-200 mt-2">
                      View details
                    </button>
                  </motion.div>
                )}

                {/* Rule Composer */}
                {showComposer && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className="bg-gray-800/50 border border-gray-700 rounded-xl p-4"
                  >
                    <h3 className="font-medium text-white mb-3">Compose Rules</h3>
                    <div className="space-y-3">
                      <div className="flex gap-2">
                        <button className="px-3 py-1 bg-purple-600 text-white text-sm rounded">AND</button>
                        <button className="px-3 py-1 border border-gray-600 text-gray-300 text-sm rounded">OR</button>
                      </div>
                      <button 
                        onClick={() => setShowAddRuleModal(true)}
                        className="flex items-center gap-2 w-full px-3 py-2 border border-gray-600 text-gray-300 text-sm rounded hover:border-gray-500 transition-colors duration-200"
                      >
                        <Plus className="w-4 h-4" />
                        Add Rule
                      </button>
                    </div>
                  </motion.div>
                )}
              </div>
            </div>
          </motion.div>
        </>
      )}
      
      {/* Add Rule Modal */}
      {showAddRuleModal && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setShowAddRuleModal(false)}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-md w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-white mb-4">Add Custom Guardrail Rule</h3>
            
            <div className="space-y-4">
              {/* Rule ID */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Rule ID</label>
                <input
                  type="text"
                  value={newRule.id}
                  onChange={(e) => setNewRule(prev => ({ ...prev, id: e.target.value }))}
                  placeholder="custom-rule-1"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none"
                />
              </div>
              
              {/* Category */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Category</label>
                <select
                  value={newRule.category}
                  onChange={(e) => setNewRule(prev => ({ ...prev, category: e.target.value as GuardrailCategory }))}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-purple-500 focus:outline-none"
                >
                  <option value="pii">PII Detection</option>
                  <option value="jailbreak">Jailbreak Guard</option>
                  <option value="toxicity">Toxicity Filter</option>
                  <option value="rateCost">Rate/Cost Limits</option>
                  <option value="latency">Latency Check</option>
                  <option value="schema">Schema Validation</option>
                  <option value="resilience">Resilience</option>
                  <option value="bias">Bias Detection</option>
                </select>
              </div>
              
              {/* Threshold */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Threshold</label>
                <input
                  type="number"
                  value={newRule.threshold}
                  onChange={(e) => setNewRule(prev => ({ ...prev, threshold: parseFloat(e.target.value) || 0 }))}
                  min="0"
                  max="1"
                  step="0.1"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-purple-500 focus:outline-none"
                />
              </div>
              
              {/* Mode */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Mode</label>
                <select
                  value={newRule.mode}
                  onChange={(e) => setNewRule(prev => ({ ...prev, mode: e.target.value as 'advisory' | 'hardGate' }))}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-purple-500 focus:outline-none"
                >
                  <option value="advisory">Advisory</option>
                  <option value="hardGate">Hard Gate</option>
                </select>
              </div>
              
              {/* Source */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Source Suite</label>
                <select
                  value={newRule.source}
                  onChange={(e) => setNewRule(prev => ({ ...prev, source: e.target.value as any }))}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-purple-500 focus:outline-none"
                >
                  <option value="safety">Safety</option>
                  <option value="red_team">Red Team</option>
                  <option value="rag_reliability">RAG Reliability</option>
                  <option value="performance">Performance</option>
                  <option value="bias">Bias</option>
                </select>
              </div>
            </div>
            
            {/* Actions */}
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowAddRuleModal(false)}
                className="flex-1 px-4 py-2 border border-gray-600 text-gray-300 rounded-lg hover:border-gray-500 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (newRule.id.trim()) {
                    addCustomRule({
                      ...newRule,
                      enabled: true
                    });
                    setNewRule({
                      id: '',
                      category: 'pii',
                      threshold: 0.8,
                      mode: 'advisory',
                      applicability: 'agnostic',
                      source: 'safety'
                    });
                    setShowAddRuleModal(false);
                  }
                }}
                disabled={!newRule.id.trim()}
                className="flex-1 px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
              >
                Add Rule
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
      
      {/* Info Modal */}
      {showInfoModal && selectedInfo && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setShowInfoModal(false)}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-lg w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 mb-4">
              <Info className="w-6 h-6 text-blue-400" />
              <h3 className="text-lg font-semibold text-white">{selectedInfo.title}</h3>
            </div>
            
            <div className="text-gray-300 text-sm leading-relaxed mb-6">
              {selectedInfo.description}
            </div>
            
            <div className="flex justify-end">
              <button
                onClick={() => setShowInfoModal(false)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
              >
                Got it
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
