<script setup lang="ts">
defineProps<{
  icon?: string
  title: string
  description?: string
  actionLabel?: string
}>()

defineEmits<{
  action: []
}>()
</script>

<template>
  <div class="empty-state">
    <el-icon v-if="icon" class="empty-icon" :size="48">
      <component :is="icon" />
    </el-icon>
    <h3 class="empty-title">{{ title }}</h3>
    <p v-if="description" class="empty-desc">{{ description }}</p>
    <el-button
      v-if="actionLabel"
      type="primary"
      @click="$emit('action')"
    >
      {{ actionLabel }}
    </el-button>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  text-align: center;
}

.empty-icon {
  color: var(--el-text-color-placeholder);
  margin-bottom: 12px;
}

.empty-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
  margin: 0 0 8px;
}

.empty-desc {
  font-size: 13px;
  color: var(--el-text-color-placeholder);
  margin: 0 0 20px;
  max-width: 360px;
}
</style>
