/**
 * Provider Availability Chip component for showing guardrail provider status
 */

import React from 'react';
import { CheckCircle, XCircle, AlertTriangle, Info } from 'lucide-react';
import clsx from 'clsx';

interface ProviderHealth {
  id: string;
  available: boolean;
  version?: string;
  missing_deps?: string[];
  category: string;
}

interface ProviderAvailabilityChipProps {
  provider: ProviderHealth;
  className?: string;
  showVersion?: boolean;
  size?: 'sm' | 'md';
}

export default function ProviderAvailabilityChip({ 
  provider, 
  className = "", 
  showVersion = false,
  size = 'sm'
}: ProviderAvailabilityChipProps) {
  const { id, available, version, missing_deps = [], category } = provider;
  
  const chipClasses = clsx(
    "inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium transition-colors",
    {
      // Size variants
      "px-2 py-1 text-xs": size === 'sm',
      "px-3 py-1.5 text-sm": size === 'md',
      
      // Status-based styling
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300": available,
      "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300": !available,
    },
    className
  );
  
  const StatusIcon = available ? CheckCircle : XCircle;
  const iconSize = size === 'sm' ? 12 : 14;
  
  // Format provider name for display
  const displayName = id.split('.').pop() || id;
  
  // Create tooltip content
  const tooltipContent = [
    `Provider: ${id}`,
    `Category: ${category}`,
    `Status: ${available ? 'Available' : 'Unavailable'}`,
    version && `Version: ${version}`,
    missing_deps.length > 0 && `Missing: ${missing_deps.join(', ')}`
  ].filter(Boolean).join('\n');
  
  return (
    <div className={chipClasses} title={tooltipContent}>
      <StatusIcon size={iconSize} className="flex-shrink-0" />
      
      <span className="capitalize">
        {displayName}
      </span>
      
      {showVersion && version && (
        <span className="text-gray-500 dark:text-gray-400 text-xs">
          v{version}
        </span>
      )}
      
      {!available && missing_deps.length > 0 && (
        <AlertTriangle 
          size={iconSize} 
          className="flex-shrink-0 text-yellow-600 dark:text-yellow-400" 
          title={`Missing dependencies: ${missing_deps.join(', ')}`}
        />
      )}
    </div>
  );
}

/**
 * Category Availability Chip - shows overall status for a category
 */
interface CategoryAvailabilityChipProps {
  category: string;
  available: boolean;
  totalProviders: number;
  availableProviders: number;
  className?: string;
}

export function CategoryAvailabilityChip({ 
  category, 
  available, 
  totalProviders, 
  availableProviders,
  className = ""
}: CategoryAvailabilityChipProps) {
  const chipClasses = clsx(
    "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors",
    {
      "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300": available,
      "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300": !available,
      "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300": available && availableProviders < totalProviders,
    },
    className
  );
  
  const StatusIcon = available ? CheckCircle : XCircle;
  
  return (
    <div 
      className={chipClasses} 
      title={`${category}: ${availableProviders}/${totalProviders} providers available`}
    >
      <StatusIcon size={12} className="flex-shrink-0" />
      
      <span className="capitalize">
        {category}
      </span>
      
      <span className="text-gray-500 dark:text-gray-400">
        {availableProviders}/{totalProviders}
      </span>
    </div>
  );
}

/**
 * Provider Unavailable Warning - shows when no providers are available
 */
interface ProviderUnavailableWarningProps {
  category: string;
  className?: string;
}

export function ProviderUnavailableWarning({ 
  category, 
  className = "" 
}: ProviderUnavailableWarningProps) {
  return (
    <div className={clsx(
      "inline-flex items-center gap-2 px-3 py-2 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg text-sm text-yellow-800 dark:text-yellow-200",
      className
    )}>
      <AlertTriangle size={16} className="flex-shrink-0" />
      <span>
        No {category} providers available - checks will be skipped
      </span>
    </div>
  );
}
