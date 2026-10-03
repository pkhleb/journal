<template>
  <div class="journal-wrap">
    <div class="journal-header">
      <h1 class="journal-title">predictor</h1>
      <router-link to="/" class="nav-link">journal</router-link>
      <router-link to="/analytics" class="nav-link">analytics</router-link>
    </div>

    <div v-if="loading" class="empty-state">loading…</div>

    <template v-else-if="events.length === 0">
      <div class="empty-state">no predictions yet</div>
    </template>

    <template v-else>
      <div class="stat-grid">
        <div class="stat-tile">
          <p class="stat-value">{{ stats.total }}</p>
          <p class="stat-label">predictions</p>
        </div>
        <div class="stat-tile">
          <p class="stat-value">{{ stats.hitRatePct }}</p>
          <p class="stat-label">top-3 hit rate</p>
        </div>
        <div class="stat-tile">
          <p class="stat-value">{{ stats.avgRank }}</p>
          <p class="stat-label">avg rank (of chosen)</p>
        </div>
        <div class="stat-tile">
          <p class="stat-value">{{ stats.avgLatency }}</p>
          <p class="stat-label">avg latency</p>
        </div>
      </div>

      <div class="chart-section">
        <p class="section-title">cumulative hit rate</p>
        <div v-if="hitRateSeries.length === 0" class="empty-state">no resolved predictions yet</div>
        <canvas v-else ref="hitRateChart" height="220"></canvas>
      </div>

      <div class="chart-section">
        <p class="section-title">rank of chosen exercise</p>
        <div v-if="rankCounts.total === 0" class="empty-state">no resolved predictions yet</div>
        <canvas v-else ref="rankChart" height="220"></canvas>
      </div>

      <div class="chart-section">
        <p class="section-title">prediction latency</p>
        <canvas ref="latencyChart" height="220"></canvas>
      </div>

      <div class="chart-section">
        <p class="section-title">feature weight evolution</p>
        <div v-if="weightSeries.labels.length === 0" class="empty-state">weights haven't updated yet</div>
        <canvas v-else ref="weightChart" height="260"></canvas>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import {
  Chart, LineController, BarController, LineElement, BarElement,
  PointElement, LinearScale, CategoryScale, TimeScale, Tooltip, Legend
} from 'chart.js'
import 'chartjs-adapter-date-fns'
import { apiFetch } from '../api'

Chart.register(
  LineController, BarController, LineElement, BarElement,
  PointElement, LinearScale, CategoryScale, TimeScale, Tooltip, Legend
)

// Categorical slots 1-5 from the validated default palette (dataviz skill) —
// passes adjacent-pair CVD/contrast checks for a line chart in both modes.
const FEATURE_COLORS = {
  transition:        { light: '#2a78d6', dark: '#3987e5' },
  phase_transition:  { light: '#eb6834', dark: '#d95926' },
  weekday:           { light: '#1baf7a', dark: '#199e70' },
  position_freq:     { light: '#eda100', dark: '#c98500' },
  recency:           { light: '#e87ba4', dark: '#d55181' },
}
const FEATURE_ORDER = ['transition', 'phase_transition', 'weekday', 'position_freq', 'recency']

const prefersDark = () => window.matchMedia?.('(prefers-color-scheme: dark)').matches
const seriesColor = (feature) => FEATURE_COLORS[feature][prefersDark() ? 'dark' : 'light']
const ACCENT = () => (prefersDark() ? '#97c459' : '#1D9E75')

const events = ref([])
const loading = ref(true)

const hitRateChart = ref(null)
const rankChart = ref(null)
const latencyChart = ref(null)
const weightChart = ref(null)
let hitRateInstance = null
let rankInstance = null
let latencyInstance = null
let weightInstance = null

async function fetchMetrics() {
  loading.value = true
  const res = await apiFetch('/predictor/metrics')
  events.value = await res.json()
  loading.value = false
}

// Resolved, non-stale events carry a trustworthy hit/rank verdict — a stale
// event was resolved without ever being scored against the live choice.
const resolvedEvents = computed(() =>
  events.value
    .filter(e => e.resolved && e.data?.hit != null && !e.data?.stale)
    .slice()
    .sort((a, b) => new Date(a.resolved_at) - new Date(b.resolved_at))
)

const stats = computed(() => {
  const total = events.value.length
  const resolved = resolvedEvents.value
  const hits = resolved.filter(e => e.data.hit).length
  const hitRatePct = resolved.length
    ? `${Math.round((hits / resolved.length) * 100)}%`
    : '—'
  const ranks = resolved.map(e => e.data.rank).filter(r => r != null)
  const avgRank = ranks.length
    ? (ranks.reduce((a, b) => a + b, 0) / ranks.length + 1).toFixed(2)
    : '—'
  const latencies = events.value.map(e => e.latency_ms).filter(l => l != null)
  const avgLatency = latencies.length
    ? `${Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length)} ms`
    : '—'
  return { total, hitRatePct, avgRank, avgLatency }
})

