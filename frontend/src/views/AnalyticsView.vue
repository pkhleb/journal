<template>
  <div class="journal-wrap">
    <div class="journal-header">
      <h1 class="journal-title">analytics</h1>
      <router-link to="/" class="nav-link">journal</router-link>
    </div>

    <div class="chart-section">
      <p class="section-title">weight over time</p>
      <div v-if="weightData.length === 0" class="empty-state">
        no weight entries yet
      </div>
      <canvas v-else ref="weightChart" height="300"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Chart, LineController, LineElement, PointElement, LinearScale, TimeScale, Tooltip } from 'chart.js'
import 'chartjs-adapter-date-fns'
import { useJournalStore } from '../stores/journal'

Chart.register(LineController, LineElement, PointElement, LinearScale, TimeScale, Tooltip)

const store = useJournalStore()
const weightChart = ref(null)
let chartInstance = null

const weightData = computed(() =>
  store.entries
    .filter(e => e.metric_type === 'weight' && e.metric_data?.value != null)
    .map(e => ({
      x: new Date(e.created_at + 'Z'),
      y: e.metric_data.value
    }))
    .reverse()
)

function buildChart() {
  if (!weightChart.value || weightData.value.length === 0) return
  if (chartInstance) chartInstance.destroy()
  chartInstance = new Chart(weightChart.value, {
    type: 'line',
    data: {
      datasets: [{
        data: weightData.value,
        borderColor: '#1D9E75',
        backgroundColor: 'transparent',
        pointBackgroundColor: '#1D9E75',
        pointRadius: 4,
        tension: 0.3
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.parsed.y} kg`
          }
        }
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'day' },
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: '#888780', font: { family: 'DM Mono' } }
        },
        y: {
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: '#888780', font: { family: 'DM Mono' }, callback: v => `${v} lb` }
        }
      }
    }
  })
}

onMounted(async () => {
  await store.fetchEntries()
  buildChart()
})

watch(weightData, buildChart)
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
