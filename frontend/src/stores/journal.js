import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiFetch } from '../api'

const API = import.meta.env.VITE_API_URL ?? '/api/'

export const useJournalStore = defineStore('journal', () => {
  const entries = ref([])
  const loading = ref(false)
	const inventoryItems = ref([])

	const foodLibrary = computed(() => {
		const library = {}
		const mealEntries = entries.value
			.filter(e => e.metric_type === 'meal' && e.metric_data?.items)
		  .slice()
		  .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
		mealEntries
			.flatMap(e => e.metric_data.items)
			.forEach(item => {
				if (!item.name || !item.qty) return
				library[item.name] = {
					cal_per_unit: item.calories != null ? item.calories / item.qty : null,
					pro_per_unit: item.protein != null ? item.protein / item.qty : null,
					caf_per_unit: item.caffeine != null ? item.caffeine / item.qty : null
				}
			})
		return library
	})

	async function fetchInventory() {
		const res = await apiFetch(`/inventory`)
		inventoryItems.value = await res.json()
	}

	async function createInventoryItem(name, items) {
		await apiFetch(`/inventory`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({name,items})
		})
		await fetchInventory()
	}

	async function deleteInventoryItem(id) {
		await apiFetch(`/inventory/${id}`, { method: 'DELETE' })
		await fetchInventory()
	}

	async function consumeInventoryItem(id) {
		await apiFetch(`/inventory/${id}/consume`, { method: 'POST' })
		await fetchEntries()
		await fetchInventory()
	}

  async function fetchEntries() {
    loading.value = true
    const res = await apiFetch(`/entries`)
    entries.value = await res.json()
    loading.value = false
  }

  async function submitEntry(prose, metricType, metricData) {
    if (!prose && !metricType) return
    await apiFetch(`/entries`, {
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
    await apiFetch(`/entries/${id}`, { method: 'DELETE' })
    await fetchEntries()
  }

  async function updateEntry(id, prose, metricType, metricData) {
    await apiFetch(`/entries/${id}`, {
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

  return { 
		entries, loading, API, foodLibrary,
		fetchEntries, submitEntry, deleteEntry, updateEntry,
		inventoryItems, fetchInventory, createInventoryItem, deleteInventoryItem, consumeInventoryItem
	}
})