// Running hit rate as predictions accumulate, rather than a per-day rate
// that's mostly noise at low volume.
const hitRateSeries = computed(() => {
  let hits = 0
  return resolvedEvents.value.map((e, i) => {
    if (e.data.hit) hits += 1
    return { x: new Date(e.resolved_at), y: (hits / (i + 1)) * 100 }
  })
})

const rankCounts = computed(() => {
  const buckets = { '1st': 0, '2nd': 0, '3rd': 0, '4th+': 0 }
  for (const e of resolvedEvents.value) {
    const r = e.data.rank
    if (r === 0) buckets['1st']++
    else if (r === 1) buckets['2nd']++
    else if (r === 2) buckets['3rd']++
    else buckets['4th+']++
  }
  const total = Object.values(buckets).reduce((a, b) => a + b, 0)
  return { buckets, total }
})

const latencySeries = computed(() =>
  events.value
    .filter(e => e.latency_ms != null)
    .slice()
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
    .map(e => ({ x: new Date(e.created_at), y: e.latency_ms }))
)

// Each feature's weight right after an update that changed it — the
// natural x-axis for "how did the model evolve", skipping hits that left
// weights untouched.
const weightSeries = computed(() => {
  const updates = resolvedEvents.value.filter(e => e.data.updated && e.data.weights_after)
  const labels = updates.map(e => new Date(e.resolved_at))
  const byFeature = {}
  for (const feature of FEATURE_ORDER) {
    byFeature[feature] = updates.map(e => e.data.weights_after[feature])
  }
  return { labels, byFeature }
})

function buildHitRateChart() {
  if (!hitRateChart.value || hitRateSeries.value.length === 0) return
  if (hitRateInstance) hitRateInstance.destroy()
  hitRateInstance = new Chart(hitRateChart.value, {
    type: 'line',
    data: {
      datasets: [{
        data: hitRateSeries.value,
        borderColor: ACCENT(),
        backgroundColor: 'transparent',
        pointRadius: 0,
        borderWidth: 2,
        tension: 0.2,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => `${ctx.parsed.y.toFixed(1)}% cumulative hit rate` } },
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'day' },
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: '#888780', font: { family: 'DM Mono' } },
        },
        y: {
          min: 0, max: 100,
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: '#888780', font: { family: 'DM Mono' }, callback: v => `${v}%` },
        },
      },
    },
  })
}

function buildRankChart() {
  if (!rankChart.value || rankCounts.value.total === 0) return
  if (rankInstance) rankInstance.destroy()
  const { buckets } = rankCounts.value
  rankInstance = new Chart(rankChart.value, {
    type: 'bar',
    data: {
      labels: Object.keys(buckets),
      datasets: [{
        data: Object.values(buckets),
        backgroundColor: ACCENT(),
        borderRadius: 4,
        maxBarThickness: 48,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => `${ctx.parsed.y} prediction${ctx.parsed.y === 1 ? '' : 's'}` } },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#888780', font: { family: 'DM Mono' } },
        },
        y: {
          beginAtZero: true,
          ticks: { color: '#888780', font: { family: 'DM Mono' }, precision: 0 },
          grid: { color: 'rgba(0,0,0,0.06)' },
        },
      },
    },
  })
}

function buildLatencyChart() {
  if (!latencyChart.value || latencySeries.value.length === 0) return
  if (latencyInstance) latencyInstance.destroy()
  latencyInstance = new Chart(latencyChart.value, {
    type: 'line',
    data: {
      datasets: [{
        data: latencySeries.value,
        borderColor: ACCENT(),
        backgroundColor: 'transparent',
        pointRadius: 2,
        pointBackgroundColor: ACCENT(),
        borderWidth: 1.5,
        tension: 0.15,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => `${ctx.parsed.y.toFixed(1)} ms` } },
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'day' },
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: '#888780', font: { family: 'DM Mono' } },
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: '#888780', font: { family: 'DM Mono' }, callback: v => `${v} ms` },
        },
      },
    },
  })
}

function buildWeightChart() {
  if (!weightChart.value || weightSeries.value.labels.length === 0) return
  if (weightInstance) weightInstance.destroy()
  const { labels, byFeature } = weightSeries.value
  weightInstance = new Chart(weightChart.value, {
    type: 'line',
    data: {
      labels,
      datasets: FEATURE_ORDER.map(feature => ({
        label: feature.replace('_', ' '),
        data: byFeature[feature],
        borderColor: seriesColor(feature),
        backgroundColor: 'transparent',
        pointRadius: 0,
        borderWidth: 2,
        tension: 0.2,
      })),
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#888780', font: { family: 'DM Mono', size: 10 }, boxWidth: 12 },
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(3)}` },
        },
      },
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'day' },
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: '#888780', font: { family: 'DM Mono' } },
        },
        y: {
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: '#888780', font: { family: 'DM Mono' } },
        },
      },
    },
  })
}

function buildAllCharts() {
  buildHitRateChart()
  buildRankChart()
  buildLatencyChart()
  buildWeightChart()
}

onMounted(async () => {
  await fetchMetrics()
  await nextTick()
  buildAllCharts()
})

watch([hitRateSeries, rankCounts, latencySeries, weightSeries], async () => {
  await nextTick()
  buildAllCharts()
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
.nav-link:hover { color: var(--color-text-primary); }

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
