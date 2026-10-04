import { useApi, type Page, type PosProduct } from '@shopdesk/shared';
import { keepPreviousData, useQuery } from '@tanstack/react-query';

export function usePosProducts(search: string) {
  const api = useApi();
  return useQuery({
    queryKey: ['pos-products', search],
    queryFn: async () =>
      (
        await api.get<Page<PosProduct>>('/api/products', {
          params: { search: search || undefined, page_size: 100 },
        })
      ).data,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
}
