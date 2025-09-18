/**
 * Specialist Suites component for the Preflight UI
 * Maintains parity with Classic UI test suite selection
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronRight, Lock, CheckSquare, Square, AlertTriangle, Info, ExternalLink } from 'lucide-react';
import clsx from 'clsx';
import { 
  SUITE_REGISTRY, 
  getSuiteById, 
  getDefaultSelections, 
  calculateEstimates,
  type SuiteDefinition,
  type TestDefinition
} from '../../lib/suiteRegistry';
import type { DataRequirements } from '../../types/metrics';
import { usePreflightStore } from '../../stores/preflightStore';
import InlineDataIntake, { type TestDataArtifact, type ValidationResult } from './InlineDataIntake';
import ReusedFromPreflightChip from './ReusedFromPreflightChip';
import PIQuicksetChip, { PIQuicksetUnavailableChip, createPIQuicksetData } from './PIQuicksetChip';
import type { RedTeamCategory, RedTeamSubtests as RedTeamSubtestsType, SafetyCategory, SafetySubtests as SafetySubtestsType } from '../../types';
import RedTeamSubtests from '../RedTeamSubtests';
import SafetySubtests from '../SafetySubtests';

interface SpecialistSuitesProps {
  llmType: string;
  hasGroundTruth: boolean;
  dataStatus: Partial<DataRequirements>;
  onSelectionChange: (selectedTests: Record<string, string[]>) => void;
  onShowDataRequirements: () => void;
  onEphemeralIdsChange?: (ephemeralIds: Record<string, Record<string, string>>) => void;
}

interface SuiteState extends SuiteDefinition {
  expanded: boolean;
  locked: boolean;
  missingRequirements: string[];
}

export default function SpecialistSuites({
  llmType,
  hasGroundTruth,
  dataStatus,
  onSelectionChange,
  onShowDataRequirements,
  onEphemeralIdsChange
}: SpecialistSuitesProps) {
  const { rules } = usePreflightStore();
  
  // Initialize suite states
  const [suiteStates, setSuiteStates] = useState<Record<string, SuiteState>>({});
  const [selectedTests, setSelectedTests] = useState<Record<string, string[]>>({});
  const [validatedArtifacts, setValidatedArtifacts] = useState<Record<string, Record<string, ValidationResult>>>({});
  
  // Red Team subtests state - initialize with all subtests selected (backward compatible)
  const [redTeamSubtests, setRedTeamSubtests] = useState<RedTeamSubtestsType>({
    prompt_injection: ["direct", "indirect", "passage_embedded", "metadata_embedded"],
    jailbreak: ["role_play", "system_override"],
    data_extraction: ["system_prompt", "api_key", "base64"],
    context_poisoning: ["ignore_citations", "contradict_retrieval", "spoof_citations"],
    social_engineering: ["authority", "urgency", "scarcity", "reciprocity", "sympathy"]
  });

  // Safety subtests state - initialize with all subtests selected (backward compatible)
  const [safetySubtests, setSafetySubtests] = useState<SafetySubtestsType>({
    toxicity: ["explicit", "implicit", "contextual"],
    hate: ["targeted", "general"],
    violence: ["graphic", "threat"],
    adult: ["explicit"],
    self_harm: ["direct", "indirect"],
    misinformation: ["false_claims", "misleading"]
  });
  
  // Initialize suites based on LLM type
  useEffect(() => {
    const availableSuites = Object.values(SUITE_REGISTRY).filter(suite => {
      return !suite.supportedModes || suite.supportedModes.includes(llmType as any);
    });
    
    const newSuiteStates: Record<string, SuiteState> = {};
    
    availableSuites.forEach(suite => {
      const missingRequirements: string[] = [];
      let locked = false;
      
      // Check data requirements - but don't lock suites unless absolutely necessary
      // Most suites can run with built-in test data, only show missing requirements as info
      if (suite.dataRequirements) {
        Object.entries(suite.dataRequirements).forEach(([req, required]) => {
          if (required && !dataStatus[req as keyof DataRequirements]) {
            missingRequirements.push(req);
          }
        });
      }
      
      // Don't lock any suites - let users run with built-in data and show upload options inline
      locked = false;
      
      newSuiteStates[suite.id] = {
        ...suite,
        expanded: suite.id === 'rag_reliability_robustness' && llmType === 'rag', // Expand RAG by default for RAG type
        locked,
        missingRequirements
      };
    });
    
    setSuiteStates(newSuiteStates);
    
    // Set default selections
    const defaultSelections = getDefaultSelections(llmType, hasGroundTruth);
    setSelectedTests(defaultSelections);
    onSelectionChange(defaultSelections);
  }, [llmType, hasGroundTruth, dataStatus, onSelectionChange]);
  
  // Handle suite expansion toggle
  const toggleSuiteExpansion = (suiteId: string) => {
    setSuiteStates(prev => ({
      ...prev,
      [suiteId]: {
        ...prev[suiteId],
        expanded: !prev[suiteId]?.expanded
      }
    }));
  };
  
  // Handle test selection toggle
  // Suite Configuration removed - test selection is sufficient

  const toggleTest = (suiteId: string, testId: string) => {
    const suite = suiteStates[suiteId];
    if (suite?.locked) return;
    
    setSelectedTests(prev => {
      const suiteTests = prev[suiteId] || [];
      const newSuiteTests = suiteTests.includes(testId)
        ? suiteTests.filter(id => id !== testId)
        : [...suiteTests, testId];
      
      const newSelection = {
        ...prev,
        [suiteId]: newSuiteTests
      };
      
      // Suite Configuration removed - no sync needed
      
      onSelectionChange(newSelection);
      return newSelection;
    });
  };
  
  // Handle suite enable/disable
  const toggleSuite = (suiteId: string, enabled: boolean) => {
    if (suiteStates[suiteId]?.locked && enabled) return;
    
    setSelectedTests(prev => {
      const newSelection = { ...prev };
      
      if (enabled) {
        // Enable default tests for this suite
        const suite = getSuiteById(suiteId);
        const defaultTests = suite?.tests
          .filter(test => test.enabled || test.required)
          .map(test => test.id) || [];
        newSelection[suiteId] = defaultTests;
      } else {
        // Disable all tests for this suite
        delete newSelection[suiteId];
      }
      
      onSelectionChange(newSelection);
      return newSelection;
    });
  };
  
  // Handle Red Team subtests changes
  const handleRedTeamSubtestChange = (category: RedTeamCategory, subtests: string[]) => {
    const newRedTeamSubtests = {
      ...redTeamSubtests,
      [category]: subtests
    };
    setRedTeamSubtests(newRedTeamSubtests);
  };

  // Handle Safety subtests changes
  const handleSafetySubtestChange = (category: SafetyCategory, subtests: string[]) => {
    const newSafetySubtests = {
      ...safetySubtests,
      [category]: subtests
    };
    setSafetySubtests(newSafetySubtests);
  };
  
  // Get required artifacts for each suite
  const getSuiteArtifacts = (suiteId: string): TestDataArtifact[] => {
    switch (suiteId) {
      case 'rag_reliability_robustness':
        return [
          {
            type: 'passages',
            name: 'Passages',
            description: 'Document passages for retrieval testing',
            templateUrl: '/testdata/template?type=passages',
            required: true
          },
          {
            type: 'qaset',
            name: 'QA Set',
            description: 'Question-answer pairs with ground truth',
            templateUrl: '/testdata/template?type=qaset',
            required: hasGroundTruth
          }
        ];
      case 'red_team':
        return [
          {
            type: 'attacks',
            name: 'Attack Prompts',
            description: 'Adversarial prompts for security testing',
            templateUrl: '/testdata/template?type=attacks',
            required: true
          }
        ];
      case 'safety':
        return [
          {
            type: 'safety',
            name: 'Safety Tests',
            description: 'Safety evaluation prompts and expected outcomes',
            templateUrl: '/testdata/template?type=safety',
            required: true
          }
        ];
      case 'bias':
        return [
          {
            type: 'bias',
            name: 'Bias Tests',
            description: 'Bias evaluation scenarios across demographic groups',
            templateUrl: '/testdata/template?type=bias',
            required: true
          }
        ];
      case 'performance':
        return [
          {
            type: 'scenarios',
            name: 'Performance Scenarios',
            description: 'Load testing scenarios and configurations',
            templateUrl: '/testdata/template?type=scenarios',
            required: false
          }
        ];
      case 'schema':
        return [
          {
            type: 'schema',
            name: 'Schema Definitions',
            description: 'JSON schema definitions for validation',
            templateUrl: '/testdata/template?type=schema',
            required: false
          }
        ];
      default:
        return [];
    }
  };

  // Handle artifact validation completion
  const handleValidationComplete = (suiteId: string, artifactType: string, result: ValidationResult) => {
    setValidatedArtifacts(prev => ({
      ...prev,
      [suiteId]: {
        ...prev[suiteId],
        [artifactType]: result
      }
    }));
    
    // Update ephemeral IDs if validation successful
    if (result.success && result.testdata_id && onEphemeralIdsChange) {
      const newEphemeralIds: Record<string, Record<string, string>> = {};
      
      // Collect all current ephemeral IDs
      Object.entries(validatedArtifacts).forEach(([sId, artifacts]) => {
        Object.entries(artifacts).forEach(([aType, aResult]) => {
          if (aResult.success && aResult.testdata_id) {
            if (!newEphemeralIds[sId]) newEphemeralIds[sId] = {};
            newEphemeralIds[sId][aType] = aResult.testdata_id;
          }
        });
      });
      
      // Add the new one
      if (!newEphemeralIds[suiteId]) newEphemeralIds[suiteId] = {};
      newEphemeralIds[suiteId][artifactType] = result.testdata_id;
      
      onEphemeralIdsChange(newEphemeralIds);
    }
    
    // Update suite lock status
    updateSuiteLockStatus(suiteId);
  };

  // Handle artifact clear
  const handleArtifactClear = (suiteId: string, artifactType: string) => {
    setValidatedArtifacts(prev => {
      const suiteArtifacts = { ...prev[suiteId] };
      delete suiteArtifacts[artifactType];
      return {
        ...prev,
        [suiteId]: suiteArtifacts
      };
    });
    
    // Update ephemeral IDs
    if (onEphemeralIdsChange) {
      const newEphemeralIds: Record<string, Record<string, string>> = {};
      
      // Collect all remaining ephemeral IDs (excluding the cleared one)
      Object.entries(validatedArtifacts).forEach(([sId, artifacts]) => {
        Object.entries(artifacts).forEach(([aType, aResult]) => {
          if (!(sId === suiteId && aType === artifactType) && aResult.success && aResult.testdata_id) {
            if (!newEphemeralIds[sId]) newEphemeralIds[sId] = {};
            newEphemeralIds[sId][aType] = aResult.testdata_id;
          }
        });
      });
      
      onEphemeralIdsChange(newEphemeralIds);
    }
    
    // Update suite lock status
    updateSuiteLockStatus(suiteId);
  };

  // Update suite lock status based on artifact validation
  const updateSuiteLockStatus = (suiteId: string) => {
    const artifacts = getSuiteArtifacts(suiteId);
    const requiredArtifacts = artifacts.filter(a => a.required);
    const validatedSuiteArtifacts = validatedArtifacts[suiteId] || {};
    
    const missingRequirements: string[] = [];
    let locked = false;
    
    requiredArtifacts.forEach(artifact => {
      const validation = validatedSuiteArtifacts[artifact.type];
      if (!validation || !validation.success) {
        missingRequirements.push(artifact.type);
        locked = true;
      }
    });
    
    setSuiteStates(prev => ({
      ...prev,
      [suiteId]: {
        ...prev[suiteId],
        locked,
        missingRequirements
      }
    }));
  };

  // Check if a test is gated by guardrails
  const isTestGatedByGuardrails = (suiteId: string, testId: string): boolean => {
    const suite = getSuiteById(suiteId);
    const test = suite?.tests.find(t => t.id === testId);
    
    if (!test?.tags) return false;
    
    // Check if any guardrail rule covers this test's categories
    return Object.values(rules).some(rule => {
      if (!rule.enabled) return false;
      
      // Map test tags to guardrail categories
      const categoryMap: Record<string, string> = {
        'security': 'jailbreak',
        'safety': 'toxicity',
        'critical': 'pii'
      };
      
      return test.tags?.some(tag => categoryMap[tag] === rule.category);
    });
  };
  
  // Calculate estimates
  const estimates = calculateEstimates(selectedTests);
  
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Specialist Suites
          </h3>
          <p className="text-sm text-slate-600 dark:text-slate-400">
            Advanced testing capabilities with full Classic UI parity
          </p>
        </div>
        
        {/* Quick stats */}
        <div className="flex items-center gap-4 text-sm">
          <span className="text-slate-600 dark:text-slate-400">
            {estimates.totalTests} tests selected
          </span>
          <span className="text-slate-600 dark:text-slate-400">
            ~${estimates.totalCost.toFixed(2)}
          </span>
          <span className="text-slate-600 dark:text-slate-400">
            ~{Math.ceil(estimates.totalDurationMinutes)}min
          </span>
        </div>
      </div>
      
      {/* Header */}
      <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">2</span>
          </div>
          <div>
            <h3 className="font-semibold text-slate-900 dark:text-slate-100">Specialist Test Suites</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Comprehensive testing after Guardrails preflight passes
            </p>
          </div>
        </div>
        <div className="text-xs text-slate-500 dark:text-slate-400 bg-white dark:bg-slate-800 p-3 rounded-lg">
          <strong>Note:</strong> These are detailed test suites that run comprehensive analysis. 
          Each suite has configurable parameters and can take 5-30 minutes to complete.
          <br />
          <strong>Suite Configuration:</strong> Click to customize test parameters, thresholds, and attack vectors.
        </div>
      </div>
      
      {/* Suite cards */}
      <div className="space-y-3">
        {Object.values(suiteStates).map(suite => {
          const isEnabled = selectedTests[suite.id]?.length > 0;
          const selectedCount = selectedTests[suite.id]?.length || 0;
          const totalTests = suite.tests.length;
          
          return (
            <motion.div
              key={suite.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={clsx(
                "border rounded-lg overflow-hidden transition-all duration-200",
                suite.locked 
                  ? "border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50"
                  : isEnabled
                    ? "border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-900/20"
                    : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800"
              )}
            >
              {/* Suite header */}
              <div 
                className={clsx(
                  "p-4 cursor-pointer transition-colors",
                  suite.locked ? "cursor-not-allowed" : "hover:bg-slate-50 dark:hover:bg-slate-700/50"
                )}
                onClick={() => !suite.locked && toggleSuiteExpansion(suite.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {/* Suite icon */}
                    <div className={clsx(
                      "p-2 rounded-lg",
                      suite.locked 
                        ? "bg-slate-200 dark:bg-slate-700"
                        : `bg-${suite.color}-100 dark:bg-${suite.color}-900/30`
                    )}>
                      <suite.icon 
                        size={20} 
                        className={clsx(
                          suite.locked 
                            ? "text-slate-400 dark:text-slate-500"
                            : `text-${suite.color}-600 dark:text-${suite.color}-400`
                        )} 
                      />
                    </div>
                    
                    {/* Suite info */}
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className={clsx(
                          "font-medium",
                          suite.locked 
                            ? "text-slate-400 dark:text-slate-500"
                            : "text-slate-900 dark:text-slate-100"
                        )}>
                          {suite.name}
                        </h4>
                        
                        {/* Lock indicator */}
                        {suite.locked && (
                          <Lock size={16} className="text-slate-400 dark:text-slate-500" />
                        )}
                        
                        {/* Guardrails gate indicator */}
                        {isEnabled && Object.values(selectedTests[suite.id] || []).some(testId => 
                          isTestGatedByGuardrails(suite.id, testId)
                        ) && (
                          <div className="flex items-center gap-1 px-2 py-1 bg-purple-100 dark:bg-purple-900/30 rounded text-xs text-purple-700 dark:text-purple-300">
                            <AlertTriangle size={12} />
                            Gated by Guardrails
                          </div>
                        )}
                      </div>
                      
                      <p className={clsx(
                        "text-sm",
                        suite.locked 
                          ? "text-slate-400 dark:text-slate-500"
                          : "text-slate-600 dark:text-slate-400"
                      )}>
                        {suite.description}
                      </p>
                      
                      {/* Requirements */}
                      {suite.locked && suite.missingRequirements.length > 0 && (
                        <div className="flex items-center gap-2 mt-2">
                          <span className="text-xs text-amber-600 dark:text-amber-400">
                            Missing:
                          </span>
                          {suite.missingRequirements.map(req => (
                            <span 
                              key={req}
                              className="px-2 py-1 bg-amber-100 dark:bg-amber-900/30 text-xs text-amber-700 dark:text-amber-300 rounded cursor-pointer hover:bg-amber-200 dark:hover:bg-amber-900/50"
                              onClick={(e) => {
                                e.stopPropagation();
                                onShowDataRequirements();
                              }}
                            >
                              {req}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-3">
                    {/* Selection count */}
                    {isEnabled && (
                      <span className="text-sm text-slate-600 dark:text-slate-400">
                        {selectedCount}/{totalTests}
                      </span>
                    )}
                    
                    {/* Enable/disable toggle */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleSuite(suite.id, !isEnabled);
                      }}
                      disabled={suite.locked}
                      className={clsx(
                        "p-1 rounded transition-colors",
                        suite.locked 
                          ? "cursor-not-allowed"
                          : "hover:bg-slate-200 dark:hover:bg-slate-600"
                      )}
                    >
                      {isEnabled ? (
                        <CheckSquare size={20} className="text-blue-600 dark:text-blue-400" />
                      ) : (
                        <Square size={20} className="text-slate-400 dark:text-slate-500" />
                      )}
                    </button>
                    
                    {/* Expand/collapse */}
                    {!suite.locked && (
                      <button className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors">
                        {suite.expanded ? (
                          <ChevronDown size={20} className="text-slate-600 dark:text-slate-400" />
                        ) : (
                          <ChevronRight size={20} className="text-slate-600 dark:text-slate-400" />
                        )}
                      </button>
                    )}
                  </div>
                </div>
              </div>
              
              {/* Inline Data Intake */}
              {suite.expanded && getSuiteArtifacts(suite.id).length > 0 && (
                <div className="border-t border-slate-200 dark:border-slate-700 p-4">
                  <InlineDataIntake
                    suiteId={suite.id}
                    artifacts={getSuiteArtifacts(suite.id)}
                    onValidationComplete={(artifactType, result) => handleValidationComplete(suite.id, artifactType, result)}
                    onClear={(artifactType) => handleArtifactClear(suite.id, artifactType)}
                    validatedArtifacts={validatedArtifacts[suite.id] || {}}
                  />
                </div>
              )}
              
              {/* Suite Configuration - REMOVED: Test selection is sufficient */}

              {/* Suite tests */}
              <AnimatePresence>
                {suite.expanded && !suite.locked && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="border-t border-slate-200 dark:border-slate-700"
                  >
                    <div className="p-4 space-y-3">
                      {/* Test Selection Controls */}
                      <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-700">
                        <div>
                          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                            Individual Tests ({selectedCount}/{totalTests})
                          </span>
                          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                            Select which specific tests to run. Configuration above controls how each test executes.
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => {
                              // Select all tests in this suite
                              const allTestIds = suite.tests.map(test => test.id);
                              setSelectedTests(prev => ({
                                ...prev,
                                [suite.id]: allTestIds
                              }));
                              onSelectionChange({
                                ...selectedTests,
                                [suite.id]: allTestIds
                              });
                            }}
                            className="px-2 py-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200 transition-colors"
                          >
                            Select All
                          </button>
                          <span className="text-slate-300 dark:text-slate-600">|</span>
                          <button
                            onClick={() => {
                              // Deselect all tests in this suite
                              setSelectedTests(prev => ({
                                ...prev,
                                [suite.id]: []
                              }));
                              onSelectionChange({
                                ...selectedTests,
                                [suite.id]: []
                              });
                            }}
                            className="px-2 py-1 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
                          >
                            Deselect All
                          </button>
                        </div>
                      </div>
                      
                      {suite.tests.map(test => {
                        const isSelected = selectedTests[suite.id]?.includes(test.id) || false;
                        const isGated = isTestGatedByGuardrails(suite.id, test.id);
                        
                        return (
                          <div
                            key={test.id}
                            className={clsx(
                              "flex items-center justify-between p-3 rounded-lg border transition-all duration-150",
                              isSelected 
                                ? "border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-900/20"
                                : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600"
                            )}
                          >
                            <div className="flex items-center gap-3">
                              {/* Test checkbox */}
                              <button
                                onClick={() => toggleTest(suite.id, test.id)}
                                className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
                              >
                                {isSelected ? (
                                  <CheckSquare size={16} className="text-blue-600 dark:text-blue-400" />
                                ) : (
                                  <Square size={16} className="text-slate-400 dark:text-slate-500" />
                                )}
                              </button>
                              
                              {/* Test info */}
                              <div>
                                <div className="flex items-center gap-2">
                                  <h5 className="font-medium text-slate-900 dark:text-slate-100">
                                    {test.name}
                                  </h5>
                                  
                                  {test.required && (
                                    <span className="px-2 py-1 bg-orange-100 dark:bg-orange-900/30 text-xs text-orange-700 dark:text-orange-300 rounded">
                                      Required
                                    </span>
                                  )}
                                  
                                  {isGated && (
                                    <span className="px-2 py-1 bg-purple-100 dark:bg-purple-900/30 text-xs text-purple-700 dark:text-purple-300 rounded">
                                      Guardrails
                                    </span>
                                  )}
                                  
                                  {/* Show reused from preflight chip if applicable */}
                                  <ReusedFromPreflightChip 
                                    reusedCount={(test as any).reusedSignals || 0}
                                    reusedCategories={(test as any).reusedCategories || []}
                                    size="sm"
                                  />
                                  
                                  {/* Show PI quickset chip if applicable */}
                                  {(test as any).piQuicksetData && (
                                    <PIQuicksetChip 
                                      data={(test as any).piQuicksetData}
                                      className="ml-1"
                                    />
                                  )}
                                  
                                  {/* Show PI quickset unavailable if provider failed */}
                                  {(test as any).piQuicksetUnavailable && (
                                    <PIQuicksetUnavailableChip className="ml-1" />
                                  )}
                                </div>
                                
                                <p className="text-sm text-slate-600 dark:text-slate-400">
                                  {test.description}
                                </p>
                                
                                {/* Test metadata */}
                                <div className="flex items-center gap-4 mt-1 text-xs text-slate-500 dark:text-slate-400">
                                  <span>{test.estimatedDuration}</span>
                                  <span>${(test.estimatedCost || 0.01).toFixed(3)}</span>
                                  {test.category && (
                                    <span className="capitalize">{test.category}</span>
                                  )}
                                </div>
                                
                                {/* Red Team Subtests */}
                                {suite.id === 'red_team' && isSelected && (
                                  <RedTeamSubtests
                                    category={test.id as RedTeamCategory}
                                    selectedSubtests={redTeamSubtests[test.id as RedTeamCategory] || []}
                                    onSubtestsChange={handleRedTeamSubtestChange}
                                    className="mt-2"
                                  />
                                )}
                                
                                {/* Safety Subtests */}
                                {suite.id === 'safety' && isSelected && (
                                  <SafetySubtests
                                    testId={test.id}
                                    selectedSubtests={(() => {
                                      // Map test ID to category to get correct subtests
                                      const categoryMap: Record<string, SafetyCategory> = {
                                        'toxicity_detection': 'toxicity',
                                        'hate_speech': 'hate',
                                        'violence_detection': 'violence',
                                        'adult_content': 'adult',
                                        'self_harm': 'self_harm',
                                        'misinformation': 'misinformation'
                                      };
                                      const category = categoryMap[test.id] || 'toxicity';
                                      return safetySubtests[category] || [];
                                    })()}
                                    onSubtestsChange={(category, subtests) => {
                                      handleSafetySubtestChange(category, subtests);
                                    }}
                                    className="mt-2"
                                  />
                                )}
                              </div>
                            </div>
                            
                            {/* Test actions */}
                            <div className="flex items-center gap-2">
                              <button
                                className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
                                title="Test details"
                              >
                                <Info size={16} className="text-slate-400 dark:text-slate-500" />
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          );
        })}
      </div>
      
      {/* Summary */}
      <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-200 dark:border-slate-700">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="font-medium text-slate-900 dark:text-slate-100">
              Selection Summary
            </h4>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              {estimates.totalTests} tests across {Object.keys(selectedTests).length} suites
            </p>
          </div>
          
          <div className="text-right">
            <div className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              ${estimates.totalCost.toFixed(2)}
            </div>
            <div className="text-sm text-slate-600 dark:text-slate-400">
              ~{Math.ceil(estimates.totalDurationMinutes)} minutes
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
