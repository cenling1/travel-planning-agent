<script setup lang="ts">
// ============================================================
// Layer 8: View — Profile / Account Settings
// ============================================================
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()

const passwordFormRef = ref<FormInstance>()
const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

const validateConfirmPassword = (_rule: any, value: string, callback: Function) => {
  if (value !== passwordForm.new_password) {
    callback(new Error('两次密码不一致'))
  } else {
    callback()
  }
}

const passwordRules: FormRules = {
  current_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 10, message: '密码至少 10 位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

const isChangingPassword = ref(false)
const changePasswordError = ref<string | null>(null)

async function handleChangePassword() {
  const valid = await passwordFormRef.value?.validate().catch(() => false)
  if (!valid) return

  isChangingPassword.value = true
  changePasswordError.value = null
  try {
    const ok = await authStore.changePassword({
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    })
    if (ok) {
      ElMessage.success('密码已修改，请重新登录')
      router.push('/login')
    } else {
      changePasswordError.value = '修改密码失败'
    }
  } catch {
    changePasswordError.value = '修改密码失败'
  } finally {
    isChangingPassword.value = false
  }
}

async function handleLogoutAll() {
  try {
    await authStore.logoutAll()
    ElMessage.success('已退出所有设备')
    router.push('/login')
  } catch {
    ElMessage.error('操作失败')
  }
}
</script>

<template>
  <div class="profile-page">
    <h2>账号设置</h2>

    <!-- User info -->
    <el-card class="info-card">
      <template #header>基本信息</template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="用户名">{{ authStore.user?.username }}</el-descriptions-item>
        <el-descriptions-item label="角色">
          <el-tag :type="authStore.isAdmin ? 'warning' : 'info'" size="small">
            {{ authStore.isAdmin ? '管理员' : '普通用户' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ authStore.user?.email || '未设置' }}</el-descriptions-item>
        <el-descriptions-item label="注册时间">{{ authStore.user?.created_at ? new Date(authStore.user.created_at).toLocaleDateString('zh-CN') : '—' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- Change password -->
    <el-card class="password-card">
      <template #header>修改密码</template>
      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-width="100px"
        style="max-width: 440px"
      >
        <el-form-item label="当前密码" prop="current_password">
          <el-input
            v-model="passwordForm.current_password"
            type="password"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="passwordForm.new_password"
            type="password"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input
            v-model="passwordForm.confirm_password"
            type="password"
            show-password
          />
        </el-form-item>

        <el-alert
          v-if="changePasswordError"
          :title="changePasswordError"
          type="error"
          show-icon
          :closable="false"
          style="margin-bottom: 12px"
        />

        <el-form-item>
          <el-button
            type="primary"
            :loading="isChangingPassword"
            @click="handleChangePassword"
          >
            修改密码
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Sessions -->
    <el-card class="sessions-card">
      <template #header>会话管理</template>
      <p class="card-desc">退出所有已登录的设备，包括当前设备。</p>
      <el-button type="danger" plain @click="handleLogoutAll">
        退出所有设备
      </el-button>
    </el-card>
  </div>
</template>

<style scoped>
.profile-page {
  max-width: 700px;
  padding: 16px 24px;
}

.profile-page h2 {
  margin: 0 0 20px;
  font-size: 18px;
}

.info-card,
.password-card,
.sessions-card {
  margin-bottom: 20px;
}

.card-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0 0 12px;
}
</style>
