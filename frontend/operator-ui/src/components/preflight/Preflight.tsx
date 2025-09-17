import React, { useState } from 'react';
import { motion } from 'framer-motion';
import HeroPreflight from './HeroPreflight';
import PreflightWizard from './PreflightWizard';

interface PreflightProps {
  onRunTests: (config: any) => void;
}

export default function Preflight({ onRunTests }: PreflightProps) {
  const [hasStarted, setHasStarted] = useState(false);

  const handleStart = () => {
    setHasStarted(true);
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0B0D12]">
      {/* Hero Section */}
      <div className="relative">
        <HeroPreflight 
          onStart={handleStart} 
          isCollapsed={hasStarted}
        />
      </div>

      {/* Wizard Section */}
      {hasStarted && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
        >
          <PreflightWizard onRunTests={onRunTests} />
        </motion.div>
      )}
    </div>
  );
}
