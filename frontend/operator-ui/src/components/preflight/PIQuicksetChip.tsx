/**
 * PI Quickset Chip component for showing quickset status and reuse information
 */

import React from 'react';
import { Shield, RefreshCw, AlertTriangle } from 'lucide-react';
import clsx from 'clsx';

interface PIQuicksetData {
  asr: number;
  total: number;
  success: number;
  ambiguous: number;
  families_used: string[];
  version: string;
  hash: string;
  reused?: boolean;
}

interface PIQuicksetChipProps {
  data: PIQuicksetData;
  className?: string;
}

export default function PIQuicksetChip({ data, className = "" }: PIQuicksetChipProps) {
  const { asr, total, success, families_used, reused } = data;
  
  const chipClasses = clsx(
    "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors",
    {
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300": asr < 0.05,
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300": asr >= 0.05 && asr < 0.2,
      "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300": asr >= 0.2,
    },
    className
  );
  
  const StatusIcon = reused ? RefreshCw : Shield;
  
  return (
    <div 
      className={chipClasses}
      title={`PI Quickset: ${(asr * 100).toFixed(1)}% ASR (${success}/${total}) - Families: ${families_used.join(', ')}`}
    >
      <StatusIcon size={12} className="flex-shrink-0" />
      
      <span>
        PI: {(asr * 100).toFixed(1)}% ASR
      </span>
      
      <span className="text-gray-500 dark:text-gray-400">
        ({success}/{total})
      </span>
      
      {reused && (
        <span className="text-xs bg-blue-200 dark:bg-blue-800 px-1 rounded">
          Reused
        </span>
      )}
    </div>
  );
}

/**
 * PI Quickset Unavailable Chip - shows when quickset is not available
 */
interface PIQuicksetUnavailableChipProps {
  className?: string;
}

export function PIQuicksetUnavailableChip({ className = "" }: PIQuicksetUnavailableChipProps) {
  return (
    <div className={clsx(
      "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
      "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
      className
    )}>
      <AlertTriangle size={12} className="flex-shrink-0" />
      <span>PI Quickset Unavailable</span>
    </div>
  );
}

/**
 * Helper function to create PI quickset data from test results
 */
export function createPIQuicksetData(testResult: any): PIQuicksetData | null {
  const piDetails = testResult?.details?.pi_quickset;
  if (!piDetails) return null;
  
  return {
    asr: piDetails.asr || 0,
    total: piDetails.total || 0,
    success: piDetails.success || 0,
    ambiguous: piDetails.ambiguous || 0,
    families_used: piDetails.families_used || [],
    version: piDetails.version || 'unknown',
    hash: piDetails.hash || 'unknown',
    reused: testResult?.reused_from_preflight || false
  };
}