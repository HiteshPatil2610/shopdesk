import { useMe } from '@shopdesk/shared';

import { ProductPanel } from '../features/products/ProductPanel';

/** Product list is live (spec 03); the cart, discount and confirm arrive in spec 06/07. */
export function BillingPage() {
  const { user } = useMe();
  return (
    <div className="grid h-[calc(100vh-57px)] grid-cols-1 md:grid-cols-[360px_1fr]">
      <ProductPanel />
      <section className="flex flex-col items-center justify-center gap-3 p-16 text-center">
        <h1 className="text-3xl font-bold">Ready to bill, {user.full_name.split(' ')[0]}</h1>
        <p className="max-w-md text-text-muted">
          Customer name, product code + quantity, discount and confirm/reject arrive in spec 06.
        </p>
      </section>
    </div>
  );
}
