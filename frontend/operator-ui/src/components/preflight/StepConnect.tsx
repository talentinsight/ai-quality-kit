import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Globe, Zap, Eye, EyeOff, Settings, CheckCircle2, XCircle, Clock, ChevronDown } from 'lucide-react';
import { TargetMode } from '../../types/preflight';
import { usePreflightStore } from '../../stores/preflightStore';

export default function StepConnect() {
  const { 
    targetMode, setTargetMode, connection, setConnection,
    provider, setProvider, model, setModel 
  } = usePreflightStore();
  const [showDetails, setShowDetails] = useState(false);
  const [showToken, setShowToken] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState({
    endpoint: 'http://localhost:8000',
    token: '',
    timeout: '30000',
    headers: ''
  });

  const handleModeToggle = (mode: TargetMode) => {
    setTargetMode(mode);
    // Reset connection status when switching modes
    setConnection({ status: 'idle' });
  };

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const testConnection = async () => {
    if (!formData.endpoint.trim()) return;
    
    setIsConnecting(true);
    
    // Simulate connection test
    try {
      const startTime = Date.now();
      
      // Simulate API call delay
      await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 1000));
      
      const latencyMs = Date.now() - startTime;
      const success = Math.random() > 0.3; // 70% success rate for demo
      
      setConnection({
        endpoint: formData.endpoint,
        tokenMasked: !!formData.token,
        status: success ? 'ok' : 'error',
        latencyMs: success ? latencyMs : undefined
      });
    } catch (error) {
      setConnection({
        endpoint: formData.endpoint,
        tokenMasked: !!formData.token,
        status: 'error'
      });
    } finally {
      setIsConnecting(false);
    }
  };

  // Auto-test connection when endpoint changes (debounced)
  useEffect(() => {
    if (!formData.endpoint.trim()) return;
    
    const timer = setTimeout(() => {
      if (connection?.status === 'idle' || connection?.endpoint !== formData.endpoint) {
        testConnection();
      }
    }, 1500);
    
    return () => clearTimeout(timer);
  }, [formData.endpoint]);

  const getStatusIcon = () => {
    if (isConnecting) return <Clock className="w-4 h-4 text-yellow-400 animate-spin" />;
    if (connection?.status === 'ok') return <CheckCircle2 className="w-4 h-4 text-green-400" />;
    if (connection?.status === 'error') return <XCircle className="w-4 h-4 text-red-400" />;
    return <div className="w-4 h-4 bg-gray-500 rounded-full" />;
  };

  const getStatusText = () => {
    if (isConnecting) return 'Testing...';
    if (connection?.status === 'ok') return `Connected (${connection.latencyMs}ms)`;
    if (connection?.status === 'error') return 'Connection failed';
    return 'Not connected';
  };

  const getStatusColor = () => {
    if (isConnecting) return 'text-yellow-400';
    if (connection?.status === 'ok') return 'text-green-400';
    if (connection?.status === 'error') return 'text-red-400';
    return 'text-gray-400';
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}
      className="space-y-6"
    >
      {/* Header */}
      <div className="text-center">
        <h2 className="text-2xl font-bold text-white mb-2">Connect to LLM</h2>
        <p className="text-gray-400">Configure your API or MCP connection</p>
      </div>

      {/* Mode Toggle */}
      <div className="flex justify-center">
        <div className="inline-flex bg-gray-800 rounded-lg p-1 border border-gray-700">
          <button
            onClick={() => handleModeToggle('api')}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-md transition-all duration-200 min-h-[44px]
              ${targetMode === 'api' 
                ? 'bg-purple-600 text-white shadow-md' 
                : 'text-gray-400 hover:text-white'
              }
            `}
          >
            <Globe className="w-4 h-4" />
            API
          </button>
          <button
            onClick={() => handleModeToggle('mcp')}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-md transition-all duration-200 min-h-[44px]
              ${targetMode === 'mcp' 
                ? 'bg-purple-600 text-white shadow-md' 
                : 'text-gray-400 hover:text-white'
              }
            `}
          >
            <Zap className="w-4 h-4" />
            MCP
          </button>
        </div>
      </div>

      {/* Connection Form */}
      {targetMode && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          transition={{ duration: 0.28 }}
          className="bg-[#0F1117] border border-gray-700 rounded-xl p-6 space-y-4"
        >
          {/* Endpoint */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              {targetMode === 'api' ? 'API Endpoint' : 'MCP WebSocket URL'}
            </label>
            <input
              type="text"
              value={formData.endpoint}
              onChange={(e) => handleInputChange('endpoint', e.target.value)}
              placeholder={targetMode === 'api' ? 'http://localhost:8000' : 'ws://localhost:3000'}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none transition-colors duration-200"
            />
          </div>

          {/* Provider & Model - Only for API mode */}
          {targetMode === 'api' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Provider */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Provider
                </label>
                <select
                  value={provider || ''}
                  onChange={(e) => setProvider(e.target.value)}
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-purple-500 focus:outline-none transition-colors duration-200"
                >
                  <option value="">Select provider...</option>
                  <option value="openai">OpenAI (Real LLM)</option>
                  <option value="anthropic">Anthropic (Real LLM)</option>
                  <option value="gemini">Gemini (Real LLM)</option>
                  <option value="custom_rest">Custom REST (Real LLM)</option>
                  <option value="synthetic">Synthetic (Smart Test Data)</option>
                </select>
              </div>

              {/* Model */}
              {provider && (
                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.28 }}
                >
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Model
                  </label>
                  <input
                    type="text"
                    value={model || ''}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="gpt-4 / your-model"
                    className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none transition-colors duration-200"
                  />
                </motion.div>
              )}
            </div>
          )}

          {/* Provider Info */}
          {targetMode === 'api' && provider === 'synthetic' && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.28 }}
              className="bg-green-500/10 border border-green-500/30 rounded-lg p-4"
            >
              <div className="flex items-start gap-3">
                <div className="w-5 h-5 bg-green-500 rounded-full flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-green-300 font-medium mb-1">🤖 Synthetic Provider</h3>
                  <p className="text-sm text-green-200/80">
                    Using intelligent test data generation. Perfect for development, testing, and CI/CD. 
                    <strong> Note:</strong> This is NOT testing a real LLM - use OpenAI/Anthropic/Gemini for actual LLM evaluation.
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* MCP Info */}
          {targetMode === 'mcp' && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.28 }}
              className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4"
            >
              <div className="flex items-start gap-3">
                <div className="w-5 h-5 bg-blue-500 rounded-full flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-blue-300 font-medium mb-1">MCP Protocol</h3>
                  <p className="text-sm text-blue-200/80">
                    <strong>MCP selected:</strong> Provider/Model not required. MCP uses a standard protocol; no provider/model selection is needed.
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* Token */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Bearer Token
            </label>
            <div className="relative">
              <input
                type={showToken ? 'text' : 'password'}
                value={formData.token}
                onChange={(e) => handleInputChange('token', e.target.value)}
                placeholder="Enter your API token..."
                className="w-full px-4 py-3 pr-12 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none transition-colors duration-200"
              />
              <button
                type="button"
                onClick={() => setShowToken(!showToken)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors duration-200"
              >
                {showToken ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          {/* Connection Status */}
          <div className="flex items-center justify-between bg-gray-800/50 border border-gray-700 rounded-lg px-4 py-3">
            <div className="flex items-center gap-3">
              {getStatusIcon()}
              <span className={`text-sm font-medium ${getStatusColor()}`}>
                {getStatusText()}
              </span>
            </div>
            
            {!isConnecting && (
              <button
                onClick={testConnection}
                disabled={!formData.endpoint.trim()}
                className="px-3 py-1 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white text-sm rounded transition-colors duration-200"
              >
                Test
              </button>
            )}
          </div>

          {/* Show Details Toggle */}
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors duration-200"
          >
            <Settings className="w-4 h-4" />
            Show details
            <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${showDetails ? 'rotate-180' : ''}`} />
          </button>

          {/* Advanced Details */}
          {showDetails && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              transition={{ duration: 0.28 }}
              className="space-y-4 pt-4 border-t border-gray-700"
            >
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Timeout (ms)
                </label>
                <input
                  type="number"
                  value={formData.timeout}
                  onChange={(e) => handleInputChange('timeout', e.target.value)}
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white focus:border-purple-500 focus:outline-none transition-colors duration-200"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Custom Headers (JSON)
                </label>
                <textarea
                  value={formData.headers}
                  onChange={(e) => handleInputChange('headers', e.target.value)}
                  placeholder='{"X-Custom-Header": "value"}'
                  rows={3}
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:border-purple-500 focus:outline-none transition-colors duration-200 resize-none"
                />
              </div>
            </motion.div>
          )}
        </motion.div>
      )}

      {/* Connection Warning */}
      {targetMode && connection?.status !== 'ok' && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28 }}
          className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4"
        >
          <div className="flex items-start gap-3">
            <div className="w-5 h-5 bg-yellow-500 rounded-full flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-yellow-300 font-medium mb-1">Connection Not Verified</h3>
              <p className="text-sm text-yellow-200/80">
                You can continue without a connection, but some features may be limited. 
                We recommend testing your connection before proceeding.
              </p>
            </div>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
