<template>
  <div class="journal-wrap">
    <div class="journal-header">
      <h1 class="journal-title">activity</h1>
      <router-link to="/" class="nav-link">journal</router-link>
      <router-link to="/analytics" class="nav-link">analytics</router-link>
      <router-link to="/predictor" class="nav-link">predictor</router-link>
    </div>

    <div class="toggle">
      <button
        v-for="p in ['week', 'month']" :key="p"
        :class="['toggle-btn', { active: period === p }]"
        @click="period = p"
      >{{ p }}ly</button>
    </div>

    <div v-if="loading" class="empty-state">loading…</div>
    <div v-else-if="forbidden" class="empty-state">admin only</div>
    <div v-else-if="buckets.length === 0" class="empty-state">no posts yet</div>

    <template v-else>
      <div class="stat-grid">
        <div class="stat-tile">
          <p class="stat-value">{{ stats.thisPosts }}</p>
          <p class="stat-label">posts this {{ period }}</p>
        </div>
        <div class="stat-tile">
          <p class="stat-value">{{ stats.thisUsers }}</p>
          <p class="stat-label">active users this {{ period }}</p>
        </div>
        <div class="stat-tile">
          <p class="stat-value">{{ stats.avgPosts }}</p>
          <p class="stat-label">avg posts / {{ period }}</p>
        </div>
        <div class="stat-tile">
          <p class="stat-value">{{ stats.avgUsers }}</p>
          <p class="stat-label">avg users / {{ period }}</p>
        </div>
      </div>

      <div class="chart-section">
        <p class="section-title">total posts per {{ period }}</p>
        <canvas ref="postsChart" height="220"></canvas>
      </div>

      <div class="chart-section">
        <p class="section-title">users who posted per {{ period }}</p>
        <canvas ref="usersChart" height="220"></canvas>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import {
  Chart, BarController, BarElement, LinearScale, CategoryScale, Tooltip
} from 'chart.js'
import { apiFetch } from '../api'

Chart.register(BarController, BarElement, LinearScale, CategoryScale, Tooltip)

const prefersDark = () => window.matchMedia?.('(prefers-color-scheme: dark)').matches
const ACCENT = () => (prefersDark() ? '#97c459' : '#1D9E75')

const period = ref('week')
const buckets = ref([])
const loading = ref(true)
const forbidden = ref(false)

const postsChart = ref(null)
const usersChart = ref(null)
let postsInstance = null
let usersInstance = null

async function fetchActivity() {
  loading.value = true
  const res = await apiFetch(`/activity?period=${period.value}`)
  if (res.status === 403) {
    forbidden.value = true
    loading.value = false
    return
  }
  buckets.value = await res.json()
  loading.value = false
}

const stats = computed(() => {
  const b = buckets.value
  if (b.length === 0) return {}
  const last = b[b.length - 1]
  const avg = key => (b.reduce((s, x) => s + x[key], 0) / b.length).toFixed(1)
  return {
    thisPosts: last.posts,
    thisUsers: last.users,
    avgPosts: avg('posts'),
    avgUsers: avg('users'),
  }
})

// period_start is a plain date; parse as local so labels don't shift a day.
function label(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  return period.value === 'month'
    ? date.toLocaleDateString(undefined, { month: 'short', year: '2-digit' })
    : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function buildChart(canvas, existing, key, noun) {
  if (!canvas) return null
  if (existing) existing.destroy()
  return new Chart(canvas, {
    type: 'bar',
    data: {
      labels: buckets.value.map(b => label(b.period_start)),
      datasets: [{
        data: buckets.value.map(b => b[key]),
        backgroundColor: ACCENT(),
        borderRadius: 4,
        maxBarThickness: 32,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: items => `${period.value} of ${label(buckets.value[items[0].dataIndex].period_start)}`,
            label: ctx => `${ctx.parsed.y} ${noun}${ctx.parsed.y === 1 ? '' : 's'}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#888780', font: { family: 'DM Mono' }, maxRotation: 0, autoSkip: true },
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: '#888780', font: { family: 'DM Mono' }, precision: 0 },
        },
      },
    },
  })
}

async function buildAllCharts() {
  await nextTick()
  postsInstance = buildChart(postsChart.value, postsInstance, 'posts', 'post')
  usersInstance = buildChart(usersChart.value, usersInstance, 'users', 'user')
}

onMounted(async () => {
  await fetchActivity()
  await buildAllCharts()
})

watch(period, async () => {
  await fetchActivity()
  await buildAllCharts()
})
</script>

<style scoped>
.journal-wrap { max-width: 640px; margin: 0 auto; }
.journal-header {
  display: flex; align-items: baseline; gap: 12px;
  margin-bottom: 2rem;
  border-bottom: 0.5px solid var(--color-border);
  padding-bottom: 1rem;
}
.journal-title {
  font-family: 'Lora', serif; font-size: 22px;
  font-weight: 400; font-style: italic;
}
.nav-link {
  font-family: 'DM Mono', monospace; font-size: 11px;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--color-text-muted); margin-left: auto; text-decoration: none;
}
.nav-link ~ .nav-link { margin-left: 0; }
.nav-link:hover { color: var(--color-text-primary); }

.toggle { display: flex; gap: 8px; margin-bottom: 1.5rem; }
.toggle-btn {
  font-family: 'DM Mono', monospace; font-size: 11px;
  letter-spacing: 0.08em; text-transform: uppercase;
  background: none; cursor: pointer;
  color: var(--color-text-muted);
  border: 0.5px solid var(--color-border);
  border-radius: var(--radius-md); padding: 6px 12px;
}
.toggle-btn.active { color: var(--color-text-primary); border-color: var(--color-text-primary); }

.stat-grid {
  display: grid; grid-template-columns: repeat(2, 1fr);
  gap: 1px; background: var(--color-border);
  border: 0.5px solid var(--color-border);
  border-radius: var(--radius-md); overflow: hidden;
  margin-bottom: 2rem;
}
.stat-tile { background: var(--color-bg); padding: 1rem; }
.stat-value {
  font-family: 'DM Mono', monospace; font-size: 22px;
  color: var(--color-text-primary);
}
.stat-label {
  font-family: 'DM Mono', monospace; font-size: 10px;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--color-text-muted); margin-top: 4px;
}

.chart-section { margin-bottom: 2rem; }
.section-title {
  font-family: 'DM Mono', monospace; font-size: 11px;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--color-text-muted); margin-bottom: 1rem;
}
.empty-state {
  font-family: 'Lora', serif; font-style: italic;
  font-size: 14px; color: var(--color-text-muted);
  text-align: center; padding: 2rem 0;
}
</style>
