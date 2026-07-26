import { describe, expect, it } from 'vitest'
import { renderMarkdown } from './markdown'

describe('renderMarkdown', () => {
  it('removes executable HTML and unsafe link protocols', () => {
    const html = renderMarkdown('[bad](javascript:alert(1))<script>alert(2)</script><img src=x onerror=alert(3)>')

    expect(html).not.toContain('javascript:')
    expect(html).not.toContain('<script')
    expect(html).not.toContain('onerror')
  })

  it('adds isolation attributes to rendered links', () => {
    const html = renderMarkdown('[Travel](https://example.com)')

    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
  })
})
