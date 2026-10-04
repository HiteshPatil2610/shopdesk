import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import { PricingSettingsPage } from './PricingSettingsPage';

const { save, examples } = vi.hoisted(() => ({ save: vi.fn(), examples: vi.fn() }));
vi.mock('../features/pricing/api', () => ({
  usePricingSettings: () => ({
    data: {
      markup_low_pct: '95',
      markup_high_pct: '90',
      markup_threshold: '500',
      small_mp_limit: '500',
      small_mp_step: '10',
      small_mp_alt_step: '50',
      mp_step: '50',
      mp_alt_step: '100',
      sp_discount_pct: '10',
      sp_step: '10',
      sp_avoid_ten: true,
    },
  }),
  useSavePricingSettings: () => ({ mutate: save }),
  useApplyPricing: () => ({}),
  useExamples: examples,
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

it('saves the rounding switch as a boolean without invalidating numeric settings', () => {
  examples.mockReturnValue({ data: [] });
  render(<PricingSettingsPage />);
  const toggle = screen.getByRole('checkbox');
  expect((toggle as HTMLInputElement).checked).toBe(true);
  fireEvent.click(toggle);
  const button = screen.getByRole('button', { name: 'Save rules' });
  expect((button as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(button);
  expect(save).toHaveBeenCalledWith(expect.objectContaining({ sp_avoid_ten: false }));
});
