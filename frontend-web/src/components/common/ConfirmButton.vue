<script setup lang="ts">
import { ref } from 'vue'
import { ElMessageBox } from 'element-plus'

const props = defineProps<{
  title: string
  message: string
  confirmText?: string
  type?: 'warning' | 'danger'
  size?: 'small' | 'default' | 'large'
  link?: boolean
}>()

const emit = defineEmits<{
  confirm: []
}>()

const loading = ref(false)

async function handleClick() {
  try {
    await ElMessageBox.confirm(props.message, props.title, {
      confirmButtonText: props.confirmText || '确定',
      cancelButtonText: '取消',
      type: (props.type === 'danger' ? 'error' : props.type) || 'warning',
    })
    loading.value = true
    emit('confirm')
  } catch {
    // cancelled
  }
}
</script>

<template>
  <el-popconfirm
    :title="message"
    :confirm-button-text="confirmText || '确定'"
    cancel-button-text="取消"
    @confirm="$emit('confirm')"
  >
    <template #reference>
      <el-button
        :size="size || 'small'"
        :type="type === 'danger' ? 'danger' : 'warning'"
        :link="link"
      >
        <slot />
      </el-button>
    </template>
  </el-popconfirm>
</template>
