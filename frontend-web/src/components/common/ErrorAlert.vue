<script setup lang="ts">
import { extractErrorMessage, errorRecoveryHint } from '@/utils/error'

defineProps<{
  error: unknown
  showRetry?: boolean
}>()

defineEmits<{
  retry: []
}>()
</script>

<template>
  <el-alert
    v-if="error"
    :title="extractErrorMessage(error)"
    :description="errorRecoveryHint(error) || undefined"
    type="error"
    show-icon
    :closable="false"
  >
    <template v-if="showRetry" #default>
      <el-button size="small" text type="danger" @click="$emit('retry')">
        重试
      </el-button>
    </template>
  </el-alert>
</template>
