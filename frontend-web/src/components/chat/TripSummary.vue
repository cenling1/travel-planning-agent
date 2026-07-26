<script setup lang="ts">
// ============================================================
// Layer 6: Component — TripSummary
// Side panel showing extracted trip parameters
// Only shows when data is available
// ============================================================
import { computed } from 'vue'
import type { TravelResponse } from '@/types/chat'

const props = defineProps<{
  response: TravelResponse | null
}>()

const visible = computed(() => {
  if (!props.response) return false
  return Object.values(props.response.trip_summary || {}).some((value) =>
    Array.isArray(value) ? value.length > 0 : value !== null && value !== '',
  )
})

const scenarioLabel = computed(() => {
  const map: Record<string, string> = {
    simple: '单目的地',
    complex: '复杂需求',
    multi_destination: '多目的地',
  }
  return map[props.response?.scenario_type || 'simple'] || '—'
})
</script>

<template>
  <aside v-if="visible" class="trip-summary">
    <h4 class="summary-title">行程摘要</h4>

    <div class="summary-item">
      <span class="summary-label">方案类型</span>
      <el-tag size="small">{{ scenarioLabel }}</el-tag>
    </div>

    <div v-if="response?.trip_summary.destination" class="summary-item">
      <span class="summary-label">目的地</span>
      <span class="summary-value">{{ response.trip_summary.destination }}</span>
    </div>
    <div v-if="response?.trip_summary.origin" class="summary-item">
      <span class="summary-label">出发地</span>
      <span class="summary-value">{{ response.trip_summary.origin }}</span>
    </div>
    <div v-if="response?.trip_summary.travel_date" class="summary-item">
      <span class="summary-label">出发日期</span>
      <span class="summary-value">{{ response.trip_summary.travel_date }}</span>
    </div>
    <div v-if="response?.trip_summary.travel_days" class="summary-item">
      <span class="summary-label">行程天数</span>
      <span class="summary-value">{{ response.trip_summary.travel_days }} 天</span>
    </div>
    <div v-if="response?.trip_summary.travelers" class="summary-item">
      <span class="summary-label">出行人数</span>
      <span class="summary-value">{{ response.trip_summary.travelers }} 人</span>
    </div>
    <div v-if="response?.trip_summary.budget" class="summary-item">
      <span class="summary-label">预算</span>
      <span class="summary-value">¥ {{ response.trip_summary.budget.toLocaleString() }}</span>
    </div>
    <div v-if="response?.trip_summary.preferences.length" class="summary-item">
      <span class="summary-label">偏好</span>
      <span class="summary-value">{{ response.trip_summary.preferences.join('、') }}</span>
    </div>

    <div v-if="response?.retrieved_chunks" class="summary-item">
      <span class="summary-label">检索资料</span>
      <span class="summary-value">{{ response.retrieved_chunks }} 个片段</span>
    </div>

    <div v-if="response?.tools && response.tools.length > 0" class="summary-item">
      <span class="summary-label">工具调用</span>
      <span class="summary-value">
        <span
          v-for="tool in response.tools"
          :key="tool.name"
          class="tool-tag"
          :class="tool.success ? 'tool-tag--ok' : 'tool-tag--fail'"
        >
          {{ tool.name }}
        </span>
      </span>
    </div>
  </aside>
</template>

<style scoped>
.trip-summary {
  width: 240px;
  min-width: 240px;
  padding: 16px;
  border-left: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
  overflow-y: auto;
}

.summary-title {
  margin: 0 0 16px;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.summary-item {
  margin-bottom: 14px;
}

.summary-label {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin-bottom: 4px;
}

.summary-value {
  font-size: 13px;
  color: var(--el-text-color-regular);
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tool-tag {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
}

.tool-tag--ok {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}

.tool-tag--fail {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}

@media (max-width: 1024px) {
  .trip-summary {
    display: none;
  }
}
</style>
