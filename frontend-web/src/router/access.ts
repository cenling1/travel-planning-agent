export interface RouteAccessMeta {
  guest?: boolean
  auth?: boolean
  role?: string
}

export type RouteAccessRedirect = string | {
  path: string
  query: { redirect: string }
}

export function getRouteAccessRedirect(
  meta: RouteAccessMeta,
  fullPath: string,
  isAuthenticated: boolean,
  isAdmin: boolean,
): RouteAccessRedirect | null {
  if (meta.guest && isAuthenticated) return '/chat'

  if (meta.auth && !isAuthenticated) {
    return { path: '/login', query: { redirect: fullPath } }
  }

  if (meta.role === 'admin' && !isAdmin) return '/forbidden'

  return null
}
