<template>
  <div class="entry-card">
    <div class="entry-meta">
      <span class="entry-ts">{{ dateStr }} · {{ timeStr }}</span>
      <span v-if="entry.metric_type" class="entry-type-badge">{{ entry.metric_type.replace('_', ' ') }}</span>
    </div>

    <div v-if="entry.metric_type && entry.metric_data" class="entry-metric-data">
      <template v-if="entry.metric_type === 'meal'">
        <div v-for="item in entry.metric_data.items" :key="item.name" class="metric-chip">
          <span>item</span>{{ item.name }}
          <template v-if="item.calories != null"><span style="margin-left:6px;">cal</span>{{ item.calories }}</template>
          <template v-if="item.protein != null"><span style="margin-left:6px;">pro</span>{{ item.protein }}</template>
        </div>
        <div class="metric-chip totals">
          <span>total cal</span>{{ totalCalories }}
          <span style="margin-left:6px;">pro</span>{{ totalProtein }}
        </div>
      </template>
      <template v-else>
        <div v-for="(val, key) in entry.metric_data" :key="key" class="metric-chip">
          <span>{{ key }}</span>{{ val }}
        </div>
      </template>
    </div>

    <p v-if="entry.prose" class="entry-prose">{{ entry.prose }}</p>

    <div class="entry-actions">
      <button class="action-btn" @click="$emit('edit', entry)">edit</button>
      <button class="action-btn danger" @click="$emit('delete', entry.id)">delete</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  entry: { type: Object, required: true }
})

defineEmits(['edit', 'delete'])

const d = computed(() => new Date(props.entry.created_at + 'Z'))

const dateStr = computed(() =>
  d.value.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
)
const timeStr = computed(() =>
  d.value.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
)

const totalCalories = computed(() =>
  props.entry.metric_data?.items?.reduce((s, i) => s + (i.calories || 0), 0) ?? 0
)
const totalProtein = computed(() =>
  props.entry.metric_data?.items?.reduce((s, i) => s + (i.protein || 0), 0) ?? 0
)
</script>

<style scoped>
.entry-card {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  padding: 14px 16px;
  margin-bottom: 10px;
  animation: fadeIn 0.25s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.entry-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.entry-ts {
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: var(--color-text-muted);
}
.entry-type-badge {
  font-family: 'DM Mono', monospace;
  font-size: 11px; font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-bg);
  border: 0.5px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 3px 10px;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.entry-metric-data {
  display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;
}
.metric-chip {
  font-family: 'DM Mono', monospace; font-size: 12px;
  color: var(--color-text-secondary);
  background: var(--color-bg);
  border: 0.5px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 4px 10px;
}
.metric-chip span {
  color: var(--color-text-muted); font-size: 10px;
  margin-right: 4px; text-transform: uppercase; letter-spacing: 0.05em;
}
.metric-chip.totals { margin-left: auto; }
.entry-prose {
  font-family: 'Lora', serif; font-size: 14px;
  line-height: 1.7; color: var(--color-text-primary);
  font-style: italic; margin-top: 6px;
}
.entry-actions {
  display: flex; gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 0.5px solid var(--color-border);
}
.action-btn {
  font-family: 'DM Mono', monospace; font-size: 10px;
  letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--color-text-muted); background: transparent;
  border: none; cursor: pointer; padding: 2px 0;
  transition: color 0.12s;
}
.action-btn:hover { color: var(--color-text-primary); }
.action-btn.danger:hover { color: #e24b4a; }
</style>
