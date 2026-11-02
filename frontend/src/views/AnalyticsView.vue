<template>
  <div class="journal-wrap">
    <div class="journal-header">
      <h1 class="journal-title">analytics</h1>
      <router-link to="/" class="nav-link">journal</router-link>
      <router-link to="/predictor" class="nav-link">predictor</router-link>
      <router-link v-if="authStore.user?.is_admin" to="/activity" class="nav-link">activity</router-link>
    </div>

    <div class="date-filter">
      <div class="field-group">
        <label class="field-label" for="analytics-start-date">start date</label>
        <input id="analytics-start-date" v-model="startDate" type="date" class="date-input" />
      </div>

      <div class="field-group">
        <label class="field-label" for="analytics-end-date">end date</label>
        <input id="analytics-end-date" v-model="endDate" type="date" class="date-input" />
      </div>
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
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  Tooltip
} from 'chart.js'
import 'chartjs-adapter-date-fns'
import { useJournalStore } from '../stores/journal'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
Chart.register(LineController, LineElement, PointElement, LinearScale, TimeScale, Tooltip)

const store = useJournalStore()
const weightChart = ref(null)
const startDate = ref('')
const endDate = ref('')
let chartInstance = null

const weightData = computed(() => {
  const start = startDate.value ? new Date(`${startDate.value}T00:00:00`) : null
  const end = endDate.value ? new Date(`${endDate.value}T23:59:59.999`) : null

  return store.entries
    .filter(e => e.metric_type === 'weight' && e.metric_data?.value != null)
    .filter(e => {
      const date = new Date(e.created_at)
      if (start && date < start) return false
      if (end && date > end) return false
      return true
    })
    .map(e => ({
      x: new Date(e.created_at),
      y: e.metric_data.value
    }))
    .reverse()
})

function buildChart() {
  if (!weightChart.value || weightData.value.length === 0) {
    if (chartInstance) {
      chartInstance.destroy()
      chartInstance = null
    }
    return
  }

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
            label: ctx => `${ctx.parsed.y} lb`
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
          ticks: {
            color: '#888780',
            font: { family: 'DM Mono' },
            callback: v => `${v} lb`
          }
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

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }
})
</script>

<style scoped>
.journal-wrap {
  max-width: 640px;
  margin: 0 auto;
}

.journal-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 2rem;
  border-bottom: 0.5px solid var(--color-border);
  padding-bottom: 1rem;
}

.journal-title {
  font-family: 'Lora', serif;
  font-size: 22px;
  font-weight: 400;
  font-style: italic;
}

.nav-link {
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  margin-left: auto;
  text-decoration: none;
}

.nav-link:hover {
  color: var(--color-text-primary);
}

.date-filter {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.field-group {
  margin: 0;
}

.field-label {
  display: block;
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  margin-bottom: 8px;
}

.date-input {
  width: 100%;
  background: transparent;
  border: 0.5px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-primary);
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  padding: 0.7rem 0.8rem;
}

.chart-section {
  margin-bottom: 2rem;
}

.section-title {
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  margin-bottom: 1rem;
}

.empty-state {
  font-family: 'Lora', serif;
  font-style: italic;
  font-size: 14px;
  color: var(--color-text-muted);
  text-align: center;
  padding: 2rem 0;
}

@media (max-width: 520px) {
  .date-filter {
    grid-template-columns: 1fr;
  }
}
</style>
