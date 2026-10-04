import { useMe } from '@shopdesk/shared';

/** Placeholder until spec 06 builds the real billing screen. */
export function BillingPage() {
  const { user } = useMe();
  return (
    <section className="flex flex-col items-center justify-center gap-3 p-16 text-center">
      <h1 className="text-3xl font-bold">Ready to bill, {user.full_name.split(' ')[0]}</h1>
      <p className="max-w-md text-text-muted">
        The billing screen (customer name, product code + quantity, discount, confirm/reject)
        arrives in spec 06.
      </p>
    </section>
  );
}
