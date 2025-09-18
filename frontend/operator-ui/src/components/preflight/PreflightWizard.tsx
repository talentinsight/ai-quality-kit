import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, Shield } from 'lucide-react';
import { usePreflightStore } from '../../stores/preflightStore';
import StepLLMType from './StepLLMType';
import StepConnect from './StepConnect';
import GuardrailsSheet from './GuardrailsSheet';
import SuitesAccordion from './SuitesAccordion';
import RagDataSideSheet from './RagDataSideSheet';
import BottomRunBar from './BottomRunBar';
import { 
  OrchestratorPayloadBuilder, 
  PreflightGateService,
  TestDedupeService,
  type PreflightGateResult 
} from '../../lib/orchestratorPayload';
import type { DataRequirements } from '../../types/metrics';

interface PreflightWizardProps {
  onRunTests: (config: any) => void;
}

export default function PreflightWizard({ onRunTests }: PreflightWizardProps) {
  const preflightStore = usePreflightStore();
  const { llmType, targetMode, rules, estimated, dryRun } = preflightStore;
  const [currentStep, setCurrentStep] = useState(1);
  const [isGuardrailsSheetOpen, setIsGuardrailsSheetOpen] = useState(false);
  const [isRagDataSheetOpen, setIsRagDataSheetOpen] = useState(false);
  const [showSuites, setShowSuites] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  
  // Specialist suites state
  const [selectedTests, setSelectedTests] = useState<Record<string, string[]>>({});
  const [dataStatus, setDataStatus] = useState<Partial<DataRequirements>>({});
  const [testDataId, setTestDataId] = useState<string>('');
  const [ephemeralIds, setEphemeralIds] = useState<Record<string, Record<string, string>>>({});
  
  // Preflight gate state
  const [preflightResult, setPreflightResult] = useState<PreflightGateResult | null>(null);
  const [preflightRunning, setPreflightRunning] = useState(false);

  const steps = [
    { id: 1, title: 'LLM Type', completed: !!llmType },
    { id: 2, title: 'Connect', completed: !!targetMode },
    { id: 3, title: 'Guardrails', completed: Object.values(rules).some(r => r.enabled) },
    { id: 4, title: 'Specialist Suites', completed: showSuites }
  ];

  const handleStepClick = (stepId: number) => {
    // Allow navigation to completed steps or the next step
    const maxAllowedStep = Math.min(
      steps.findIndex(s => !s.completed) + 1 || steps.length,
      steps.length
    );
    if (stepId <= maxAllowedStep) {
      setCurrentStep(stepId);
    }
  };

  const handleNext = () => {
    if (currentStep < steps.length) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleGuardrailsOpen = () => {
    setIsGuardrailsSheetOpen(true);
  };

  const handleGuardrailsClose = () => {
    setIsGuardrailsSheetOpen(false);
  };

  const handlePreflightComplete = () => {
    setShowSuites(true);
    handleNext();
  };

  const handleRunTests = async () => {
    setIsRunning(true);
    
    try {
      // Step 1: Run preflight check first
      setPreflightRunning(true);
      const preflightResult = await PreflightGateService.runPreflight(preflightStore);
      setPreflightResult(preflightResult);
      setPreflightRunning(false);
      
      // Step 2: Check if preflight gates the run
      const guardrailsMode = new OrchestratorPayloadBuilder(
        preflightStore, 
        selectedTests, 
        dataStatus, 
        testDataId,
        ephemeralIds
      ).buildPayload().guardrails_config?.mode || 'advisory';
      
      const gateCheck = PreflightGateService.shouldGateRun(preflightResult, guardrailsMode);
      
      if (gateCheck.blocked) {
        // Show blocked message and return
        alert(`Run blocked: ${gateCheck.reason}`);
        return;
      }
      
      // Step 3: Mark preflight fingerprints as executed
      preflightResult.signals.forEach(signal => {
        TestDedupeService.markExecuted(
          'guardrails', 
          signal.category, 
          'preflight'
        );
      });
      
      // Step 4: Build orchestrator payload with Classic parity
      const payloadBuilder = new OrchestratorPayloadBuilder(
        preflightStore,
        selectedTests,
        dataStatus,
        testDataId,
        ephemeralIds
      );
      
      const payload = payloadBuilder.buildPayload();
      
      // Step 5: Execute tests via existing orchestrator
      await onRunTests(payload);
      
    } catch (error) {
      console.error('Test run failed:', error);
      alert(`Test run failed: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsRunning(false);
      setPreflightRunning(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0B0D12] pb-24">
      {/* Progress Steps */}
      <div className="sticky top-0 z-20 bg-slate-50/95 dark:bg-[#0B0D12]/95 backdrop-blur-md border-b border-slate-200 dark:border-gray-800">
        <div className="max-w-[1120px] mx-auto px-6 py-4">
          <div className="flex items-center justify-center">
            <div className="flex items-center gap-2">
              {steps.map((step, index) => (
                <React.Fragment key={step.id}>
                  <button
                    onClick={() => handleStepClick(step.id)}
                    className={`
                      flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-200 min-h-[44px]
                      ${currentStep === step.id 
                        ? 'bg-purple-600 text-white' 
                        : step.completed 
                          ? 'bg-green-600/20 text-green-600 dark:text-green-300 hover:bg-green-600/30' 
                          : 'bg-slate-200 dark:bg-gray-800 text-slate-600 dark:text-gray-400 hover:bg-slate-300 dark:hover:bg-gray-700'
                      }
                      ${step.completed || currentStep >= step.id ? 'cursor-pointer' : 'cursor-not-allowed opacity-50'}
                    `}
                    disabled={!step.completed && currentStep < step.id}
                  >
                    <div className={`
                      w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold
                      ${currentStep === step.id 
                        ? 'bg-white text-purple-600' 
                        : step.completed 
                          ? 'bg-green-500 text-white' 
                          : 'bg-slate-400 dark:bg-gray-600 text-white dark:text-gray-300'
                      }
                    `}>
                      {step.completed ? '✓' : step.id}
                    </div>
                    <span className="text-sm font-medium">{step.title}</span>
                  </button>
                  
                  {index < steps.length - 1 && (
                    <ChevronRight className="w-4 h-4 text-slate-400 dark:text-gray-600" />
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-[1120px] mx-auto px-6 py-8">
        <AnimatePresence mode="wait">
          {/* Step 1: LLM Type */}
          {currentStep === 1 && (
            <motion.div
              key="step1"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.28 }}
            >
              <StepLLMType />
              {llmType && (
                <div className="flex justify-center mt-8">
                  <button
                    onClick={handleNext}
                    className="flex items-center gap-2 px-6 py-3 bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-xl transition-colors duration-200"
                  >
                    Continue
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              )}
            </motion.div>
          )}

          {/* Step 2: Connect */}
          {currentStep === 2 && (
            <motion.div
              key="step2"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.28 }}
            >
              <StepConnect />
              {targetMode && (
                <div className="flex justify-center mt-8">
                  <button
                    onClick={handleNext}
                    className="flex items-center gap-2 px-6 py-3 bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-xl transition-colors duration-200"
                  >
                    Continue
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              )}
            </motion.div>
          )}

          {/* Step 3: Guardrails */}
          {currentStep === 3 && (
            <motion.div
              key="step3"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.28 }}
              className="space-y-8"
            >
              {/* Guardrails Trigger */}
              <div className="text-center">
                <div className="flex items-center justify-center gap-3 mb-4">
                  <div className="w-8 h-8 bg-purple-600 rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold text-sm">1</span>
                  </div>
                  <h2 className="text-2xl font-bold text-white">Guardrails Preflight</h2>
                </div>
                <p className="text-gray-400 mb-4">Quick safety gate - runs in ~30 seconds</p>
                <div className="text-sm text-gray-500 bg-gray-800/50 p-3 rounded-lg mb-8 max-w-2xl mx-auto">
                  <strong>Purpose:</strong> Fast preliminary checks before running comprehensive tests.
                  <br />
                  <strong>Coverage:</strong> PII detection, jailbreak protection, toxicity filtering, basic performance.
                </div>
                
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleGuardrailsOpen}
                  className="inline-flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-semibold rounded-xl shadow-lg transition-all duration-200"
                >
                  <Shield className="w-5 h-5" />
                  Open Guardrails Configuration
                </motion.button>
              </div>

              {/* Quick Summary */}
              {Object.values(rules).some(r => r.enabled) && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-[#0F1117] border border-gray-700 rounded-xl p-6"
                >
                  <h3 className="text-lg font-semibold text-white mb-4">Current Configuration</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-gray-400">Enabled Rules:</span>
                      <span className="text-white ml-2 font-medium">
                        {Object.values(rules).filter(r => r.enabled).length}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-400">Estimated Tests:</span>
                      <span className="text-white ml-2 font-medium">{estimated.tests}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">Estimated Cost:</span>
                      <span className="text-white ml-2 font-medium">${estimated.costUsd.toFixed(3)}</span>
                    </div>
                  </div>
                  
                  <div className="flex justify-center mt-6">
                    <button
                      onClick={handleNext}
                      className="flex items-center gap-2 px-6 py-3 bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-xl transition-colors duration-200"
                    >
                      Continue to Specialist Suites
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </motion.div>
              )}
            </motion.div>
          )}

          {/* Step 4: Specialist Suites */}
          {currentStep === 4 && (
            <motion.div
              key="step4"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.28 }}
            >
              <SuitesAccordion 
                onRagDataClick={() => setIsRagDataSheetOpen(true)}
                dataStatus={dataStatus}
                onSelectionChange={setSelectedTests}
                onEphemeralIdsChange={setEphemeralIds}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Guardrails Sheet */}
      <GuardrailsSheet
        isOpen={isGuardrailsSheetOpen}
        onClose={handleGuardrailsClose}
        onRunPreflight={handlePreflightComplete}
      />

      {/* RAG Data Side Sheet */}
      <RagDataSideSheet
        isOpen={isRagDataSheetOpen}
        onClose={() => setIsRagDataSheetOpen(false)}
      />

      {/* Bottom Run Bar */}
      <BottomRunBar
        onRunTests={handleRunTests}
        isRunning={isRunning}
        selectedTests={selectedTests}
        preflightRunning={preflightRunning}
        preflightResult={preflightResult}
      />
    </div>
  );
}
