/**
 * Display formatters to ensure clean, student-friendly presentation.
 * Hides raw file extensions, ISBN codes, hashes, and internal metadata.
 */

export function formatDocumentTitle(rawName: string, fallback = 'Study Material'): string {
  if (!rawName) return fallback;

  // Remove file extension
  let clean = rawName.replace(/\.(pdf|docx|txt|md|pptx|markdown)$/i, '').trim();

  // If mostly numbers or ISBN/hash artifacts (e.g. 1nbsped-1098135504-9781098135508)
  const lettersOnly = clean.replace(/[\d\-_]/g, '');
  if (lettersOnly.length < 4 || /^(nbsped|isbn|\d+)/i.test(clean)) {
    return `${fallback} Notes`;
  }

  // Replace underscores and hyphens with spaces
  clean = clean.replace(/[-_]+/g, ' ');

  // Strip leading numbers if any
  clean = clean.replace(/^\d+\s*/, '');

  // Title Case words
  const words = clean.split(' ').filter(Boolean);
  const titled = words
    .map((w) => (w === w.toUpperCase() && w.length <= 4 ? w : w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()))
    .join(' ');

  return titled.length > 3 ? titled : fallback;
}

export function formatFileSize(bytes: number): string {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function formatFriendlyDate(dateStr: string): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * Format verified grounding source page citations into clean human labels.
 * Examples:
 *   [16, 17, 18, 19, 20] -> "Pages 16–20"
 *   [5] -> "Page 5"
 *   [2, 7, 11] -> "Pages 2, 7, 11"
 */
export function formatSourcePages(pages?: number[]): string | null {
  if (!pages || pages.length === 0) return null;
  // Filter valid positive page numbers and sort
  const validPages = pages.filter((p) => typeof p === 'number' && p > 0);
  if (validPages.length === 0) return null;
  const sorted = Array.from(new Set(validPages)).sort((a, b) => a - b);
  if (sorted.length === 1) return `Page ${sorted[0]}`;

  const isConsecutive = sorted.every((p, idx) => idx === 0 || p === sorted[idx - 1] + 1);
  if (isConsecutive && sorted.length > 1) {
    return `Pages ${sorted[0]}–${sorted[sorted.length - 1]}`;
  }
  return `Pages ${sorted.join(', ')}`;
}
