import React, { useState, useRef, useEffect } from 'react';
import { useWizardStore, getNextStep, getPreviousStep, isStepOptional } from '../stores/wizardStore';
import { RunConfig, StepId, Message } from '../types/runConfig';
import MessageBubble from './MessageBubble';
import SuggestionChips from './SuggestionChips';

import InlineDrawer from './InlineDrawer';
import RequirementsMatrix from './RequirementsMatrix';
import { computeRequirementMatrix, hasBlocking, ProvidedIntake } from '../lib/requirementStatus';
import { postRunTests, mapRunConfigToRequest } from '../lib/api';
import { ChevronLeft, ChevronRight, CheckCircle, Circle, Play, Download, Settings, Paperclip, Send } from 'lucide-react';

interface TestResult {
  run_id: string;
  success: boolean;
  duration_ms: number;
  suites: string[];
  provider: string;
  model: string;
}

const stepOrder: StepId[] = [
  'mode', 'base', 'auth', 'provider', 'model', 
  'suites', 'thresholds', 'volumes', 'resilience', 
  'compliance', 'bias', 'testdataId', 'testData', 'summary'
];

const stepLabels: Record<StepId, string> = {
  mode: 'Mode',
  base: 'Base',
  auth: 'Auth',
  provider: 'Provider',
  model: 'Model',
  suites: 'Suites',
  thresholds: 'Thresholds',
  volumes: 'Volumes',
  resilience: 'Resilience',
  compliance: 'Compliance',
  bias: 'Bias',
  testdataId: 'Test Data ID',
  testData: 'Test Data',
  summary: 'Summary'
};

