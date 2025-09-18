import React from 'react';
import { Shield, AlertTriangle, Info, X } from 'lucide-react';
import clsx from 'clsx';

interface GuardrailsBlockingInfo {
  blocked: boolean;
  mode: 'hard_gate' | 'mixed' | 'advisory';
  blocking_categories: string[];
  blocking_reasons: string[];
  advisory_categories: string[];
}

interface GuardrailsBlockingBannerProps {
  blockingInfo: GuardrailsBlockingInfo;
  onDismiss?: () => void;
  className?: string;
}

const GuardrailsBlockingBanner: React.FC<GuardrailsBlockingBannerProps> = ({
  blockingInfo,
  onDismiss,
  className
}) => {
  const { blocked, mode, blocking_categories, blocking_reasons, advisory_categories } = blockingInfo;

  // Don't render if no blocking or advisory issues
  if (!blocked && advisory_categories.length === 0) {
    return null;
  }

  const isBlocked = blocked;
  const hasAdvisory = advisory_categories.length > 0;

  // Determine banner style based on severity
  const bannerClasses = clsx(
    "rounded-lg border p-4 mb-4 relative",
    {
      // Blocked (critical)
      "bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800": isBlocked,
      // Advisory only (warning)
      "bg-amber-50 border-amber-200 dark:bg-amber-900/20 dark:border-amber-800": !isBlocked && hasAdvisory,
    },
    className
  );

  const iconClasses = clsx(
    "flex-shrink-0 w-5 h-5",
    {
      "text-red-600 dark:text-red-400": isBlocked,
      "text-amber-600 dark:text-amber-400": !isBlocked && hasAdvisory,
    }
  );

  const titleClasses = clsx(
    "font-semibold text-sm",
    {
      "text-red-800 dark:text-red-200": isBlocked,
      "text-amber-800 dark:text-amber-200": !isBlocked && hasAdvisory,
    }
  );

  const textClasses = clsx(
    "text-sm mt-1",
    {
      "text-red-700 dark:text-red-300": isBlocked,
      "text-amber-700 dark:text-amber-300": !isBlocked && hasAdvisory,
    }
  );

  const formatCategoryName = (category: string) => {
    return category
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const getModeDescription = (mode: string) => {
    switch (mode) {
      case 'hard_gate':
        return 'Hard Gate mode blocks all tests when any guardrail fails';
      case 'mixed':
        return 'Mixed mode blocks tests only for critical categories (PII, Jailbreak, Self-harm, Adult content)';
      case 'advisory':
        return 'Advisory mode provides warnings but does not block execution';
      default:
        return '';
    }
  };

  return (
    <div className={bannerClasses}>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="absolute top-2 right-2 p-1 rounded-full hover:bg-black/5 dark:hover:bg-white/5"
          aria-label="Dismiss"
        >
          <X className="w-4 h-4" />
        </button>
      )}
      
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">
          {isBlocked ? (
            <AlertTriangle className={iconClasses} />
          ) : (
            <Info className={iconClasses} />
          )}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className={titleClasses}>
            <Shield className="inline w-4 h-4 mr-1" />
            {isBlocked ? 'Tests Blocked by Guardrails' : 'Guardrails Advisory'}
          </div>
          
          <div className={textClasses}>
            <p className="mb-2">
              {getModeDescription(mode)}
            </p>
            
            {isBlocked && (
              <div className="mb-2">
                <p className="font-medium mb-1">Blocking Categories:</p>
                <div className="flex flex-wrap gap-1">
                  {blocking_categories.map((category, index) => (
                    <span
                      key={index}
                      className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                    >
                      {formatCategoryName(category)}
                    </span>
                  ))}
                </div>
              </div>
            )}
            
            {hasAdvisory && (
              <div className="mb-2">
                <p className="font-medium mb-1">
                  {isBlocked ? 'Additional Advisory Categories:' : 'Advisory Categories:'}
                </p>
                <div className="flex flex-wrap gap-1">
                  {advisory_categories.map((category, index) => (
                    <span
                      key={index}
                      className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300"
                    >
                      {formatCategoryName(category)}
                    </span>
                  ))}
                </div>
              </div>
            )}
            
            {blocking_reasons.length > 0 && (
              <div>
                <p className="font-medium mb-1">Reasons:</p>
                <ul className="list-disc list-inside space-y-1">
                  {blocking_reasons.map((reason, index) => (
                    <li key={index} className="text-xs">
                      {reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            {isBlocked && (
              <div className="mt-3 p-2 rounded bg-red-100 dark:bg-red-900/30">
                <p className="text-xs font-medium">
                  ⚠️ Test execution has been prevented. Please review and adjust your guardrails configuration or model setup before proceeding.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default GuardrailsBlockingBanner;
