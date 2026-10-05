import { useApi } from '@shopdesk/shared';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type AuditEntry = {
  id: number;
  occurred_at: string;
  actor_user_id: number | null;
  actor_username: string;
  source: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  summary: string;
  changes: Record<string, unknown[]> | null;
  metadata: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
};

export function useAudit(params: Record<string, string>) {
  const api = useApi();
  return useQuery({
    queryKey: ['audit', params],
    placeholderData: keepPreviousData,
    queryFn: async () =>
      (
        await api.get<{ items: AuditEntry[]; total: number; page: number; page_size: number }>(
          '/audit-logs',
          { params },
        )
      ).data,
  });
}

export function useExportAudit() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (params: Record<string, string>) => {
      const response = await api.get<Blob>('/audit-logs/export.csv', {
        params,
        responseType: 'blob',
        timeout: 120000,
      });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'shopdesk-audit.csv';
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['audit'] }),
  });
}