const ChatWizard: React.FC = () => {
  const {
    config,
    currentStep,
    completedSteps,
    messages,
    isProcessing,
    errors,
    updateConfig,
    setCurrentStep,
    markStepCompleted,
    addMessage,
    setProcessing,
    setErrors,
    validateStep,
    reset
  } = useWizardStore();

  // Add test result state
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [reportsReady, setReportsReady] = useState(false);

  const [inputValue, setInputValue] = useState('');
  const [showDrawer, setShowDrawer] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isRunning, setIsRunning] = useState(false);

  // Requirements matrix state
  const [useDefaults, setUseDefaults] = useState(true);
  const [showRequirementsModal, setShowRequirementsModal] = useState(false);
  
  // Artifacts state for real API results
  const [artifacts, setArtifacts] = useState<{json_path?:string;xlsx_path?:string;powerbi?:string} | null>(null);
  
  // Power BI config state
  const [powerbiConfig, setPowerbiConfig] = useState<{powerbi_enabled: boolean; powerbi_embed_report_url?: string} | null>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Initialize with welcome message
  useEffect(() => {
    if (messages.length === 0) {
      addMessage({
        type: 'assistant',
        content: `Hello! I'm your AI Quality Kit assistant. I'll help you configure and run comprehensive tests for your AI system.

Let's start by choosing your target mode. Are you testing an API endpoint or an MCP server?`
      });
    }
  }, [messages.length, addMessage]);

  // Fetch Power BI configuration
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const base = (config.base_url || "").replace(/\/+$/,"");
        const response = await fetch(`${base}/config`);
        if (response.ok) {
          const configData = await response.json();
          setPowerbiConfig(configData);
        }
      } catch (error) {
        console.log('Failed to fetch config:', error);
      }
    };
    
    if (config.base_url) {
      fetchConfig();
    }
  }, [config.base_url]);

  const handleInputSubmit = async (input: string) => {
    if (!input.trim() || isProcessing) return;

    // Add user message
    addMessage({
      type: 'user',
      content: input
    });

    setInputValue('');
    setProcessing(true);

    try {
      // Process the input and update configuration
      await processUserInput(input);
    } catch (error) {
      addMessage({
        type: 'assistant',
        content: `I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}`
      });
    } finally {
      setProcessing(false);
    }
  };

  const processUserInput = async (input: string) => {
    const inputLower = input.toLowerCase();
    
    switch (currentStep) {
      case 'mode':
        if (inputLower.includes('api') || inputLower.includes('endpoint')) {
          updateConfig({ target_mode: 'api' });
          addMessage({
            type: 'assistant',
            content: `Great! You've chosen API mode. Now I need the base URL of your API endpoint. What's the URL? (e.g., http://localhost:8000)`
          });
          setCurrentStep('base');
          markStepCompleted('mode');
        } else if (inputLower.includes('mcp') || inputLower.includes('server')) {
          updateConfig({ target_mode: 'mcp' });
          addMessage({
            type: 'assistant',
            content: `Perfect! You've chosen MCP mode. Now I need the MCP server URL. What's the URL? (e.g., stdio:///path/to/mcp-server)`
          });
          setCurrentStep('base');
          markStepCompleted('mode');
        } else {
          addMessage({
            type: 'assistant',
            content: `I need to know whether you're testing an API endpoint or an MCP server. Please specify "API" or "MCP".`
          });
        }
        break;

      case 'base':
        const url = input.trim();
        if (url) {
          updateConfig({ base_url: url });
          addMessage({
            type: 'assistant',
            content: `URL set to: ${url}

Do you need to provide authentication? If yes, what type? (Bearer token, API key, etc.)`
          });
          setCurrentStep('auth');
          markStepCompleted('base');
        } else {
          addMessage({
            type: 'assistant',
            content: `Please provide a valid URL.`
          });
        }
        break;

      case 'auth':
        if (inputLower.includes('no') || inputLower.includes('skip') || inputLower.includes('none')) {
          addMessage({
            type: 'assistant',
            content: `No authentication needed. 

Now, which AI provider are you using? (OpenAI, Anthropic, Gemini, Custom REST, or Mock)`
          });
          setCurrentStep('provider');
          markStepCompleted('auth');
        } else if (inputLower.includes('bearer') || inputLower.includes('token')) {
          addMessage({
            type: 'assistant',
            content: `Please provide your Bearer token.`
          });
          // Stay on auth step to collect token
        } else if (inputLower.includes('api key')) {
          addMessage({
            type: 'assistant',
            content: `Please provide your API key.`
          });
          // Stay on auth step to collect key
        } else {
          // Assume they provided the token/key
          updateConfig({ bearer_token: input.trim() });
          addMessage({
            type: 'assistant',
            content: `Authentication configured. 

Now, which AI provider are you using? (OpenAI, Anthropic, Gemini, Custom REST, or Mock)`
          });
          setCurrentStep('provider');
          markStepCompleted('auth');
        }
        break;

      case 'provider':
        if (inputLower.includes('openai')) {
          updateConfig({ provider: 'openai' });
          addMessage({
            type: 'assistant',
            content: `OpenAI provider selected. Which model would you like to test? You can select from: gpt-4, gpt-4-turbo, gpt-4o, gpt-3.5-turbo, gpt-3.5-turbo-16k`
          });
          setCurrentStep('model');
          markStepCompleted('provider');
        } else if (inputLower.includes('anthropic')) {
          updateConfig({ provider: 'anthropic' });
          addMessage({
            type: 'assistant',
            content: `Anthropic provider selected. Which model would you like to test? You can select from: claude-3-opus, claude-3-sonnet, claude-3-haiku, claude-2.1, claude-2.0`
          });
          setCurrentStep('model');
          markStepCompleted('provider');
        } else if (inputLower.includes('gemini')) {
          updateConfig({ provider: 'gemini' });
          addMessage({
            type: 'assistant',
            content: `Gemini provider selected. Which model would you like to test? You can select from: gemini-1.5-pro, gemini-1.5-flash, gemini-pro, gemini-flash`
          });
          setCurrentStep('model');
          markStepCompleted('provider');
        } else if (inputLower.includes('custom') || inputLower.includes('rest')) {
          updateConfig({ provider: 'custom_rest' });
          addMessage({
            type: 'assistant',
            content: `Custom REST provider selected. Which model would you like to test? (Enter the model name)`
          });
          setCurrentStep('model');
          markStepCompleted('provider');
        } else if (inputLower.includes('mock')) {
          updateConfig({ provider: 'mock' });
          addMessage({
            type: 'assistant',
            content: `Mock provider selected. Which model would you like to test? You can select from: mock-model-1, mock-model-2, mock-model-3`
          });
          setCurrentStep('model');
          markStepCompleted('provider');
        } else {
          addMessage({
            type: 'assistant',
            content: `Please specify a valid provider: OpenAI, Anthropic, Gemini, Custom REST, or Mock.`
          });
        }
        break;

      case 'model':
        const model = input.trim();
        if (model) {
          updateConfig({ model: model });
          addMessage({
            type: 'assistant',
            content: `Model set to: ${model}

Now let's configure the test suites. Which test suites would you like to run? (rag_quality, red_team, safety, performance, regression, resilience, compliance_smoke, bias_smoke)`
          });
          setCurrentStep('suites');
          markStepCompleted('model');
        } else {
          addMessage({
            type: 'assistant',
            content: `Please provide a valid model name.`
          });
        }
        break;

      case 'suites':
        const suites = input.trim().split(',').map(s => s.trim());
        if (suites.length > 0 && suites.every(s => s)) {
          updateConfig({ test_suites: suites });
          addMessage({
            type: 'assistant',
            content: `Test suites configured: ${suites.join(', ')}

Now let's set the quality thresholds. What's your minimum faithfulness score? (0.0 to 1.0, default: 0.80)`
          });
          setCurrentStep('thresholds');
          markStepCompleted('suites');
        } else {
          addMessage({
            type: 'assistant',
            content: `Please provide valid test suite names separated by commas.`
          });
        }
        break;

      case 'thresholds':
        const faithScore = parseFloat(input);
        if (!isNaN(faithScore) && faithScore >= 0 && faithScore <= 1) {
          updateConfig({ 
            thresholds: { 
              ...config.thresholds, 
              faithfulness_min: faithScore 
            } 
          });
          addMessage({
            type: 'assistant',
            content: `Faithfulness threshold set to: ${faithScore}

What's your minimum context recall score? (0.0 to 1.0, default: 0.80)`
          });
          // Stay on thresholds step to collect more values
        } else {
          addMessage({
            type: 'assistant',
            content: `Please provide a valid score between 0.0 and 1.0.`
          });
        }
        break;

      case 'volumes':
        addMessage({
          type: 'assistant',
          content: `Volume profiles configured. Now let's set up resilience testing. Would you like to enable synthetic load testing? (yes/no)`
        });
        setCurrentStep('resilience');
        markStepCompleted('volumes');
        break;

      case 'resilience':
        addMessage({
          type: 'assistant',
          content: `Resilience testing configured. Now let's set up compliance testing. Would you like to enable PII scanning? (yes/no)`
        });
        setCurrentStep('compliance');
        markStepCompleted('resilience');
        break;

      case 'compliance':
        addMessage({
          type: 'assistant',
          content: `Compliance testing configured. Now let's set up bias testing. Would you like to enable bias detection? (yes/no)`
        });
        setCurrentStep('bias');
        markStepCompleted('compliance');
        break;

      case 'bias':
        addMessage({
          type: 'assistant',
          content: `Bias testing configured. Do you have a specific test data ID to use? (Enter ID or say "no" to use default)`
        });
        setCurrentStep('testdataId');
        markStepCompleted('bias');
        break;

      case 'testdataId':
        if (inputLower.includes('no') || inputLower.includes('default')) {
          addMessage({
            type: 'assistant',
            content: `Using default test data. Would you like to upload custom test data files? (Upload, URL, Paste, or ZIP)`
          });
          setCurrentStep('testData');
          markStepCompleted('testdataId');
        } else {
          updateConfig({ testdata_id: input.trim() });
          addMessage({
            type: 'assistant',
            content: `Test data ID set to: ${input.trim()}. Would you like to upload custom test data files? (Upload, URL, Paste, or ZIP)`
          });
          setCurrentStep('testData');
          markStepCompleted('testdataId');
        }
        break;

      case 'testData':
        addMessage({
          type: 'assistant',
          content: `Test data configuration complete. Let me show you a summary of your configuration and then we can run the tests.`
        });
        setCurrentStep('summary');
        markStepCompleted('testData');
        break;

      case 'summary':
        addMessage({
          type: 'assistant',
          content: `Perfect! Your configuration is complete. You can now run the tests using the "Run Tests" button in the configuration panel, or type "run tests" to proceed.`
        });
        break;

      default:
        addMessage({
          type: 'assistant',
          content: `I'm not sure how to handle that input for the current step. Please try again or ask for help.`
        });
    }
  };

  const getSuggestions = () => {
    const suggestions = (() => {
      switch (currentStep) {
        case 'mode':
          return ['API', 'MCP'];
        case 'provider':
          return ['OpenAI', 'Anthropic', 'Gemini', 'Custom REST', 'Mock'];
        case 'model':
          // Return model options based on selected provider
          switch (config.provider) {
            case 'openai':
              return ['gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-3.5-turbo', 'gpt-3.5-turbo-16k'];
            case 'anthropic':
              return ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku', 'claude-2.1', 'claude-2.0'];
            case 'gemini':
              return ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro', 'gemini-flash'];
            case 'custom_rest':
              return ['custom-model-1', 'custom-model-2', 'local-llm'];
            case 'mock':
              return ['mock-model-1', 'mock-model-2', 'mock-model-3'];
            default:
              return ['Enter model name'];
          }
        case 'suites':
          return ['rag_quality', 'red_team', 'safety', 'performance', 'regression', 'resilience', 'compliance_smoke', 'bias_smoke'];
        case 'volumes':
          return ['Smoke', 'Full', 'Red Team Heavy'];
        case 'resilience':
          return ['Yes', 'No'];
        case 'compliance':
          return ['Yes', 'No'];
        case 'bias':
          return ['Yes', 'No'];
        case 'testdataId':
          return ['No', 'Use default'];
        case 'testData':
          return ['Upload', 'URL', 'Paste', 'ZIP'];
        case 'summary':
          return ['Run tests', 'Show summary', 'Validate config'];
        default:
          return [];
      }
    })();
    return suggestions;
  };

  const handleRunTests = async () => {
    setIsRunning(true);
    try {
      const req = mapRunConfigToRequest(config);
      const result = await postRunTests(req, config.bearer_token || null);
      
      setTestResult({
        run_id: result.run_id,
        success: true, // If we get here without error, it's successful
        duration_ms: 0, // if you want, compute from timestamps
        suites: config.test_suites || [],
        provider: config.provider || 'unknown',
        model: config.model || 'unknown'
      });
      setReportsReady(true);
      setArtifacts(result.artifacts); // add a local state {json_path, xlsx_path}
      
      addMessage({
        type: 'assistant',
        content: `Tests completed successfully! Run ID: ${result.run_id}

You can download JSON/XLSX reports from the configuration panel.`
      });
    } catch (error: any) {
      addMessage({
        type: 'assistant',
        content: `Test execution failed: ${error?.message || 'Unknown error'}`
      });
    } finally {
      setIsRunning(false);
    }
  };

  const getEstimatedTests = () => {
    const baseTests = 50;
    const suiteMultiplier = (config.test_suites?.length || 0) * 0.8;
    const volumeMultiplier = 1.2; // Default to full profile
    return Math.round(baseTests * (1 + suiteMultiplier) * volumeMultiplier);
  };

  const maskToken = (token: string) => {
    if (!token) return '';
    if (token.length <= 8) return '*'.repeat(token.length);
    return '*'.repeat(token.length - 4) + token.slice(-4);
  };

  // Compute provided intake from config
  const getProvidedIntake = (): ProvidedIntake => {
    const provided: ProvidedIntake = {};
    
    // Mock data counts - in real implementation, this would come from test data state
    // For now, we'll assume no data is provided unless config.test_data exists
    if (config.test_data) {
      if (config.test_data.passages) {
        provided.passages = { count: 10 }; // Mock count
      }
      if (config.test_data.qaset) {
        provided.qaset = { count: 5 }; // Mock count
      }
      if (config.test_data.attacks) {
        provided.attacks = { count: 15 }; // Mock count
      }
      if (config.test_data.schema) {
        provided.schema = { ok: true };
      }
    }
    
    // Handle compliance PII patterns
    if (config.compliance?.pii_patterns_file) {
      provided.pii_patterns = { path: config.compliance.pii_patterns_file };
    }
    
    // Handle bias groups
    if (config.bias?.groups_csv) {
      const pairs = config.bias.groups_csv.split(';').length;
      provided.bias_groups = { pairs };
    }
    
    return provided;
  };

  // Compute requirements matrix
  const providedIntake = getProvidedIntake();
  const requirementRows = computeRequirementMatrix(config.test_suites, providedIntake, useDefaults);
  const runBlocked = hasBlocking(requirementRows);

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Progress Bar */}
      <div className="sticky top-0 z-10 bg-white/90 backdrop-blur border-b">
        <div className="max-w-[820px] mx-auto px-4 py-3">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${
                completedSteps.size > 0 ? 'bg-green-500' : 'bg-gray-300'
              }`} />
              <span className="text-gray-600">
                Step {stepOrder.indexOf(currentStep) + 1} of {stepOrder.length}: {stepLabels[currentStep]}
              </span>
            </div>
            <div className="text-gray-400">
              {completedSteps.size}/{stepOrder.length} completed
            </div>
          </div>
          <div className="mt-2 w-full bg-gray-200 rounded-full h-1">
            <div 
              className="bg-blue-500 h-1 rounded-full transition-all duration-300" 
              style={{ width: `${(completedSteps.size / stepOrder.length) * 100}%` }}
            />
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex">
        {/* Chat Area - Centered */}
        <div className="flex-1 flex flex-col max-w-[820px] mx-auto px-4 lg:px-6">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto pt-4 pb-28 space-y-3">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            
            {/* Test Results Display */}
            {testResult && (
              <div className="bg-green-50 border border-green-200 rounded-2xl p-4">
                <h3 className="text-lg font-semibold text-green-800 mb-2">🎉 Test Execution Complete!</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div><span className="font-medium">Run ID:</span> {testResult.run_id}</div>
                  <div><span className="font-medium">Duration:</span> {Math.round(testResult.duration_ms / 1000)}s</div>
                  <div><span className="font-medium">Provider:</span> {testResult.provider}</div>
                  <div><span className="font-medium">Model:</span> {testResult.model}</div>
                  <div className="col-span-2"><span className="font-medium">Suites:</span> {testResult.suites.join(', ')}</div>
                </div>
                
                {reportsReady && artifacts && (
                  <div className="mt-4 space-y-2">
                    <h4 className="font-medium text-green-700">📁 Download Reports:</h4>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => {
                          const base = (config.base_url || "").replace(/\/+$/,"");
                          const jsonUrl = (artifacts?.json_path?.startsWith("/") ? base + artifacts.json_path : artifacts?.json_path) || "#";
                          window.open(jsonUrl, "_blank");
                        }}
                        disabled={!artifacts?.json_path}
                        className="px-3 py-1 bg-blue-500 text-white rounded-2xl text-sm hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Download JSON
                      </button>
                      <button
                        onClick={() => {
                          const base = (config.base_url || "").replace(/\/+$/,"");
                          const xlsxUrl = (artifacts?.xlsx_path?.startsWith("/") ? base + artifacts.xlsx_path : artifacts?.xlsx_path) || "#";
                          window.open(xlsxUrl, "_blank");
                        }}
                        disabled={!artifacts?.xlsx_path}
                        className="px-3 py-1 bg-green-500 text-white rounded-2xl text-sm hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Download Excel
                      </button>
                      
                      {/* Power BI Button */}
                      {powerbiConfig?.powerbi_enabled && artifacts?.powerbi && (
                        <button
                          onClick={() => {
                            if (powerbiConfig.powerbi_embed_report_url) {
                              window.open(powerbiConfig.powerbi_embed_report_url, "_blank");
                            } else {
                              // Show tooltip or message about opening workspace
                              alert("Dataset published to Power BI workspace. Open your Power BI workspace to build a report.");
                            }
                          }}
                          className="px-3 py-1 bg-purple-500 text-white rounded-2xl text-sm hover:bg-purple-600 transition-colors"
                          title={powerbiConfig.powerbi_embed_report_url ? "View in Power BI" : "Dataset published to Power BI workspace; open your workspace to build a report"}
                        >
                          View in Power BI
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggestion Chips - Above Composer */}
          <div className="px-4 py-2 border-t bg-white/80 backdrop-blur">
            {!isProcessing && (
              <SuggestionChips 
                suggestions={getSuggestions()} 
                onSelect={(suggestion: string) => handleInputSubmit(suggestion)}
                disabled={isProcessing}
              />
            )}
            {isProcessing && (
              <div className="flex items-center space-x-2 text-sm text-gray-500 mb-3">
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-500 border-t-transparent" />
                <span>Processing your input...</span>
              </div>
            )}
          </div>

          {/* Sticky Composer */}
          <div className="fixed bottom-0 inset-x-0 z-20 border-t bg-white/85 backdrop-blur px-4 py-3">
            <div className="max-w-[820px] mx-auto">
              <div className="flex items-end space-x-3">
                <button
                  type="button"
                  disabled={isProcessing}
                  className="flex-shrink-0 p-2 text-gray-400 hover:text-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Attach file"
                >
                  <Paperclip className="w-5 h-5" />
                </button>

                <div className="flex-1 min-w-0">
                  <textarea
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleInputSubmit(inputValue);
                      }
                    }}
                    placeholder={`Tell me about ${stepLabels[currentStep].toLowerCase()}...`}
                    disabled={isProcessing}
                    rows={1}
                    className="w-full rounded-2xl border px-4 py-3 focus:ring-2 focus:ring-gray-300 resize-none"
                    style={{
                      minHeight: '24px',
                      maxHeight: '120px'
                    }}
                  />
                </div>

                <button
                  type="button"
                  onClick={() => handleInputSubmit(inputValue)}
                  disabled={isProcessing || !inputValue.trim()}
                  className="flex-shrink-0 px-4 py-3 bg-black text-white rounded-2xl hover:bg-black/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  title="Send message"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
              
              {/* Hint row */}
              <div className="flex items-center justify-between mt-2 text-xs text-gray-400">
                <div className="flex items-center space-x-2">
                  <Paperclip className="w-3 h-3" />
                  <span>Shift+Enter for newline</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Floating Config Preview Panel - Right side, hidden on small screens */}
        <div className="fixed right-4 bottom-24 w-[360px] rounded-2xl border bg-white p-4 shadow-xl hidden xl:block">
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">Configuration Preview</h3>
            
            {/* Allow Default Datasets Toggle */}
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
              <div>
                <div className="text-sm font-medium text-gray-900">Allow default datasets</div>
                <div className="text-xs text-gray-600">No uploads required</div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={useDefaults}
                  onChange={(e) => setUseDefaults(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
            </div>

            {/* Requirements Matrix */}
            {config.test_suites.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-medium text-gray-700">Data Requirements</h4>
                  {runBlocked && (
                    <span className="text-xs text-red-600 font-medium">⚠ Blocked</span>
                  )}
                </div>
                <RequirementsMatrix 
                  rows={requirementRows} 
                  compact={true}
                  onUploadClick={(kind) => {
                    // TODO: Implement upload functionality
                    setShowDrawer(true);
                  }}
                />
              </div>
            )}
            
            {/* Estimated Tests */}
            <div className="text-center p-4 bg-gray-50 rounded-xl">
              <div className="text-2xl font-bold text-gray-900">{getEstimatedTests()}</div>
              <div className="text-sm text-gray-600">Estimated tests</div>
            </div>

            {/* JSON Payload Preview */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Payload</h4>
              <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-auto max-h-32">
                {JSON.stringify({
                  ...config,
                  bearer_token: config.bearer_token ? maskToken(config.bearer_token) : undefined
                }, null, 2)}
              </pre>
            </div>

            {/* Action Buttons */}
            <div className="space-y-2">
              <button
                onClick={() => setShowRequirementsModal(true)}
                className="w-full rounded-2xl border px-4 py-2 hover:bg-gray-50 text-sm"
              >
                Show Requirements
              </button>
              <button
                onClick={() => setShowDrawer(true)}
                className="w-full rounded-2xl border px-4 py-2 hover:bg-gray-50 text-sm"
              >
                Show Summary
              </button>
              <button
                onClick={() => {
                  const errors = validateStep(currentStep);
                  setErrors(errors);
                  if (errors.length === 0) {
                    addMessage({
                      type: 'assistant',
                      content: '✅ Configuration is valid!'
                    });
                  } else {
                    addMessage({
                      type: 'assistant',
                      content: `❌ Configuration has ${errors.length} validation error(s). Please check the details.`
                    });
                  }
                }}
                className="w-full rounded-2xl border px-4 py-2 hover:bg-gray-50 text-sm"
              >
                Validate
              </button>
              
              {/* Run Tests Button with Blocking */}
              <div className="space-y-1">
                <button
                  onClick={handleRunTests}
                  disabled={isRunning || runBlocked}
                  className="w-full rounded-2xl px-4 py-2 bg-black text-white hover:bg-black/90 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                >
                  {isRunning ? 'Running...' : 'Run Tests'}
                </button>
                {runBlocked && (
                  <div className="text-xs text-red-600 px-2">
                    Missing required data for selected suite(s). Upload the items marked Missing or enable 'Allow default datasets'.
                  </div>
                )}
              </div>
            </div>

            {/* Quick Actions */}
            <div className="pt-2 border-t">
              <div className="flex space-x-2">
                <button
                  onClick={reset}
                  className="flex-1 rounded-2xl border px-3 py-2 hover:bg-gray-50 text-xs"
                >
                  Reset
                </button>
                <button
                  onClick={() => setShowDrawer(!showDrawer)}
                  className="flex-1 rounded-2xl border px-3 py-2 hover:bg-gray-50 text-xs"
                >
                  {showDrawer ? 'Hide' : 'Show'} Config
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Inline Drawer for Configuration */}
      {showDrawer && (
        <InlineDrawer
          config={config}
          onUpdate={updateConfig}
          onRun={handleRunTests}
          isRunning={isRunning}
          onClose={() => setShowDrawer(false)}
        />
      )}

      {/* Requirements Matrix Modal */}
      {showRequirementsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-2xl shadow-xl max-w-4xl max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold text-gray-900">Test Data Requirements Matrix</h2>
                <button
                  onClick={() => setShowRequirementsModal(false)}
                  className="p-2 hover:bg-gray-100 rounded-full"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              <RequirementsMatrix 
                rows={requirementRows}
                onUploadClick={(kind) => {
                  setShowRequirementsModal(false);
                  // TODO: Focus the intake drawer and highlight specific data kind
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatWizard;
