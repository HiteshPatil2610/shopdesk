import { zodResolver } from '@hookform/resolvers/zod';
import { apiErrorMessage, Button, Modal, SelectField, TextField } from '@shopdesk/shared';
import { useForm } from 'react-hook-form';
import { useState } from 'react';

import { useCreateUser } from './api';
import { newUserSchema, type NewUserForm } from './schema';

const ROLE_OPTIONS = [
  { value: 'cashier', label: 'Cashier: Billing Counter only' },
  { value: 'manager', label: 'Manager: products, stock, orders, audit' },
  { value: 'admin', label: 'Admin: everything, including users and pricing' },
];

type Props = { open: boolean; onClose: () => void };

export function AddUserModal({ open, onClose }: Props) {
  const create = useCreateUser();
  const [showPassword, setShowPassword] = useState(false);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<NewUserForm>({
    resolver: zodResolver(newUserSchema),
    defaultValues: { role: 'cashier' },
  });

  const close = () => {
    reset();
    create.reset();
    setShowPassword(false);
    onClose();
  };

  const onSubmit = handleSubmit(async (data) => {
    try {
      await create.mutateAsync({ ...data, email: data.email || undefined });
      close();
    } catch {
      /* The mutation error stays visible in the form. */
    }
  });

  return (
    <Modal
      open={open}
      title="Add staff account"
      onClose={close}
      footer={
        <>
          <Button variant="secondary" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" form="add-user-form" disabled={isSubmitting}>
            {isSubmitting ? 'Creating…' : 'Create account'}
          </Button>
        </>
      }
    >
      <form id="add-user-form" onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <TextField
          label="Username"
          autoComplete="off"
          hint="Used to sign in"
          error={errors.username?.message}
          {...register('username')}
        />
        <TextField label="Full name" error={errors.full_name?.message} {...register('full_name')} />
        <TextField
          label="Email (optional)"
          type="email"
          autoComplete="off"
          hint="Primary sign-in and recovery email. Check the address carefully."
          error={errors.email?.message}
          {...register('email')}
        />
        <SelectField
          label="Role"
          options={ROLE_OPTIONS}
          error={errors.role?.message}
          {...register('role')}
        />
        <TextField
          label="Temporary password"
          type={showPassword ? 'text' : 'password'}
          autoComplete="new-password"
          hint="At least 10 characters. Share it with them privately."
          error={errors.password?.message}
          {...register('password')}
        />
        <Button
          variant="secondary"
          aria-pressed={showPassword}
          onClick={() => setShowPassword((value) => !value)}
        >
          {showPassword ? 'Hide password' : 'Show password'}
        </Button>
        {create.isError && (
          <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
            {apiErrorMessage(create.error)}
          </p>
        )}
      </form>
    </Modal>
  );
}
