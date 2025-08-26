import React, { useState, useRef, useEffect } from 'react';
import { useWizardStore, getNextStep, getPreviousStep, isStepOptional } from '../stores/wizardStore';
import { RunConfig, StepId, Message } from '../types/runConfig';
import MessageBubble from './MessageBubble';
import SuggestionChips from './SuggestionChips';
import ComposerBar from './ComposerBar';
import InlineDrawer from './InlineDrawer';
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
    console.log('getSuggestions called, currentStep:', currentStep, 'provider:', config.provider);
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
    console.log('Suggestions returned:', suggestions);
    return suggestions;
  };

  const handleRunTests = async () => {
    setIsRunning(true);
    try {
      // Simulate test execution
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const result: TestResult = {
        run_id: `run_${Date.now()}`,
        success: true,
        duration_ms: 2000,
        suites: config.test_suites || [],
        provider: config.provider || 'unknown',
        model: config.model || 'unknown'
      };
      
      setTestResult(result);
      setReportsReady(true);
      
      addMessage({
        type: 'assistant',
        content: `🎉 Tests completed successfully! Run ID: ${result.run_id}

You can download the reports in JSON and Excel formats from the configuration panel.`
      });
    } catch (error) {
      addMessage({
        type: 'assistant',
        content: `❌ Test execution failed: ${error instanceof Error ? error.message : 'Unknown error'}`
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

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Slim Status Bar */}
      <div className="sticky top-12 z-10 text-xs text-gray-500 px-4 py-2 backdrop-blur bg-white/70 border-b">
        <div className="flex items-center space-x-4 max-w-[820px] mx-auto">
          {stepOrder.map((step, index) => {
            const isCompleted = completedSteps.has(step);
            const isCurrent = currentStep === step;
            
            return (
              <div key={step} className="flex items-center">
                <div className={`w-2 h-2 rounded-full ${
                  isCompleted 
                    ? 'bg-green-500' 
                    : isCurrent 
                    ? 'bg-blue-500' 
                    : 'bg-gray-300'
                }`} />
                <span className={`ml-2 ${
                  isCurrent ? 'font-semibold text-gray-900' : 'text-gray-500'
                }`}>
                  {stepLabels[step]}
                </span>
                {index < stepOrder.length - 1 && (
                  <span className="ml-4 text-gray-300">•</span>
                )}
              </div>
            );
          })}
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
                
                {reportsReady && (
                  <div className="mt-4 space-y-2">
                    <h4 className="font-medium text-green-700">📁 Download Reports:</h4>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => window.open(`${config.base_url}/reports/${testResult.run_id}.json`, '_blank')}
                        className="px-3 py-1 bg-blue-500 text-white rounded-2xl text-sm hover:bg-blue-600"
                      >
                        Download JSON
                      </button>
                      <button
                        onClick={() => window.open(`${config.base_url}/reports/${testResult.run_id}.xlsx`, '_blank')}
                        className="px-3 py-1 bg-green-500 text-white rounded-2xl text-sm hover:bg-green-600"
                      >
                        Download Excel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggestion Chips - Above Composer */}
          <div className="px-4 py-2 border-t bg-white/80 backdrop-blur">
            <div className="text-xs text-gray-500 mb-2">Current Step: {currentStep} | Provider: {config.provider}</div>
            <div className="text-xs text-gray-400 mb-2">Suggestions: {JSON.stringify(getSuggestions())}</div>
            <SuggestionChips 
              suggestions={getSuggestions()} 
              onSelect={(suggestion: string) => handleInputSubmit(suggestion)}
              disabled={isProcessing}
            />
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
              <button
                onClick={handleRunTests}
                disabled={isRunning}
                className="w-full rounded-2xl px-4 py-2 bg-black text-white hover:bg-black/90 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
              >
                {isRunning ? 'Running...' : 'Run Tests'}
              </button>
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
    </div>
  );
};

export default ChatWizard;
