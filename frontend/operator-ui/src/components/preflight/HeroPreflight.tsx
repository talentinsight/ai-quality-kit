import React from 'react';
import { motion } from 'framer-motion';
import { ShieldCheck, Rocket } from 'lucide-react';

interface HeroPreflightProps {
  onStart: () => void;
  isCollapsed?: boolean;
}

export default function HeroPreflight({ onStart, isCollapsed = false }: HeroPreflightProps) {
  if (isCollapsed) {
    return (
      <motion.div
        initial={{ height: 'auto' }}
        animate={{ height: 64 }}
        transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}
        className="sticky top-0 z-50 bg-white dark:bg-[#0B0D12] border-b border-slate-200 dark:border-gray-800"
      >
        <div className="max-w-[1120px] mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ShieldCheck className="w-6 h-6 text-purple-600 dark:text-purple-400" />
            <span className="text-lg font-semibold text-slate-900 dark:text-white">Guardrails Preflight</span>
          </div>
          <div className="text-sm text-slate-500 dark:text-gray-400">
            Privacy: no user data persisted by default
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}
      className="relative overflow-hidden bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-[#0B0D12] dark:via-[#0F1117] dark:to-[#0B0D12] border border-blue-200 dark:border-gray-800 rounded-xl shadow-lg"
    >
      {/* Background pattern */}
      <div className="absolute inset-0 opacity-5">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(139,92,246,0.1),transparent_50%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(45deg,transparent_25%,rgba(139,92,246,0.05)_25%,rgba(139,92,246,0.05)_50%,transparent_50%,transparent_75%,rgba(139,92,246,0.05)_75%)] bg-[length:20px_20px]" />
      </div>
      
      <div className="relative max-w-[1120px] mx-auto px-8 py-16">
        <div className="text-center max-w-4xl mx-auto">
          {/* Icon */}
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1, duration: 0.28 }}
            className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-purple-500/20 to-blue-500/20 rounded-2xl border border-purple-500/30 mb-8"
          >
            <ShieldCheck className="w-10 h-10 text-purple-600 dark:text-purple-400" />
          </motion.div>

          {/* Title */}
          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.28 }}
            className="text-4xl md:text-5xl font-bold text-slate-800 dark:text-white mb-6 leading-tight"
          >
            Ship safer LLMs — start with{' '}
            <span className="bg-gradient-to-r from-purple-600 to-blue-600 dark:from-purple-400 dark:to-blue-400 bg-clip-text text-transparent">
              Guardrails
            </span>
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.28 }}
            className="text-xl text-slate-700 dark:text-gray-300 mb-8 max-w-2xl mx-auto leading-relaxed"
          >
            Trust & verify your LLMs with comprehensive safety checks, performance monitoring, 
            and bias detection — all in one canvas.
          </motion.p>

          {/* Privacy notice */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.28 }}
            className="inline-flex items-center gap-2 bg-white/80 dark:bg-gray-800/50 border border-blue-200 dark:border-gray-700 rounded-lg px-4 py-2 mb-10 backdrop-blur-sm"
          >
            <div className="w-2 h-2 bg-green-500 dark:bg-green-400 rounded-full animate-pulse" />
            <span className="text-sm text-slate-700 dark:text-gray-400">
              Privacy: no user data persisted by default
            </span>
          </motion.div>

          {/* CTA Button */}
          <motion.button
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.28 }}
            whileHover={{ 
              scale: 1.02,
              boxShadow: '0 20px 25px -5px rgba(139, 92, 246, 0.3), 0 10px 10px -5px rgba(139, 92, 246, 0.1)'
            }}
            whileTap={{ scale: 0.98 }}
            onClick={onStart}
            className="group inline-flex items-center gap-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-semibold px-8 py-4 rounded-xl shadow-lg transition-all duration-200 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-white dark:focus:ring-offset-[#0B0D12]"
            aria-label="Start the Guardrails Preflight configuration process"
          >
            <Rocket className="w-5 h-5 group-hover:translate-x-0.5 transition-transform duration-200" aria-hidden="true" />
            Start Preflight
          </motion.button>

          {/* Features preview */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.28 }}
            className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6 max-w-3xl mx-auto"
          >
            {[
              { icon: '🛡️', title: 'PII & Safety', desc: 'Detect sensitive data leaks' },
              { icon: '⚡', title: 'Performance', desc: 'Monitor latency & costs' },
              { icon: '🎯', title: 'Bias Detection', desc: 'Ensure fair responses' }
            ].map((feature, index) => (
              <div
                key={feature.title}
                className="text-center p-4 rounded-lg bg-white/60 dark:bg-gray-800/30 border border-blue-200/50 dark:border-gray-700/50 backdrop-blur-sm"
              >
                <div className="text-2xl mb-2">{feature.icon}</div>
                <h3 className="text-slate-800 dark:text-white font-medium mb-1">{feature.title}</h3>
                <p className="text-sm text-slate-600 dark:text-gray-400">{feature.desc}</p>
              </div>
            ))}
          </motion.div>
        </div>
      </div>
    </motion.div>
  );
}
