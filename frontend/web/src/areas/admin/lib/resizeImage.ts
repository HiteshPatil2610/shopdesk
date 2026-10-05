/**
 * Shrinks a photo in the browser before upload (spec 03): phone photos are often 5–12 MB,
 * Vercel functions accept ~4.5 MB. The server still validates and re-encodes everything.
 */

export const MAX_SIDE = 1024;
export const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

/** Size that fits inside MAX_SIDE×MAX_SIDE while keeping the aspect ratio. */
export function fitWithin(width: number, height: number, max = MAX_SIDE) {
  if (width <= max && height <= max) return { width, height };
  const scale = Math.min(max / width, max / height);
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

export async function resizeImage(file: File): Promise<Blob> {
  if (!ACCEPTED_TYPES.includes(file.type)) {
    throw new Error('Use a JPG, PNG or WebP image');
  }
  const bitmap = await createImageBitmap(file);
  const { width, height } = fitWithin(bitmap.width, bitmap.height);
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('This browser cannot process images');
  ctx.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, 'image/webp', 0.85),
  );
  if (!blob) throw new Error('Could not process this image');
  return blob;
}
