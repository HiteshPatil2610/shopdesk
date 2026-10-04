// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { Modal } from './Modal';

afterEach(cleanup);

/** Re-renders on every keystroke and passes a NEW onClose each time — like a real form. */
function TypingForm() {
  const [first, setFirst] = useState('');
  const [second, setSecond] = useState('');
  return (
    <Modal open title="Add user" onClose={() => undefined}>
      <label>
        Username
        <input value={first} onChange={(e) => setFirst(e.target.value)} />
      </label>
      <label>
        Password
        <input value={second} onChange={(e) => setSecond(e.target.value)} />
      </label>
    </Modal>
  );
}

describe('Modal', () => {
  it('focuses the first field once when it opens', () => {
    render(<TypingForm />);
    expect(document.activeElement).toBe(screen.getByLabelText('Username'));
  });

  it('keeps focus in the field being typed in when the parent re-renders', () => {
    render(<TypingForm />);
    const password = screen.getByLabelText('Password');
    password.focus();
    fireEvent.change(password, { target: { value: 'a' } });
    fireEvent.change(password, { target: { value: 'ab' } });
    expect(document.activeElement).toBe(password);
  });

  it('calls the latest onClose on Escape', () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <Modal open title="t" onClose={() => undefined}>
        <input aria-label="x" />
      </Modal>,
    );
    rerender(
      <Modal open title="t" onClose={onClose}>
        <input aria-label="x" />
      </Modal>,
    );
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledOnce();
  });
});
