import React from 'react';
import { motion } from 'framer-motion';
import { Play, Clock, DollarSign, CheckCircle2, XCircle, Settings } from 'lucide-react';
import { usePreflightStore } from '../../stores/preflightStore';

interface BottomRunBarProps {
  onRunTests: () => void;
  isRunning?: boolean;
  selectedTests?: Record<string, string[]>;
  preflightRunning?: boolean;
  preflightResult?: any;
}

export default function BottomRunBar({ onRunTests, isRunning = false }: BottomRunBarProps) {
  const { 
    estimated, dryRun, setDryRun, connection, profile, 
    rules, llmType, targetMode 
  } = usePreflightStore();

  const enabledRulesCount = Object.values(rules).filter(rule => rule.enabled).length;
  const connectionStatus = connection?.status || 'idle';
  
  const getConnectionIcon = () => {
    switch (connectionStatus) {
      case 'ok': return <CheckCircle2 className="w-4 h-4 text-green-400" />;
      case 'error': return <XCircle className="w-4 h-4 text-red-400" />;
      default: return <div className="w-4 h-4 bg-gray-500 rounded-full" />;
    }
  };

  const getConnectionColor = () => {
    switch (connectionStatus) {
      case 'ok': return 'text-green-400';
      case 'error': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const formatDuration = (ms: number) => {
    const minutes = Math.floor(ms / 60000);
    const seconds = Math.floor((ms % 60000) / 1000);
    return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
  };

  const isReadyToRun = llmType && targetMode && enabledRulesCount > 0;

  return (
    <motion.div
      initial={{ y: 100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}
      className="fixed bottom-0 left-0 right-0 z-30 bg-[#0B0D12]/95 backdrop-blur-md border-t border-gray-700"
    >
      <div className="max-w-[1120px] mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Left side - Test info */}
          <div className="flex items-center gap-6">
            {/* Test count */}
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-purple-400 rounded-full" />
              <span className="text-sm text-gray-300">
                <span className="font-medium text-white">{estimated.tests}</span> tests selected
              </span>
            </div>
            
            {/* Duration estimate */}
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <Clock className="w-4 h-4" />
              <span>~{formatDuration(estimated.p95ms)}</span>
            </div>
            
            {/* Cost estimate */}
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <DollarSign className="w-4 h-4" />
              <span>${estimated.costUsd.toFixed(3)} total</span>
            </div>
            
            {/* Connection status */}
            <div className="flex items-center gap-2">
              {getConnectionIcon()}
              <span className={`text-sm ${getConnectionColor()}`}>
                {connectionStatus === 'ok' ? 'Connected' : 
                 connectionStatus === 'error' ? 'Disconnected' : 'Not connected'}
              </span>
            </div>
          </div>

          {/* Right side - Controls */}
          <div className="flex items-center gap-4">
            {/* Active profile indicator */}
            <div className="flex items-center gap-2 px-3 py-1 bg-gray-800/50 border border-gray-700 rounded-lg">
              <Settings className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-300 capitalize">{profile}</span>
            </div>
            
            {/* Dry run toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                className="sr-only peer"
              />
              <div className="relative w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
              <span className="text-sm text-gray-300">Plan Only</span>
            </label>
            
            {/* Run button */}
            <motion.button
              whileHover={{ scale: isReadyToRun ? 1.02 : 1 }}
              whileTap={{ scale: isReadyToRun ? 0.98 : 1 }}
              onClick={onRunTests}
              disabled={!isReadyToRun || isRunning}
              className={`
                flex items-center gap-3 px-6 py-3 rounded-xl font-semibold transition-all duration-200 min-h-[44px]
                ${isReadyToRun && !isRunning
                  ? 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white shadow-lg'
                  : 'bg-gray-600 text-gray-400 cursor-not-allowed'
                }
              `}
            >
              {isRunning ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Running Tests...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  {dryRun ? 'Plan Tests' : 'Run Tests'}
                </>
              )}
            </motion.button>
          </div>
        </div>

        {/* Warning for missing requirements */}
        {!isReadyToRun && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            transition={{ duration: 0.28 }}
            className="mt-3 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg"
          >
            <div className="flex items-start gap-2">
              <div className="w-4 h-4 bg-yellow-500 rounded-full flex-shrink-0 mt-0.5" />
              <div className="text-sm">
                <span className="text-yellow-300 font-medium">Setup required:</span>
                <span className="text-yellow-200/80 ml-2">
                  {!llmType && 'Select LLM type'}
                  {llmType && !targetMode && 'Configure connection'}
                  {llmType && targetMode && enabledRulesCount === 0 && 'Enable at least one guardrail'}
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}
