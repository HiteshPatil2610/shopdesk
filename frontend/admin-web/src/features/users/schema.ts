import { z } from 'zod';

// Mirrors backend core/schemas/users.py
export const newUserSchema = z
  .object({
    username: z
      .string()
      .trim()
      .min(3, 'At least 3 characters')
      .max(50)
      .regex(/^[a-zA-Z0-9_.-]+$/, 'Letters, numbers, dot, dash or underscore only'),
    full_name: z.string().trim().min(2, 'Enter the full name').max(120),
    role: z.enum(['admin', 'manager', 'cashier']),
    password: z.string().min(10, 'At least 10 characters').max(128),
  })
  .refine((v) => v.password.toLowerCase() !== v.username.toLowerCase(), {
    path: ['password'],
    message: 'Password must not be the same as the username',
  });

export type NewUserForm = z.infer<typeof newUserSchema>;

export const resetPasswordSchema = z.object({
  new_password: z.string().min(10, 'At least 10 characters').max(128),
});

export type ResetPasswordForm = z.infer<typeof resetPasswordSchema>;
