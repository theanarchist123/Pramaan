/** Shrink a very large photo before upload (phone cameras make 8-12 MB files). Small files and non-images are returned untouched, because
 *  re-encoding drops the file's own metadata, which the document check uses; so we only do it when the size is the problem. */
export const COMPRESS_OVER_BYTES = 4 * 1024 * 1024;
const MAX_EDGE = 2400;

export function shouldCompress(file: { type: string; size: number }): boolean {
  return /^image\/(jpeg|png|webp)$/.test(file.type) && file.size > COMPRESS_OVER_BYTES;
}

export function targetSize(w: number, h: number, maxEdge = MAX_EDGE): { w: number; h: number } {
  const scale = Math.min(1, maxEdge / Math.max(w, h));
  return { w: Math.round(w * scale), h: Math.round(h * scale) };
}

export async function compressIfLarge(file: File): Promise<File> {
  if (!shouldCompress(file) || typeof createImageBitmap === "undefined") return file;
  try {
    const bmp = await createImageBitmap(file);
    const { w, h } = targetSize(bmp.width, bmp.height);
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    canvas.getContext("2d")?.drawImage(bmp, 0, 0, w, h);
    bmp.close();
    const blob = await new Promise<Blob | null>((res) => canvas.toBlob(res, "image/jpeg", 0.85));
    if (!blob || blob.size >= file.size) return file;
    return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch {
    return file; // never block an upload because shrinking failed
  }
}
