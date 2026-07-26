import { describe, expect, it } from 'vitest'
import { getRouteAccessRedirect } from './access'

describe('route access', () => {
  it('returns authenticated users from the login page to chat', () => {
    expect(getRouteAccessRedirect({ guest: true }, '/login', true, false)).toBe('/chat')
  })

  it('preserves the requested path when redirecting a guest to login', () => {
    expect(getRouteAccessRedirect({ auth: true }, '/documents?tab=recent', false, false)).toEqual({
      path: '/login',
      query: { redirect: '/documents?tab=recent' },
    })
  })

  it('sends non-admin users to the forbidden page', () => {
    expect(getRouteAccessRedirect({ auth: true, role: 'admin' }, '/admin/users', true, false)).toBe('/forbidden')
  })

  it('allows an administrator to open protected admin routes', () => {
    expect(getRouteAccessRedirect({ auth: true, role: 'admin' }, '/admin/users', true, true)).toBeNull()
  })
})
