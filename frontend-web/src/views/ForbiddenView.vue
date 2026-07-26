<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Lock } from '@element-plus/icons-vue'

const router = useRouter()
</script>

<template>
  <section class="state-page">
    <el-icon :size="40"><Lock /></el-icon>
    <h1>没有访问权限</h1>
    <p>当前账号不能查看管理页面。</p>
    <el-button type="primary" @click="router.push('/chat')">返回旅行工作台</el-button>
  </section>
</template>

<style scoped>
.state-page {
  min-height: 100%;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 12px;
  padding: 32px;
  text-align: center;
  color: var(--el-text-color-secondary);
}
.state-page h1 { margin: 4px 0 0; font-size: 22px; color: var(--el-text-color-primary); }
.state-page p { margin: 0 0 8px; }
</style>
