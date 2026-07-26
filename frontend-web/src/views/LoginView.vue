<script setup lang="ts">
// ============================================================
// Layer 8: View — Login
// ============================================================
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSystemStore } from '@/stores/system'
import { Sunny } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const systemStore = useSystemStore()

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const formRef = ref()

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  const ok = await authStore.login({
    username: form.username,
    password: form.password,
  })

  if (ok) {
    const redirect = (route.query.redirect as string) || '/chat'
    router.push(redirect)
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <Sunny class="login-logo" />
        <h1>智能旅行规划</h1>
        <p>登录以使用旅行规划、知识库和长期记忆</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="输入用户名"
            autocomplete="username"
            size="large"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="输入密码"
            autocomplete="current-password"
            show-password
            size="large"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-alert
          v-if="authStore.loginError"
          :title="authStore.loginError"
          type="error"
          show-icon
          :closable="false"
          style="margin-bottom: 16px"
        />

        <el-button
          type="primary"
          size="large"
          :loading="authStore.isLoginLoading"
          style="width: 100%"
          @click="handleLogin"
        >
          登录
        </el-button>
      </el-form>

      <div class="login-footer">
        <span v-if="systemStore.health?.registration_enabled">
          还没有账号？
          <el-link type="primary" disabled>请联系管理员</el-link>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    linear-gradient(90deg, transparent 49.9%, rgba(20, 125, 100, .05) 50%, transparent 50.1%),
    var(--el-bg-color-page);
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 400px;
  padding: 40px 36px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-top: 3px solid var(--el-color-primary);
  border-radius: 6px;
  box-shadow: 0 12px 36px rgba(32, 39, 37, .08);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-logo {
  width: 56px;
  height: 56px;
  color: var(--el-color-warning);
  margin-bottom: 12px;
}

.login-header h1 {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.login-header p {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.login-footer {
  text-align: center;
  margin-top: 20px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
