import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Database, Bot, MessageSquare, Wrench, Sparkles, Info } from 'lucide-react';
import { LlmType } from '../../types/preflight';
import { usePreflightStore } from '../../stores/preflightStore';

const LLM_TYPES = [
  {
    type: 'rag' as LlmType,
    icon: Database,
    title: 'RAG',
    description: 'Retrieval-Augmented Generation with knowledge base',
    color: 'from-blue-500 to-cyan-500'
  },
  {
    type: 'agent' as LlmType,
    icon: Bot,
    title: 'Agent (A2A)',
    description: 'Autonomous agent with tool calling capabilities',
    color: 'from-purple-500 to-pink-500'
  },
  {
    type: 'plain' as LlmType,
    icon: MessageSquare,
    title: 'Plain',
    description: 'Standard LLM without external tools or data',
    color: 'from-green-500 to-emerald-500'
  },
  {
    type: 'tools' as LlmType,
    icon: Wrench,
    title: 'Tools/Function',
    description: 'Function calling and tool integration',
    color: 'from-orange-500 to-red-500'
  }
];

export default function StepLLMType() {
  const { llmType, setLlmType } = usePreflightStore();
  const [autoDetectResult, setAutoDetectResult] = useState<{
    suggested: LlmType;
    confidence: number;
    reasoning: string;
  } | null>(null);

  const handleAutoDetect = () => {
    // Simulate auto-detection logic
    // In real implementation, this would analyze available signals
    const suggestions = [
      { type: 'rag' as LlmType, confidence: 0.85, reasoning: 'Detected knowledge base and retrieval patterns' },
      { type: 'tools' as LlmType, confidence: 0.72, reasoning: 'Found tool schema and MCP manifest' },
      { type: 'agent' as LlmType, confidence: 0.68, reasoning: 'Identified agentic trace patterns' },
      { type: 'plain' as LlmType, confidence: 0.45, reasoning: 'No specific patterns detected' }
    ];
    
    const bestSuggestion = suggestions[Math.floor(Math.random() * suggestions.length)];
    setAutoDetectResult({
      suggested: bestSuggestion.type,
      confidence: bestSuggestion.confidence,
      reasoning: bestSuggestion.reasoning
    });
  };

  const handleTypeSelect = (type: LlmType) => {
    setLlmType(type);
    setAutoDetectResult(null);
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
        <h2 className="text-2xl font-bold text-white mb-2">Select LLM Type</h2>
        <p className="text-gray-400">Choose the type that best matches your LLM implementation</p>
      </div>

      {/* Auto-detect option */}
      <div className="flex justify-center">
        <button
          onClick={handleAutoDetect}
          className="inline-flex items-center gap-2 px-4 py-2 border border-gray-600 rounded-lg text-gray-300 hover:text-white hover:border-gray-500 transition-colors duration-200 min-h-[44px]"
        >
          <Sparkles className="w-4 h-4" />
          Auto (detect & suggest)
        </button>
      </div>

      {/* Auto-detect result */}
      {autoDetectResult && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          transition={{ duration: 0.28 }}
          className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4"
        >
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="text-blue-300 font-medium mb-1">
                We recommend {autoDetectResult.suggested.toUpperCase()} 
                <span className="text-sm text-blue-400 ml-2">
                  ({Math.round(autoDetectResult.confidence * 100)}% confidence)
                </span>
              </h3>
              <p className="text-sm text-blue-200/80 mb-3">{autoDetectResult.reasoning}</p>
              <div className="flex gap-2">
                <button
                  onClick={() => handleTypeSelect(autoDetectResult.suggested)}
                  className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded transition-colors duration-200"
                >
                  Use Recommendation
                </button>
                <button
                  onClick={() => setAutoDetectResult(null)}
                  className="px-3 py-1 border border-blue-500/50 text-blue-300 text-sm rounded hover:bg-blue-500/10 transition-colors duration-200"
                >
                  Choose Manually
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {/* Type selection chips */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {LLM_TYPES.map((typeOption, index) => {
          const Icon = typeOption.icon;
          const isSelected = llmType === typeOption.type;
          
          return (
            <motion.button
              key={typeOption.type}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1, duration: 0.28 }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => handleTypeSelect(typeOption.type)}
              className={`
                relative p-6 rounded-xl border-2 transition-all duration-200 text-left min-h-[44px]
                ${isSelected 
                  ? 'border-purple-500 bg-purple-500/10 shadow-lg shadow-purple-500/20' 
                  : 'border-gray-700 bg-gray-800/50 hover:border-gray-600 hover:bg-gray-800/70'
                }
              `}
            >
              {/* Selection indicator */}
              {isSelected && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="absolute top-3 right-3 w-3 h-3 bg-purple-500 rounded-full"
                />
              )}
              
              {/* Icon with gradient */}
              <div className={`
                inline-flex items-center justify-center w-12 h-12 rounded-lg mb-4
                bg-gradient-to-br ${typeOption.color} bg-opacity-20
              `}>
                <Icon className="w-6 h-6 text-white" />
              </div>
              
              {/* Content */}
              <h3 className="text-lg font-semibold text-white mb-2">
                {typeOption.title}
              </h3>
              <p className="text-sm text-gray-400 leading-relaxed">
                {typeOption.description}
              </p>
            </motion.button>
          );
        })}
      </div>

      {/* Selected type confirmation */}
      {llmType && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28 }}
          className="text-center"
        >
          <div className="inline-flex items-center gap-2 bg-green-500/10 border border-green-500/30 rounded-lg px-4 py-2">
            <div className="w-2 h-2 bg-green-400 rounded-full" />
            <span className="text-green-300 text-sm">
              Selected: {llmType.toUpperCase()}
            </span>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
