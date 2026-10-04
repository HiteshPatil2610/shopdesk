import { useApi, type Role, type UserPublic } from '@shopdesk/shared';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type NewUser = { username: string; full_name: string; role: Role; password: string };
export type AdminUser = UserPublic & {
  clerk_user_id: string;
  created_at: string | null;
  updated_at: string | null;
};

const KEY = ['users'];

export function useUsers() {
  const api = useApi();
  return useQuery({
    queryKey: KEY,
    queryFn: async () => (await api.get<{ items: AdminUser[] }>('/api/users')).data.items,
  });
}

function useInvalidate() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: KEY });
}

export function useCreateUser() {
  const api = useApi();
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (data: NewUser) => (await api.post('/api/users', data)).data,
    onSuccess: invalidate,
  });
}

export function useUpdateUser() {
  const api = useApi();
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async ({ id, ...data }: { id: number; role?: Role; full_name?: string }) =>
      (await api.patch(`/api/users/${id}`, data)).data,
    onSuccess: invalidate,
  });
}

export function useSetActive() {
  const api = useApi();
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async ({ id, active }: { id: number; active: boolean }) =>
      (await api.post(`/api/users/${id}/${active ? 'unban' : 'ban'}`)).data,
    onSuccess: invalidate,
  });
}

export function useResetPassword() {
  const api = useApi();
  return useMutation({
    mutationFn: async ({ id, new_password }: { id: number; new_password: string }) =>
      api.post(`/api/users/${id}/reset-password`, { new_password }),
  });
}
