import { defineStore } from 'pinia'
import { ref } from 'vue'

const API = import.meta.env.VITE_API_URL ?? '/api/'

export const useJournalStore = defineStore('journal', () => {
  const entries = ref([])
  const loading = ref(false)
	const inventoryItems = ref([])

	const foodLibrary = computed(() => {
		const library = {}
		entries.value
			.filter(e => e.metric_type === 'meal' && e.metric_data?.items)
			.flatMap(e => e.metric_data.items)
			.forEach(item => {
				if (!item.name || !item.qty) return
				library[item.name] = {
					cal_per_unit: item.calories != null ? item.calories / item.qty : null,
					pro_per_unit: item.protein != null ? item.protein / item.qty : null
				}
			})
		return library
	})

	async function fetchInventory() {
		const res = await fetch(`${API}/inventory`)
		inventoryItems.value = await res.json()
	}

	async function createInventoryItem(name, items) {
		await fetch(`${API}/inventory`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({name,items})
		})
		await fetchInventory()
	}

	async function deleteInventoryItem(id) {
		await fetch(`${API}/inventory/${id}`, { method: 'DELETE' })
		await fetchInventory()
	}

	async function consumeInventoryItem(id) {
		await fetch(`${API}/inventory/${id}/consume`, { method: 'POST' })
		await fetchInventory()
	}

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

  return { 
		entries, loading, API, 
		fetchEntries, submitEntry, deleteEntry, updateEntry,
		inventoryItems, fetchInventory, createInventoryItem, deleteInventoryItem, consumeInventoryItem
	}
})
