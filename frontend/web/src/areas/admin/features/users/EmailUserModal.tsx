import { apiErrorMessage, Button, Modal, TextField } from '@shopdesk/shared';
import { useState } from 'react';
import { z } from 'zod';
import { useUpdateUser, type AdminUser } from './api';

export function EmailUserModal({ user, onClose }: { user: AdminUser; onClose: () => void }) {
  const [email, setEmail] = useState(user.email ?? '');
  const [error, setError] = useState('');
  const update = useUpdateUser();
  return (
    <Modal
      open
      title={`Set email for ${user.full_name}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={update.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="set-user-email" disabled={update.isPending}>
            {update.isPending ? 'Saving…' : 'Save email'}
          </Button>
        </>
      }
    >
      <form
        id="set-user-email"
        className="flex flex-col gap-4"
        noValidate
        onSubmit={async (event) => {
          event.preventDefault();
          const parsed = z.email().max(254).safeParse(email.trim());
          if (!parsed.success) {
            setError('Enter a valid email address.');
            return;
          }
          setError('');
          try {
            await update.mutateAsync({ id: user.id, email: parsed.data });
            onClose();
          } catch {
            /* The API error is shown below. */
          }
        }}
      >
        <TextField
          label="Email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={error}
          hint="The admin confirms this as the user's primary sign-in and recovery email. Check the address carefully."
        />
        {update.isError && (
          <p role="alert" className="text-sm text-danger">
            {apiErrorMessage(update.error)}
          </p>
        )}
      </form>
    </Modal>
  );
}
