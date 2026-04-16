/**
 * Minimal HTML sanitizer — strips dangerous tags/attributes.
 * For production, replace with DOMPurify library.
 */
export default function purify(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/on\w+\s*=\s*["'][^"']*["']/gi, '')
    .replace(/javascript\s*:/gi, '')
}
