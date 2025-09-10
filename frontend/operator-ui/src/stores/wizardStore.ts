import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { RunConfig, StepId, Message, ValidationError } from '../types/runConfig';

interface WizardState {
  // Configuration state
  config: RunConfig;
  currentStep: StepId;
  completedSteps: Set<StepId>;
  
  // Chat state
  messages: Message[];
  isProcessing: boolean;
  
  // Validation
  errors: ValidationError[];
  
  // Actions
  updateConfig: (updates: Partial<RunConfig>) => void;
  resetConfig: () => void;
  setCurrentStep: (step: StepId) => void;
  markStepCompleted: (step: StepId) => void;
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void;
  setProcessing: (processing: boolean) => void;
  setErrors: (errors: ValidationError[]) => void;
  validateStep: (step: StepId) => ValidationError[];
  reset: () => void;
}

const initialConfig: RunConfig = {
  target_mode: null,
  url: '',
  bearer_token: '',
  provider: null,
  model: null,
  test_suites: [],
  thresholds: {},
  volumes: {},
  resilience: {},
  compliance: {},
  bias: {},
  testdata_id: null,
  test_data: null,
};

const stepOrder: StepId[] = [
  'mode', 'base', 'auth', 'provider', 'model', 
  'suites', 'thresholds', 'volumes', 'resilience', 
  'compliance', 'bias', 'testdataId', 'testData', 'summary'
];

export const useWizardStore = create(persist<WizardState>(
  (set, get) => ({
  config: initialConfig,
  currentStep: 'mode',
  completedSteps: new Set(),
  messages: [],
  isProcessing: false,
  errors: [],

  updateConfig: (updates) => set((state) => ({
    config: { ...state.config, ...updates }
  })),

  resetConfig: () => set((state) => ({
    config: initialConfig
  })),

  setCurrentStep: (step) => set({ currentStep: step }),

  markStepCompleted: (step) => set((state) => ({
    completedSteps: new Set([...state.completedSteps, step])
  })),

  addMessage: (message) => set((state) => ({
    messages: [...state.messages, {
      ...message,
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date()
    }]
  })),

  setProcessing: (processing) => set({ isProcessing: processing }),

  setErrors: (errors) => set({ errors }),

  validateStep: (step) => {
    const { config } = get();
    const errors: ValidationError[] = [];

    switch (step) {
      case 'mode':
        if (!config.target_mode) {
          errors.push({ field: 'target_mode', message: 'Target mode is required' });
        }
        break;

      case 'base':
        if (!config.url?.trim()) {
          errors.push({ field: 'url', message: 'URL is required' });
        }
        break;

      case 'provider':
        if (config.target_mode === 'api' && !config.provider) {
          errors.push({ field: 'provider', message: 'Provider is required for API mode' });
        }
        break;

      case 'model':
        if (config.target_mode === 'api' && config.provider && ['openai', 'anthropic', 'gemini', 'mock'].includes(config.provider) && !config.model) {
          errors.push({ field: 'model', message: 'Model is required for this provider' });
        }
        break;

      case 'suites':
        if (config.test_suites.length === 0) {
          errors.push({ field: 'test_suites', message: 'At least one test suite is required' });
        }
        break;
    }

    return errors;
  },

  reset: () => set({
    config: initialConfig,
    currentStep: 'mode',
    completedSteps: new Set(),
    messages: [],
    isProcessing: false,
    errors: []
  })
  }),
  { name: "wizard-v1" }
));

// Helper functions
export const getNextStep = (currentStep: StepId): StepId | null => {
  const currentIndex = stepOrder.indexOf(currentStep);
  return currentIndex < stepOrder.length - 1 ? stepOrder[currentIndex + 1] : null;
};

export const getPreviousStep = (currentStep: StepId): StepId | null => {
  const currentIndex = stepOrder.indexOf(currentStep);
  return currentIndex > 0 ? stepOrder[currentIndex - 1] : null;
};

export const isStepOptional = (step: StepId): boolean => {
  return ['auth', 'thresholds', 'volumes', 'resilience', 'compliance', 'bias', 'testdataId', 'testData'].includes(step);
};

// Helper selector for API mode
export const useIsApiMode = () => useWizardStore(s => s.config?.target_mode === "api");
