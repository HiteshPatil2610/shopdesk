import {
  useApi,
  type Category,
  type MpMode,
  type Page,
  type PricingPreview,
  type Product,
} from '@shopdesk/shared';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type ProductQuery = {
  search?: string;
  category_id?: string;
  low_stock?: boolean;
  include_inactive?: boolean;
  sort?: string;
  page?: number;
  page_size?: number;
};

/** Fields sent on create (multipart). Prices are only sent when typed manually. */
export type ProductCreateInput = {
  name: string;
  category_id: string;
  unit: string;
  barcode: string;
  description: string;
  quantity: string;
  reorder_level: string;
  cost_price: string;
  mp_round_mode: MpMode;
  market_price?: string;
  selling_price?: string;
  image?: Blob | null;
};

export type ProductPatch = Record<string, unknown> & { version: number };

const PRODUCTS = ['products'];

function cleanParams(q: ProductQuery) {
  return Object.fromEntries(
    Object.entries(q).filter(([, v]) => v !== undefined && v !== '' && v !== false),
  );
}

export function useProducts(query: ProductQuery) {
  const api = useApi();
  return useQuery({
    queryKey: [...PRODUCTS, 'list', query],
    queryFn: async () =>
      (await api.get<Page<Product>>('/products', { params: cleanParams(query) })).data,
    placeholderData: keepPreviousData,
  });
}

export function useProduct(id: number) {
  const api = useApi();
  return useQuery({
    queryKey: [...PRODUCTS, 'detail', id],
    queryFn: async () => (await api.get<{ product: Product }>(`/products/${id}`)).data.product,
  });
}

function useProductMutation<TVars>(fn: (vars: TVars) => Promise<Product>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (product) => {
      qc.setQueryData([...PRODUCTS, 'detail', product.id], product);
      void qc.invalidateQueries({ queryKey: [...PRODUCTS, 'list'] });
    },
  });
}

export function useCreateProduct() {
  const api = useApi();
  return useProductMutation(async (input: ProductCreateInput) => {
    const form = new FormData();
    for (const [key, value] of Object.entries(input)) {
      if (key === 'image') continue;
      if (value !== undefined && value !== null) form.append(key, String(value));
    }
    if (input.image) form.append('image', input.image, 'photo.webp');
    return (await api.post<{ product: Product }>('/products', form)).data.product;
  });
}

export function useUpdateProduct(id: number) {
  const api = useApi();
  return useProductMutation(
    async (patch: ProductPatch) =>
      (await api.patch<{ product: Product }>(`/products/${id}`, patch)).data.product,
  );
}

export function useSetProductActive(id: number) {
  const api = useApi();
  return useProductMutation(
    async (active: boolean) =>
      (
        await api.post<{ product: Product }>(
          `/products/${id}/${active ? 'activate' : 'deactivate'}`,
        )
      ).data.product,
  );
}

export function useReplaceImage(id: number) {
  const api = useApi();
  return useProductMutation(async (image: Blob | null) => {
    if (!image) {
      return (await api.delete<{ product: Product }>(`/products/${id}/image`)).data.product;
    }
    const form = new FormData();
    form.append('image', image, 'photo.webp');
    return (await api.post<{ product: Product }>(`/products/${id}/image`, form)).data.product;
  });
}

export function useCategories() {
  const api = useApi();
  return useQuery({
    queryKey: ['categories'],
    queryFn: async () => (await api.get<{ items: Category[] }>('/categories')).data.items,
    staleTime: 5 * 60_000,
  });
}

export function useCreateCategory() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) =>
      (await api.post<{ category: Category }>('/categories', { name })).data.category,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }),
  });
}

/** Server-side MP/SP preview for a cost (and optional manual MP). Money is never computed here. */
export function usePricingPreview(args: {
  cost: string | null;
  mode: MpMode;
  manualMp: string | null;
}) {
  const api = useApi();
  return useQuery({
    queryKey: ['pricing-preview', args.cost, args.mode, args.manualMp],
    enabled: args.cost !== null,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    queryFn: async () =>
      (
        await api.post<PricingPreview>('/pricing/preview', {
          cost_price: args.cost,
          mp_round_mode: args.mode,
          market_price: args.manualMp ?? undefined,
        })
      ).data,
  });
}
