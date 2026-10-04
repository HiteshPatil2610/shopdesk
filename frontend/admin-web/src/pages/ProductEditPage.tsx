import { zodResolver } from '@hookform/resolvers/zod';
import {
  apiErrorCode,
  apiErrorMessage,
  Badge,
  Button,
  Modal,
  Spinner,
  type Product,
} from '@shopdesk/shared';
import { useEffect, useState } from 'react';
import { FormProvider, useForm } from 'react-hook-form';
import { Link, useLocation, useParams } from 'react-router';

import {
  useProduct,
  useReplaceImage,
  useSetProductActive,
  useUpdateProduct,
} from '../features/products/api';
import { ImagePicker } from '../features/products/ImagePicker';
import { formToPatch, productToForm } from '../features/products/mapping';
import { PriceSection } from '../features/products/PriceSection';
import { ProductFields } from '../features/products/ProductFields';
import { productFormSchema, type ProductFormValues } from '../features/products/schema';

export function ProductEditPage() {
  const id = Number(useParams().id);
  const location = useLocation();
  const product = useProduct(id);
  // Lives here, not in the form: a save bumps `version`, which remounts the form.
  const [saved, setSaved] = useState(
    Boolean((location.state as { created?: boolean } | null)?.created),
  );
  useEffect(() => {
    if (!saved) return;
    const t = window.setTimeout(() => setSaved(false), 3000);
    return () => window.clearTimeout(t);
  }, [saved]);

  if (product.isPending) {
    return (
      <div className="flex justify-center p-16">
        <Spinner label="Loading product" />
      </div>
    );
  }
  if (product.isError) {
    return (
      <div className="p-8 text-center">
        <p className="text-danger">{apiErrorMessage(product.error)}</p>
        <Link to="/products" className="text-primary">
          Back to products
        </Link>
      </div>
    );
  }
  return (
    <EditForm
      key={product.data.version}
      product={product.data}
      saved={saved}
      onSaved={() => setSaved(true)}
      reload={() => void product.refetch()}
    />
  );
}

type EditFormProps = {
  product: Product;
  saved: boolean;
  onSaved: () => void;
  reload: () => void;
};

function EditForm({ product, saved, onSaved, reload }: EditFormProps) {
  const update = useUpdateProduct(product.id);
  const setActive = useSetProductActive(product.id);
  const replaceImage = useReplaceImage(product.id);
  const form = useForm<ProductFormValues>({
    resolver: zodResolver(productFormSchema),
    defaultValues: productToForm(product),
  });

  const conflict = apiErrorCode(update.error) === 'VERSION_CONFLICT';

  const onSubmit = form.handleSubmit(async (values) => {
    await update.mutateAsync(formToPatch(values, product.version));
    onSaved();
  });

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link to="/products" className="text-sm text-primary">
            ← Products
          </Link>
          <h1 className="flex items-center gap-3 text-2xl font-bold">
            <span className="font-mono text-lg text-text-muted">{product.code}</span>
            {product.name}
            {!product.is_active && <Badge tone="danger">Inactive</Badge>}
          </h1>
          <p className="text-xs text-text-muted">
            Last changed{' '}
            {product.updated_at ? new Date(product.updated_at).toLocaleString('en-IN') : '—'}
            {product.updated_by && ` by ${product.updated_by}`}
          </p>
        </div>
        <Button
          variant={product.is_active ? 'danger' : 'secondary'}
          size="sm"
          disabled={setActive.isPending}
          onClick={() => setActive.mutate(!product.is_active)}
        >
          {product.is_active ? 'Deactivate' : 'Reactivate'}
        </Button>
      </div>

      {saved && (
        <p role="status" className="rounded-lg bg-success/10 px-3 py-2 text-sm text-success">
          ✓ Saved
        </p>
      )}

      <FormProvider {...form}>
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
          <div className="grid gap-6 rounded-xl border border-border bg-surface p-5 md:grid-cols-[220px_1fr]">
            <div className="flex flex-col gap-2">
              <ImagePicker
                currentUrl={product.image_url}
                disabled={replaceImage.isPending}
                onChange={(image) => replaceImage.mutate(image)}
              />
              {replaceImage.isPending && <p className="text-xs text-text-muted">Uploading…</p>}
              {replaceImage.isError && (
                <p className="text-xs text-danger">{apiErrorMessage(replaceImage.error)}</p>
              )}
            </div>
            <div className="flex flex-col gap-4">
              <ProductFields mode="edit" />
              <div className="flex items-center gap-3 rounded-lg bg-bg px-3 py-2 text-sm">
                <span>
                  In stock: <strong className="tabular-nums">{product.quantity}</strong>{' '}
                  {product.unit}
                </span>
                {product.low_stock && <Badge tone="warning">Low stock</Badge>}
                <span className="text-text-muted">
                  · Quantity changes go through stock adjustments (coming in spec 07)
                </span>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-border bg-surface p-5">
            <PriceSection />
          </div>

          {update.isError && !conflict && (
            <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
              {apiErrorMessage(update.error)}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => form.reset(productToForm(product))}>
              Undo changes
            </Button>
            <Button type="submit" disabled={update.isPending || !form.formState.isDirty}>
              {update.isPending ? 'Saving…' : 'Save changes'}
            </Button>
          </div>
        </form>
      </FormProvider>

      <Modal
        open={conflict}
        title="Someone else changed this product"
        onClose={() => update.reset()}
        size="sm"
        footer={
          <Button
            onClick={() => {
              update.reset();
              reload();
            }}
          >
            Load latest version
          </Button>
        }
      >
        <p className="text-sm">
          {apiErrorMessage(update.error)} Your unsaved edits will be replaced by the latest saved
          version.
        </p>
      </Modal>
    </section>
  );
}
