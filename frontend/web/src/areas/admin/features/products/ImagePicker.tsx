import { Button } from '@shopdesk/shared';
import { useEffect, useId, useRef, useState } from 'react';

import { ACCEPTED_TYPES, resizeImage } from '../../lib/resizeImage';

type Props = {
  /** Current image URL (edit page) shown until a new file is chosen. */
  currentUrl?: string | null;
  /** Called with the resized image, or null when removed. */
  onChange: (image: Blob | null) => void;
  disabled?: boolean;
};

/** Drop or pick a photo; it's resized to ≤1024px WebP in the browser before upload. */
export function ImagePicker({ currentUrl, onChange, disabled }: Props) {
  const inputId = useId();
  const input = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);

  useEffect(() => () => void (preview && URL.revokeObjectURL(preview)), [preview]);

  const handle = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    setBusy(true);
    try {
      const blob = await resizeImage(file);
      setPreview(URL.createObjectURL(blob));
      onChange(blob);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not use this image');
    } finally {
      setBusy(false);
    }
  };

  const shown = preview ?? currentUrl ?? null;

  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor={inputId}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          void handle(e.dataTransfer.files[0]);
        }}
        className={`flex aspect-square w-full cursor-pointer items-center justify-center overflow-hidden rounded-xl border-2 border-dashed bg-bg text-center text-sm text-text-muted ${
          dragging ? 'border-primary' : 'border-border'
        }`}
      >
        {shown ? (
          <img src={shown} alt="Product" className="h-full w-full object-contain" />
        ) : (
          <span className="p-4">
            {busy ? 'Processing…' : 'Drop a photo here or click to choose'}
            <br />
            <span className="text-xs">JPG, PNG or WebP · resized automatically</span>
          </span>
        )}
      </label>
      <input
        id={inputId}
        ref={input}
        type="file"
        accept={ACCEPTED_TYPES.join(',')}
        className="sr-only"
        disabled={disabled || busy}
        onChange={(e) => void handle(e.target.files?.[0])}
      />
      {shown && (
        <Button
          size="sm"
          variant="ghost"
          disabled={disabled || busy}
          onClick={() => {
            setPreview(null);
            if (input.current) input.current.value = '';
            onChange(null);
          }}
        >
          Remove photo
        </Button>
      )}
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
