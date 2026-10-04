// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { KpiTile } from './KpiTile';

afterEach(cleanup);

describe('KpiTile', () => {
  it('shows an up arrow and sign, not colour alone', () => {
    render(<KpiTile label="Sales" value="₹990.00" change="395.00" />);
    expect(screen.getByText(/▲ \+395.0%/)).toBeDefined();
    expect(screen.getByLabelText('up 395.00 percent vs yesterday')).toBeDefined();
  });

  it('shows a down arrow for a drop', () => {
    render(<KpiTile label="Profit" value="₹10.00" change="-12.50" />);
    expect(screen.getByText(/▼ -12.5%/)).toBeDefined();
  });

  it('shows the sub-line when there is nothing to compare with', () => {
    render(<KpiTile label="Low stock" value="2" change={null} sub="1 out of stock" />);
    expect(screen.getByText('1 out of stock')).toBeDefined();
    expect(screen.queryByText(/vs yesterday/)).toBeNull();
  });
});
