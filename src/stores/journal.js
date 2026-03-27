import { defineStore } from 'pinia'
import { ref } from 'vue'

const API = import.meta.env.VITE_API_URL ?? ''

export const useJournalStore = defineStore('journal', () => {
  const entries = ref([])
  const loading = ref(false)

  async function fetchEntries() {
    loading.value = true
    const res = await fetch(`${API}/entries`)
    entries.value = await res.json()
    loading.value = false
  }

  async function submitEntry(prose, metricType, metricData) {
    if (!prose && !metricType) return
    await fetch(`${API}/entries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prose: prose || null,
        metric_type: metricType || null,
        metric_data: metricData || null
      })
    })
    await fetchEntries()
  }

  async function deleteEntry(id) {
    await fetch(`${API}/entries/${id}`, { method: 'DELETE' })
    await fetchEntries()
  }

  async function updateEntry(id, prose, metricType, metricData) {
    await fetch(`${API}/entries/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prose: prose || null,
        metric_type: metricType || null,
        metric_data: metricData || null
      })
    })
    await fetchEntries()
  }

  return { entries, loading, API, fetchEntries, submitEntry, deleteEntry, updateEntry }
})
