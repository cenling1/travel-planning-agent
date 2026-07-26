// ============================================================
// Layer 9: Application entry point
// Initialization order: Pinia → Router → App
// ============================================================

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import router from './router'

const app = createApp(App)

// Pinia must be installed before router guards access stores
const pinia = createPinia()
app.use(pinia)

// Router (guards depend on Pinia being installed)
app.use(router)

window.addEventListener('auth:expired', () => {
  if (router.currentRoute.value.path !== '/login') {
    router.replace({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } })
  }
})

// Element Plus with Chinese locale
app.use(ElementPlus, { locale: zhCn })

app.mount('#app')
