/**
 * ASR (Attack Success Rate) Display component for Red Team results
 */

import React from 'react';
import { TrendingUp, TrendingDown, AlertTriangle, Shield, Target, Clock } from 'lucide-react';
import clsx from 'clsx';

interface ASRMetrics {
  overall_asr: number;
  success_rate_percent: number;
  total_items: number;
  success_count: number;
  blocked_count: number;
  ambiguous_count: number;
}

interface FamilyMetric {
  family: string;
  asr: number;
  success_count: number;
  total_count: number;
}

interface PerformanceMetrics {
  avg_latency_ms: number;
  p95_latency_ms: number;
  estimated_cost: number;
  total_tokens: number;
}

interface ASRDisplayProps {
  metrics: ASRMetrics;
  topFailingFamilies: FamilyMetric[];
  performanceMetrics: PerformanceMetrics;
  reusedCount: number;
  executedCount: number;
  isLoading?: boolean;
  className?: string;
}

export default function ASRDisplay({
  metrics,
  topFailingFamilies,
  performanceMetrics,
  reusedCount,
  executedCount,
  isLoading = false,
  className = ""
}: ASRDisplayProps) {
  const getRiskLevel = (asr: number) => {
    if (asr >= 0.3) return 'high';
    if (asr >= 0.1) return 'medium';
    return 'low';
  };

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'high': return 'text-red-600 dark:text-red-400';
      case 'medium': return 'text-yellow-600 dark:text-yellow-400';
      default: return 'text-green-600 dark:text-green-400';
    }
  };

  const getRiskBgColor = (level: string) => {
    switch (level) {
      case 'high': return 'bg-red-100 dark:bg-red-900/30';
      case 'medium': return 'bg-yellow-100 dark:bg-yellow-900/30';
      default: return 'bg-green-100 dark:bg-green-900/30';
    }
  };

  const overallRiskLevel = getRiskLevel(metrics.overall_asr);

  if (isLoading) {
    return (
      <div className={clsx("bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6", className)}>
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
          <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
          <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className={clsx("bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700", className)}>
      <div className="p-6 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Attack Success Rate (ASR)
          </h3>
          
          <div className="flex items-center gap-2">
            {reusedCount > 0 && (
              <div className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                <Shield size={12} />
                {reusedCount} reused
              </div>
            )}
            
            <div className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300">
              <Target size={12} />
              {executedCount} executed
            </div>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Overall ASR */}
        <div className="text-center">
          <div className={clsx(
            "inline-flex items-center justify-center w-24 h-24 rounded-full text-3xl font-bold",
            getRiskBgColor(overallRiskLevel),
            getRiskColor(overallRiskLevel)
          )}>
            {(metrics.overall_asr * 100).toFixed(1)}%
          </div>
          
          <div className="mt-3 space-y-1">
            <div className="text-lg font-semibold text-gray-900 dark:text-white">
              Overall ASR
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              {metrics.success_count} successful attacks out of {metrics.total_items} total
            </div>
          </div>
        </div>

        {/* Breakdown */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {metrics.success_count}
            </div>
            <div className="text-sm text-red-700 dark:text-red-300">
              Successful
            </div>
          </div>
          
          <div className="text-center p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {metrics.blocked_count}
            </div>
            <div className="text-sm text-green-700 dark:text-green-300">
              Blocked
            </div>
          </div>
          
          <div className="text-center p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
            <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
              {metrics.ambiguous_count}
            </div>
            <div className="text-sm text-yellow-700 dark:text-yellow-300">
              Ambiguous
            </div>
          </div>
        </div>

        {/* Top Failing Families */}
        {topFailingFamilies.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <TrendingUp size={16} className="text-red-600 dark:text-red-400" />
              Top Failing Attack Families
            </h4>
            
            <div className="space-y-2">
              {topFailingFamilies.slice(0, 5).map((family, index) => {
                const familyRiskLevel = getRiskLevel(family.asr);
                
                return (
                  <div key={family.family} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-6 h-6 rounded-full bg-gray-200 dark:bg-gray-600 text-xs font-bold text-gray-600 dark:text-gray-400">
                        {index + 1}
                      </div>
                      
                      <div>
                        <div className="font-medium text-gray-900 dark:text-white">
                          {family.family.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {family.success_count}/{family.total_count} attacks succeeded
                        </div>
                      </div>
                    </div>
                    
                    <div className={clsx(
                      "px-2 py-1 rounded-full text-sm font-medium",
                      getRiskBgColor(familyRiskLevel),
                      getRiskColor(familyRiskLevel)
                    )}>
                      {(family.asr * 100).toFixed(1)}%
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Performance Metrics */}
        <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
            <Clock size={16} className="text-blue-600 dark:text-blue-400" />
            Performance Summary
          </h4>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">Avg Latency</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {performanceMetrics.avg_latency_ms.toFixed(0)}ms
                </span>
              </div>
              
              <div className="flex justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">P95 Latency</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {performanceMetrics.p95_latency_ms.toFixed(0)}ms
                </span>
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">Total Tokens</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {performanceMetrics.total_tokens.toLocaleString()}
                </span>
              </div>
              
              <div className="flex justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">Est. Cost</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  ${performanceMetrics.estimated_cost.toFixed(3)}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Risk Assessment */}
        <div className={clsx(
          "p-4 rounded-lg border-l-4",
          overallRiskLevel === 'high' ? 'bg-red-50 dark:bg-red-900/20 border-red-500' :
          overallRiskLevel === 'medium' ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-500' :
          'bg-green-50 dark:bg-green-900/20 border-green-500'
        )}>
          <div className="flex items-start gap-3">
            {overallRiskLevel === 'high' ? (
              <AlertTriangle size={20} className="text-red-600 dark:text-red-400 mt-0.5" />
            ) : overallRiskLevel === 'medium' ? (
              <AlertTriangle size={20} className="text-yellow-600 dark:text-yellow-400 mt-0.5" />
            ) : (
              <Shield size={20} className="text-green-600 dark:text-green-400 mt-0.5" />
            )}
            
            <div>
              <div className={clsx(
                "font-semibold",
                getRiskColor(overallRiskLevel)
              )}>
                {overallRiskLevel === 'high' ? 'High Risk' :
                 overallRiskLevel === 'medium' ? 'Medium Risk' :
                 'Low Risk'}
              </div>
              
              <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                {overallRiskLevel === 'high' ? 
                  'Significant vulnerabilities detected. Review failing attack families and strengthen defenses.' :
                 overallRiskLevel === 'medium' ?
                  'Some vulnerabilities present. Consider additional safeguards for failing attack types.' :
                  'Model demonstrates good resistance to adversarial attacks. Continue monitoring.'}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
