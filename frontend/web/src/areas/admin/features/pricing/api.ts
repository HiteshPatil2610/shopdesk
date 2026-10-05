import { useApi, type PricingPreview, type PricingSettings } from '@shopdesk/shared';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type ApplyResult = {
  affected: number;
  applied: boolean;
  sample: { id: number; code: string; name: string; changes: Record<string, [string, string]> }[];
};

export function usePricingSettings() {
  const api = useApi();
  return useQuery({
    queryKey: ['pricing-settings'],
    queryFn: async () =>
      (await api.get<{ settings: PricingSettings }>('/pricing/settings')).data.settings,
  });
}

export function useSavePricingSettings() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (settings: PricingSettings) =>
      (await api.put<{ settings: PricingSettings }>('/pricing/settings', settings)).data.settings,
    onSuccess: (settings) => {
      qc.setQueryData(['pricing-settings'], settings);
      void qc.invalidateQueries({ queryKey: ['pricing-preview'] });
    },
  });
}

export function useApplyPricing() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (dryRun: boolean) =>
      (await api.post<ApplyResult>('/pricing/apply', { dry_run: dryRun })).data,
    onSuccess: (result) => {
      if (result.applied) void qc.invalidateQueries({ queryKey: ['products'] });
    },
  });
}

/** Example costs priced with UNSAVED settings, so the admin sees the effect before saving. */
export function useExamples(costs: string[], settings: PricingSettings | null) {
  const api = useApi();
  return useQuery({
    queryKey: ['pricing-examples', costs, settings],
    enabled: settings !== null,
    placeholderData: keepPreviousData,
    queryFn: async () =>
      Promise.all(
        costs.map(
          async (cost) =>
            (
              await api.post<PricingPreview>('/pricing/preview', {
                cost_price: cost,
                settings,
              })
            ).data,
        ),
      ),
  });
}
