// ============================================================
// Layer 2: Utility — Markdown renderer
// Uses marked + DOMPurify for safe, XSS-free rendering
// ============================================================

import { marked } from 'marked'
import DOMPurify from 'dompurify'

// Configure marked for safe rendering
marked.setOptions({
  breaks: true,
  gfm: true,
})

// Whitelist of allowed HTML tags and attributes
const ALLOWED_TAGS = [
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'p', 'br', 'hr',
  'ul', 'ol', 'li',
  'blockquote', 'pre', 'code',
  'strong', 'em', 'del',
  'a', 'img',
  'table', 'thead', 'tbody', 'tr', 'th', 'td',
  'span', 'div',
]

const ALLOWED_ATTR = [
  'href', 'src', 'alt', 'title', 'target', 'rel',
  'class', 'id',
]

/**
 * Convert raw Markdown text to sanitized HTML.
 * Strips executable elements (script, iframe, event handlers).
 */
export function renderMarkdown(text: string): string {
  if (!text) return ''

  // Pre-process: normalize citation markers
  const normalized = text

  // Render with marked
  const html = marked.parse(normalized, { async: false }) as string

  // Sanitize with DOMPurify
  const clean = DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ADD_ATTR: ['target'],
  } satisfies DOMPurify.Config)

  // Open external links in new tab
  return clean.replace(/<a /g, '<a target="_blank" rel="noopener noreferrer" ')
}

/**
 * Strip markdown formatting for use in plain-text contexts (e.g., search snippets).
 */
export function stripMarkdown(text: string, maxLength = 120): string {
  const stripped = text
    .replace(/[#*_`~>\[\]()|]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  return stripped.length > maxLength
    ? stripped.substring(0, maxLength) + '…'
    : stripped
}
