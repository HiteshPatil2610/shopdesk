import { zodResolver } from '@hookform/resolvers/zod';
import { apiErrorMessage, Button } from '@shopdesk/shared';
import { useState } from 'react';
import { FormProvider, useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router';

import { useCreateProduct } from '../features/products/api';
import { ImagePicker } from '../features/products/ImagePicker';
import { formToCreate } from '../features/products/mapping';
import { PriceSection } from '../features/products/PriceSection';
import { ProductFields } from '../features/products/ProductFields';
import {
  emptyProductForm,
  productFormSchema,
  type ProductFormValues,
} from '../features/products/schema';

export function ProductNewPage() {
  const navigate = useNavigate();
  const create = useCreateProduct();
  const [image, setImage] = useState<Blob | null>(null);
  const form = useForm<ProductFormValues>({
    resolver: zodResolver(productFormSchema),
    defaultValues: emptyProductForm,
  });

  const onSubmit = form.handleSubmit(async (values) => {
    const product = await create.mutateAsync(formToCreate(values, image));
    navigate(`/products/${product.id}`, { replace: true, state: { created: true } });
  });

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/products" className="text-sm text-primary">
            ← Products
          </Link>
          <h1 className="text-2xl font-bold">Add product</h1>
        </div>
      </div>

      <FormProvider {...form}>
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
          <div className="grid gap-6 rounded-xl border border-border bg-surface p-5 md:grid-cols-[220px_1fr]">
            <ImagePicker onChange={setImage} disabled={create.isPending} />
            <ProductFields mode="create" />
          </div>
          <div className="rounded-xl border border-border bg-surface p-5">
            <PriceSection />
          </div>

          {create.isError && (
            <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
              {apiErrorMessage(create.error)}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => navigate('/products')}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Saving…' : 'Save product'}
            </Button>
          </div>
        </form>
      </FormProvider>
    </section>
  );
}
