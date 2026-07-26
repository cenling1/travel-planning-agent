// ============================================================
// Layer 5: Router — Route definitions & navigation guards
// ============================================================

import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import MainLayout from '@/layouts/MainLayout.vue'
import AdminLayout from '@/layouts/AdminLayout.vue'
import { getRouteAccessRedirect } from './access'

// Lazy-loaded views for code splitting
const LoginView = () => import('@/views/LoginView.vue')
const ChatView = () => import('@/views/ChatView.vue')
const DocumentsView = () => import('@/views/DocumentsView.vue')
const MemoriesView = () => import('@/views/MemoriesView.vue')
const ProfileView = () => import('@/views/ProfileView.vue')
const AdminUsersView = () => import('@/views/admin/AdminUsersView.vue')
const AdminSystemView = () => import('@/views/admin/AdminSystemView.vue')
const NotFoundView = () => import('@/views/NotFoundView.vue')
const ForbiddenView = () => import('@/views/ForbiddenView.vue')

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView,
    meta: { guest: true },
  },
  {
    path: '/',
    component: MainLayout,
    meta: { auth: true },
    children: [
      { path: '', redirect: '/chat' },
      { path: 'chat/:conversationId?', name: 'Chat', component: ChatView },
      { path: 'documents', name: 'Documents', component: DocumentsView },
      { path: 'memories', name: 'Memories', component: MemoriesView },
      { path: 'profile', name: 'Profile', component: ProfileView },
      { path: 'forbidden', name: 'Forbidden', component: ForbiddenView },
      {
        path: 'admin',
        component: AdminLayout,
        meta: { role: 'admin' },
        children: [
          { path: '', redirect: '/admin/users' },
          { path: 'users', name: 'AdminUsers', component: AdminUsersView },
          { path: 'system', name: 'AdminSystem', component: AdminSystemView },
        ],
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: NotFoundView,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ---- Navigation Guard ----
router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()

  if (!authStore.restoreAttempted && !authStore.isRestoring) {
    await authStore.restoreSession()
  }

  const isAuthenticated = authStore.isAuthenticated
  const redirect = getRouteAccessRedirect(to.meta, to.fullPath, isAuthenticated, authStore.isAdmin)
  if (redirect) return next(redirect)

  next()
})

export default router
