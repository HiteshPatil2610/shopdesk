import { zodResolver } from '@hookform/resolvers/zod';
import { apiErrorMessage, Button, Modal, TextField, type UserPublic } from '@shopdesk/shared';
import { useForm } from 'react-hook-form';

import { useResetPassword } from './api';
import { resetPasswordSchema, type ResetPasswordForm } from './schema';

type Props = { user: UserPublic | null; onClose: () => void };

export function ResetPasswordModal({ user, onClose }: Props) {
  const resetPassword = useResetPassword();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordForm>({ resolver: zodResolver(resetPasswordSchema) });

  const close = () => {
    reset();
    resetPassword.reset();
    onClose();
  };

  const onSubmit = handleSubmit(async ({ new_password }) => {
    if (!user) return;
    await resetPassword.mutateAsync({ id: user.id, new_password });
    close();
  });

  return (
    <Modal
      open={user !== null}
      title={`Reset password for ${user?.username ?? user?.full_name ?? ''}`}
      onClose={close}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" form="reset-password-form" disabled={isSubmitting}>
            {isSubmitting ? 'Saving…' : 'Reset password'}
          </Button>
        </>
      }
    >
      <form id="reset-password-form" onSubmit={onSubmit} className="flex flex-col gap-3" noValidate>
        <TextField
          label="New password"
          type="password"
          autoComplete="new-password"
          error={errors.new_password?.message}
          {...register('new_password')}
        />
        <p className="text-xs text-text-muted">They'll be signed out of every device.</p>
        {resetPassword.isError && (
          <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
            {apiErrorMessage(resetPassword.error)}
          </p>
        )}
      </form>
    </Modal>
  );
}
