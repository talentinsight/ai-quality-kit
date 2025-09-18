/**
 * Reusable chip component to indicate when a test is reusing signals from preflight
 */

import React from 'react';
import { Recycle } from 'lucide-react';
import clsx from 'clsx';

interface ReusedFromPreflightChipProps {
  reusedCount?: number;
  reusedCategories?: string[];
  size?: 'sm' | 'md';
  className?: string;
}

export default function ReusedFromPreflightChip({
  reusedCount = 0,
  reusedCategories = [],
  size = 'sm',
  className
}: ReusedFromPreflightChipProps) {
  if (reusedCount === 0) return null;

  const sizeClasses = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-3 py-1.5 text-sm'
  };

  const iconSizes = {
    sm: 12,
    md: 14
  };

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 rounded-full font-medium',
        sizeClasses[size],
        className
      )}
      title={`Reusing ${reusedCount} signal${reusedCount > 1 ? 's' : ''} from preflight${
        reusedCategories.length > 0 ? `: ${reusedCategories.join(', ')}` : ''
      }`}
    >
      <Recycle size={iconSizes[size]} />
      <span>Reused from Preflight</span>
      {reusedCount > 1 && (
        <span className="bg-emerald-200 dark:bg-emerald-800 text-emerald-800 dark:text-emerald-200 px-1.5 py-0.5 rounded-full text-xs font-bold">
          {reusedCount}
        </span>
      )}
    </span>
  );
}
