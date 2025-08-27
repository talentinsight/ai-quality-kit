import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Sparkles, Settings } from 'lucide-react';
import { useWizardStore } from '../stores/wizardStore';
import { RunConfig } from '../types/runConfig';
import { mapRunConfigToRequest } from '../lib/api';

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

// Helper function for API calls
async function postJSON(url: string, body: unknown): Promise<Response> {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}

const ChatWizardV2: React.FC = () => {
  const { config, updateConfig, resetConfig } = useWizardStore();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      type: 'assistant',
      content: "Hi! I'm your AI Quality Kit assistant. Let's configure your testing setup together.\n\nFirst, are you testing an API endpoint or an MCP server?",
      timestamp: new Date()
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentField, setCurrentField] = useState<keyof RunConfig | null>('target_mode');
  const [isRunning, setIsRunning] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const addMessage = (type: 'user' | 'assistant', content: string) => {
    const newMessage: ChatMessage = {
      id: Date.now().toString(),
      type,
      content,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, newMessage]);
  };

  const getNextQuestion = (field: keyof RunConfig, value: any): { field: keyof RunConfig | null; question: string } => {
    switch (field) {
      case 'target_mode':
        if (value === 'api') {
          return {
            field: 'url',
            question: "Perfect! Now I need your API endpoint URL. What's your base URL? (e.g., http://localhost:8000)"
          };
        } else if (value === 'mcp') {
          return {
            field: 'url',
            question: "Great! MCP mode selected. What's your MCP server URL? (e.g., http://localhost:3000)"
          };
        }
        break;
      
      case 'url':
        return {
          field: 'bearer_token',
          question: "Excellent! Now I need your authentication token. What's your Bearer token?"
        };
      
      case 'bearer_token':
        if (config.target_mode === 'api') {
          return {
            field: 'provider',
            question: "Authentication set! Which provider are you using? (openai, anthropic, gemini, custom_rest, or mock)"
          };
        } else {
          return {
            field: 'test_suites',
            question: "Authentication configured! Since you're using MCP, no provider selection needed.\n\nWhich test suites would you like to run? (safety, mcp_security, red_team, performance)"
          };
        }
      
      case 'provider':
        return {
          field: 'model',
          question: "Great choice! What model would you like to use? (e.g., gpt-4, claude-3-sonnet, gemini-pro)"
        };
      
      case 'model':
        return {
          field: 'test_suites',
          question: "Perfect setup! Now, which test suites would you like to run?\n\nAvailable: rag_quality, red_team, safety, performance, regression, resilience"
        };
      
      case 'test_suites':
        return {
          field: null,
          question: "Excellent! Your configuration is ready. You can review it on the right and click 'Run Tests' when you're ready to start!"
        };
      
      default:
        return { field: null, question: "Configuration complete!" };
    }
    
    return { field: null, question: "Configuration complete!" };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isProcessing) return;

    const userInput = inputValue.trim();
    setInputValue('');
    setIsProcessing(true);

    // Add user message
    addMessage('user', userInput);

    // Process input based on current field
    setTimeout(() => {
      let updatedConfig: Partial<RunConfig> = {};
      let nextQuestion = '';

      if (currentField) {
        switch (currentField) {
          case 'target_mode':
            const mode = userInput.toLowerCase().includes('api') ? 'api' : 
                        userInput.toLowerCase().includes('mcp') ? 'mcp' : null;
            if (mode) {
              updatedConfig.target_mode = mode;
              // Clear URL when switching modes to avoid confusion
              updatedConfig.url = '';
            }
            break;
          
          case 'url':
            updatedConfig.url = userInput;
            break;
          
          case 'bearer_token':
            updatedConfig.bearer_token = userInput;
            break;
          
          case 'provider':
            const providers = ['openai', 'anthropic', 'gemini', 'custom_rest', 'mock'];
            const provider = providers.find(p => userInput.toLowerCase().includes(p));
            if (provider) {
              updatedConfig.provider = provider as any;
            }
            break;
          
          case 'model':
            updatedConfig.model = userInput;
            break;
          
          case 'test_suites':
            const availableSuites = ['rag_quality', 'red_team', 'safety', 'performance', 'regression', 'resilience', 'mcp_security'];
            const selectedSuites = availableSuites.filter(suite => 
              userInput.toLowerCase().includes(suite.replace('_', ' ')) || 
              userInput.toLowerCase().includes(suite)
            );
            if (selectedSuites.length > 0) {
              updatedConfig.test_suites = selectedSuites as any[];
            }
            break;
        }

        // Update config
        updateConfig(updatedConfig);

        // Get next question
        const next = getNextQuestion(currentField, updatedConfig[currentField]);
        setCurrentField(next.field);
        nextQuestion = next.question;
      }

      // Add assistant response
      addMessage('assistant', nextQuestion);
      setIsProcessing(false);
    }, 800);
  };

  const handleRunTests = async () => {
    if (!isConfigurationComplete() || isRunning) return;

    setIsRunning(true);
    setTestResult(null);

    try {
      // Map config to request format
      const request = mapRunConfigToRequest(config);
      
      // Get base URL from config - use server port 8000
      const baseUrl = config.url && config.url.trim() ? config.url : 'http://localhost:8000';
      
      // Make the request
      const response = await postJSON(`${baseUrl}/orchestrator/run_tests`, request);
      
      if (!response.ok) {
        throw new Error(`Test run failed: ${response.status} ${response.statusText}`);
      }
      
      const result = await response.json();
      setTestResult(result);
      
      // Add success message
      addMessage('assistant', `🎉 Tests completed successfully! Run ID: ${result.run_id}\n\nYou can view your reports using the buttons below.`);
      
    } catch (error: any) {
      console.error('Test run error:', error);
      addMessage('assistant', `❌ Test run failed: ${error.message || 'Unknown error'}\n\nPlease check your configuration and try again.`);
    } finally {
      setIsRunning(false);
    }
  };

  const handleReset = () => {
    resetConfig();
    setMessages([
      {
        id: '1',
        type: 'assistant',
        content: "Hi! I'm your AI Quality Kit assistant. Let's configure your testing setup together.\n\nFirst, are you testing an API endpoint or an MCP server?",
        timestamp: new Date()
      }
    ]);
    setCurrentField('target_mode');
    setTestResult(null);
  };

  // Check if configuration is complete for the selected mode
  const isConfigurationComplete = () => {
    if (!config.target_mode || !config.test_suites?.length) return false;
    
    // Common requirements
    if (!config.url?.trim() || !config.bearer_token?.trim()) return false;
    
    // API mode specific requirements
    if (config.target_mode === 'api') {
      if (!config.provider || !config.model) return false;
    }
    
    return true;
  };

  // Filter config to show only relevant fields based on target_mode
  const getFilteredConfig = () => {
    const filtered: any = { ...config };
    
    if (config.target_mode === 'mcp') {
      // For MCP mode, remove API-specific fields
      delete filtered.provider;
      delete filtered.model;
    } else if (config.target_mode === 'api') {
      // For API mode, all fields are relevant
      // No fields to remove
    } else {
      // If no target_mode selected, show minimal config
      return {
        target_mode: filtered.target_mode,
        test_suites: filtered.test_suites
      };
    }
    
    // Remove empty/null fields for cleaner display
    Object.keys(filtered).forEach(key => {
      if (filtered[key] === null || filtered[key] === '' || 
          (Array.isArray(filtered[key]) && filtered[key].length === 0) ||
          (typeof filtered[key] === 'object' && filtered[key] !== null && Object.keys(filtered[key]).length === 0)) {
        delete filtered[key];
      }
    });
    
    return filtered;
  };

  // Simple JSON syntax highlighter - no numbers to avoid conflicts
  const highlightJSON = (json: string) => {
    return json
      .replace(/"([^"]+)":/g, '<span style="color: #0066cc; font-weight: 500;">"$1"</span>:')        // Keys (blue)
      .replace(/:\s*"([^"]*)"/g, ': <span style="color: #009900;">"$1"</span>')                      // String values (green)
      .replace(/:\s*(true|false|null)\b/g, ': <span style="color: #cc6600;">$1</span>')             // Booleans/null (orange)
      .replace(/([{}[\],])/g, '<span style="color: #666; font-weight: bold;">$1</span>');           // Brackets (gray)
  };

  return (
    <div className="h-full flex bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
      {/* Chat Area */}
      <div className="flex-1 flex flex-col max-w-2xl">
        {/* Header */}
        <div className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm border-b border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">AI Quality Kit Assistant</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">Let's configure your tests together</p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((message, index) => (
            <div
              key={message.id}
              className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'} animate-in slide-in-from-bottom-2 duration-300`}
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <div className={`flex items-start space-x-3 max-w-[80%] ${
                message.type === 'user' ? 'flex-row-reverse space-x-reverse' : ''
              }`}>
                {/* Avatar */}
                <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                  message.type === 'user' 
                    ? 'bg-gradient-to-r from-blue-500 to-blue-600' 
                    : 'bg-gradient-to-r from-purple-500 to-pink-500'
                }`}>
                  {message.type === 'user' ? (
                    <User className="w-4 h-4 text-white" />
                  ) : (
                    <Bot className="w-4 h-4 text-white" />
                  )}
                </div>
                
                {/* Message */}
                <div className={`px-4 py-3 rounded-2xl shadow-sm ${
                  message.type === 'user'
                    ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white'
                    : 'bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-900 dark:text-white'
                }`}>
                  <div className="text-sm leading-relaxed whitespace-pre-wrap">
                    {message.content}
                  </div>
                  <div className={`text-xs mt-2 ${
                    message.type === 'user' ? 'text-blue-100' : 'text-gray-400 dark:text-gray-500'
                  }`}>
                    {message.timestamp.toLocaleTimeString([], { 
                      hour: '2-digit', 
                      minute: '2-digit' 
                    })}
                  </div>
                </div>
              </div>
            </div>
          ))}
          
          {isProcessing && (
            <div className="flex justify-start">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full flex items-center justify-center">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-2xl px-4 py-3">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm border-t border-gray-200 dark:border-gray-700 p-4">
          <form onSubmit={handleSubmit} className="flex space-x-3">
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Type your response..."
              disabled={isProcessing}
              className="flex-1 px-4 py-3 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 rounded-full focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!inputValue.trim() || isProcessing}
              className="w-12 h-12 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-full flex items-center justify-center hover:from-blue-600 hover:to-purple-700 hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
        </div>
      </div>

      {/* Config Preview */}
      <div className="w-96 bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm border-l border-gray-200 dark:border-gray-700 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center space-x-2">
            <Settings className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Configuration Preview</h3>
          </div>
        </div>

        {/* Config JSON */}
        <div className="flex-1 p-4 overflow-y-auto">
          <pre className="text-sm bg-gray-50 dark:bg-gray-900 rounded-lg p-4 overflow-x-auto transition-all duration-300 hover:bg-gray-100 dark:hover:bg-gray-800">
            <code 
              className="text-gray-800 transition-all duration-200"
              dangerouslySetInnerHTML={{
                __html: highlightJSON(JSON.stringify(getFilteredConfig(), null, 2))
              }}
            />
          </pre>
        </div>

        {/* Actions */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-700 space-y-3">
          <button
            onClick={handleRunTests}
            disabled={!isConfigurationComplete() || isRunning}
            className="w-full bg-gradient-to-r from-green-500 to-emerald-600 text-white py-3 px-4 rounded-lg font-medium hover:from-green-600 hover:to-emerald-700 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
          >
            {isRunning ? 'Running Tests...' : 'Run Tests'}
          </button>
          <button 
            onClick={handleReset}
            className="w-full bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 py-2 px-4 rounded-lg font-medium hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          >
            Reset Configuration
          </button>
          
          {/* Test Results */}
          {testResult && (
            <div className="mt-4 space-y-2">
              <div className="text-sm font-medium text-gray-700 dark:text-gray-300">Test Results:</div>
              <div className="space-y-1">
                <a
                  href={`${config.url || 'http://localhost:8000'}/orchestrator/report/${testResult.run_id}.json`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block w-full text-center bg-blue-50 text-blue-700 py-2 px-3 rounded text-sm hover:bg-blue-100 transition-colors"
                >
                  📄 JSON Report
                </a>
                <a
                  href={`${config.url || 'http://localhost:8000'}/orchestrator/report/${testResult.run_id}.xlsx`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block w-full text-center bg-green-50 text-green-700 py-2 px-3 rounded text-sm hover:bg-green-100 transition-colors"
                >
                  📊 Excel Report
                </a>
                <a
                  href={`${config.url || 'http://localhost:8000'}/orchestrator/report/${testResult.run_id}.html`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block w-full text-center bg-purple-50 text-purple-700 py-2 px-3 rounded text-sm hover:bg-purple-100 transition-colors"
                >
                  🎨 HTML Report
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatWizardV2;
