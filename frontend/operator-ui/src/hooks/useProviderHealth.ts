/**
 * Hook for fetching and managing provider health data
 */

import { useState, useEffect, useCallback } from 'react';

interface ProviderHealth {
  id: string;
  available: boolean;
  version?: string;
  missing_deps?: string[];
  category: string;
}

interface CategoryHealth {
  category: string;
  available: boolean;
  total_providers: number;
  available_providers: number;
  providers: ProviderHealth[];
}

interface UseProviderHealthReturn {
  providers: ProviderHealth[];
  providersByCategory: Record<string, ProviderHealth[]>;
  categoryHealth: Record<string, CategoryHealth>;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useProviderHealth(): UseProviderHealthReturn {
  const [providers, setProviders] = useState<ProviderHealth[]>([]);
  const [providersByCategory, setProvidersByCategory] = useState<Record<string, ProviderHealth[]>>({});
  const [categoryHealth, setCategoryHealth] = useState<Record<string, CategoryHealth>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProviderHealth = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Fetch all providers health
      const response = await fetch('/guardrails/health');
      if (!response.ok) {
        throw new Error(`Failed to fetch provider health: ${response.statusText}`);
      }

      const healthData: ProviderHealth[] = await response.json();
      setProviders(healthData);

      // Group by category
      const byCategory: Record<string, ProviderHealth[]> = {};
      const categoryHealthData: Record<string, CategoryHealth> = {};

      healthData.forEach(provider => {
        const category = provider.category;
        if (!byCategory[category]) {
          byCategory[category] = [];
        }
        byCategory[category].push(provider);
      });

      // Calculate category health
      Object.entries(byCategory).forEach(([category, categoryProviders]) => {
        const availableCount = categoryProviders.filter(p => p.available).length;
        categoryHealthData[category] = {
          category,
          available: availableCount > 0,
          total_providers: categoryProviders.length,
          available_providers: availableCount,
          providers: categoryProviders
        };
      });

      setProvidersByCategory(byCategory);
      setCategoryHealth(categoryHealthData);

    } catch (err) {
      console.error('Failed to fetch provider health:', err);
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProviderHealth();
  }, [fetchProviderHealth]);

  return {
    providers,
    providersByCategory,
    categoryHealth,
    isLoading,
    error,
    refetch: fetchProviderHealth
  };
}

/**
 * Hook for fetching health of a specific category
 */
export function useCategoryHealth(category: string) {
  const [categoryHealth, setCategoryHealth] = useState<CategoryHealth | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCategoryHealth = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`/guardrails/health/category/${category}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch category health: ${response.statusText}`);
      }

      const healthData: CategoryHealth = await response.json();
      setCategoryHealth(healthData);

    } catch (err) {
      console.error(`Failed to fetch health for category ${category}:`, err);
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    } finally {
      setIsLoading(false);
    }
  }, [category]);

  useEffect(() => {
    fetchCategoryHealth();
  }, [fetchCategoryHealth]);

  return {
    categoryHealth,
    isLoading,
    error,
    refetch: fetchCategoryHealth
  };
}
