<script setup lang="ts">
// ============================================================
// Layer 8: View — Admin: User Management
// ============================================================
import { ref, onMounted, reactive } from 'vue'
import { adminApi } from '@/api/admin'
import type { User } from '@/types/auth'
import { formatDate } from '@/utils/format'
import { extractErrorMessage } from '@/utils/error'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const users = ref<User[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)

// Create user dialog
const createDialogVisible = ref(false)
const isCreating = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive({
  username: '',
  email: '',
  password: '',
  role: 'user' as 'user' | 'admin',
})

const createRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 64, message: '用户名 3-64 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 10, message: '密码至少 10 位', trigger: 'blur' },
  ],
}

// Reset password dialog
const resetDialogVisible = ref(false)
const resetUserId = ref('')
const resetUsername = ref('')
const resetPassword = ref('')
const isResetting = ref(false)

// Edit user dialog
const editDialogVisible = ref(false)
const editUserId = ref('')
const editUsername = ref('')
const editRole = ref<'user' | 'admin'>('user')
const editIsActive = ref(true)
const isEditing = ref(false)

async function fetchUsers() {
  isLoading.value = true
  error.value = null
  try {
    users.value = await adminApi.listUsers()
  } catch (err) {
    error.value = extractErrorMessage(err, '加载用户列表失败')
  } finally {
    isLoading.value = false
  }
}

async function handleCreate() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return

  isCreating.value = true
  try {
    const user = await adminApi.createUser({
      username: createForm.username,
      email: createForm.email || undefined,
      password: createForm.password,
      role: createForm.role,
    })
    users.value.unshift(user)
    createDialogVisible.value = false
    ElMessage.success(`用户 ${user.username} 已创建`)
    createForm.username = ''
    createForm.email = ''
    createForm.password = ''
    createForm.role = 'user'
  } catch (err) {
    ElMessage.error(extractErrorMessage(err, '创建失败'))
  } finally {
    isCreating.value = false
  }
}

function openEditDialog(user: User) {
  editUserId.value = user.id
  editUsername.value = user.username
  editRole.value = user.role as 'user' | 'admin'
  editIsActive.value = user.is_active
  editDialogVisible.value = true
}

async function handleEdit() {
  isEditing.value = true
  try {
    const updated = await adminApi.updateUser(editUserId.value, {
      role: editRole.value,
      is_active: editIsActive.value,
    })
    const idx = users.value.findIndex((u) => u.id === editUserId.value)
    if (idx !== -1) users.value[idx] = updated
    editDialogVisible.value = false
    ElMessage.success('用户已更新')
  } catch (err) {
    ElMessage.error(extractErrorMessage(err, '更新失败'))
  } finally {
    isEditing.value = false
  }
}

function openResetDialog(user: User) {
  resetUserId.value = user.id
  resetUsername.value = user.username
  resetPassword.value = ''
  resetDialogVisible.value = true
}

async function handleResetPassword() {
  if (resetPassword.value.length < 10) {
    ElMessage.error('密码至少 10 位')
    return
  }

  isResetting.value = true
  try {
    await adminApi.resetPassword(resetUserId.value, {
      new_password: resetPassword.value,
    })
    resetDialogVisible.value = false
    ElMessage.success(`已重置 ${resetUsername.value} 的密码`)
  } catch (err) {
    ElMessage.error(extractErrorMessage(err, '重置失败'))
  } finally {
    isResetting.value = false
  }
}

onMounted(fetchUsers)
</script>

<template>
  <div class="admin-users">
    <div class="page-header">
      <h2>用户管理</h2>
      <div class="header-actions">
        <el-button :icon="Plus" type="primary" @click="createDialogVisible = true">
          创建用户
        </el-button>
        <el-button :icon="Refresh" :loading="isLoading" @click="fetchUsers">
          刷新
        </el-button>
      </div>
    </div>

    <ErrorAlert v-if="error" :error="error" :show-retry="true" @retry="fetchUsers" />

    <el-table :data="users" v-loading="isLoading" stripe>
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column prop="email" label="邮箱" min-width="160">
        <template #default="{ row }">{{ row.email || '—' }}</template>
      </el-table-column>
      <el-table-column prop="role" label="角色" width="90">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'warning' : 'info'" size="small">
            {{ row.role === 'admin' ? '管理员' : '用户' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_login_at" label="最近登录" width="160">
        <template #default="{ row }">{{ row.last_login_at ? formatDate(row.last_login_at) : '—' }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="160">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button text size="small" type="primary" @click="openEditDialog(row)">编辑</el-button>
          <el-button text size="small" type="warning" @click="openResetDialog(row)">重置密码</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Create User Dialog -->
    <el-dialog v-model="createDialogVisible" title="创建用户" width="440px">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="3-64 个字符" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="createForm.email" placeholder="可选" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="createForm.password" type="password" show-password placeholder="至少 10 位" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="createForm.role" style="width: 100%">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="isCreating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- Edit User Dialog -->
    <el-dialog v-model="editDialogVisible" :title="`编辑用户: ${editUsername}`" width="400px">
      <el-form label-position="top">
        <el-form-item label="角色">
          <el-select v-model="editRole" style="width: 100%">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editIsActive" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="isEditing" @click="handleEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- Reset Password Dialog -->
    <el-dialog v-model="resetDialogVisible" :title="`重置密码: ${resetUsername}`" width="400px">
      <el-form label-position="top">
        <el-form-item label="新密码">
          <el-input
            v-model="resetPassword"
            type="password"
            show-password
            placeholder="至少 10 位"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="isResetting" @click="handleResetPassword">
          重置
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.admin-users {
  padding: 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-header h2 { margin: 0; font-size: 18px; }
.header-actions { display: flex; gap: 8px; }
</style>
