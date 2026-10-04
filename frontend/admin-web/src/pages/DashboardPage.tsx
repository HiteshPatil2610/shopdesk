import { HealthBadge, useApi, useMe, type HealthResponse } from '@shopdesk/shared';
import { useQuery } from '@tanstack/react-query';

export function DashboardPage() {
  const { user } = useMe();
  const api = useApi();
  const health = useQuery({
    queryKey: ['health'],
    queryFn: async () =>
      (
        await api.get<HealthResponse>('/api/health', {
          validateStatus: (s) => s === 200 || s === 503,
        })
      ).data,
  });

  return (
    <section className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">Welcome, {user.full_name.split(' ')[0]}</h1>
        <p className="text-text-muted">
          Sales, profit and low-stock alerts will appear here (spec 08).
        </p>
      </div>
      <div>
        <HealthBadge isLoading={health.isLoading} isError={health.isError} data={health.data} />
      </div>
    </section>
  );
}
