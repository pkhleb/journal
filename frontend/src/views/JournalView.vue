<template>
  <div class="journal-wrap">
    <div class="journal-header">
      <h1 class="journal-title">journal</h1>
			<router-link to="/inventory" class="nav-link">inventory</router-link>
			<router-link to="/analytics" class="nav-link">analytics</router-link>
      <span class="journal-date">{{ todayStr }}</span>
    </div>

		<div v-if="todaysSummary.calories > 0 || todaysSummary.protein > 0" class="daily-summary">
			<span>today</span>
			<span>{{ todaysSummary.calories }} cal · {{ todaysSummary.protein }}g protein</span>
		</div>
    <div class="field-group">
      <label class="field-label">entry</label>
      <textarea
        v-model="prose"
        placeholder="Write something…"
        @keydown.meta.enter="submit"
        @keydown.ctrl.enter="submit"
      />
    </div>

    <MetricFields ref="metricFields" />

    <div class="submit-row">
      <button class="submit-btn" @click="submit">Save entry</button>
      <button class="submit-btn" @click="exportDb">Export db</button>
      <span class="toast" :class="{ show: toastVisible }">saved</span>
    </div>

    <div v-if="store.entries.length" class="entries-section">
      <p class="entries-title">entries</p>
      <EntryCard
        v-for="entry in store.entries"
        :key="entry.id"
        :entry="entry"
        @edit="startEdit"
        @delete="deleteEntry"
      />
    </div>

    <div v-if="editingEntry" class="modal-backdrop" @click.self="cancelEdit">
      <div class="modal">
        <p class="modal-title">edit entry</p>
        <div class="field-group">
          <label class="field-label">entry</label>
          <textarea v-model="editProse" placeholder="Write something…" />
        </div>
        <MetricFields ref="editMetricFields" />
        <div class="modal-actions">
          <button class="submit-btn" @click="saveEdit">Save</button>
          <button class="submit-btn" @click="cancelEdit">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { useJournalStore } from '../stores/journal'
import MetricFields from '../components/MetricFields.vue'
import EntryCard from '../components/EntryCard.vue'

const store = useJournalStore()
const prose = ref('')
const toastVisible = ref(false)
const metricFields = ref(null)
const editingEntry = ref(null)
const editProse = ref('')
const editMetricFields = ref(null)

const todaysSummary = computed(() => {
	const today = new Date().toDateString()
	const todaysEntries = store.entries.filter( e =>
		new Date(e.created_at + 'Z').toDateString() === today
	)
	let calories = 0
	let protein = 0

	todaysEntries.forEach(e => {
		if (e.metric_type === 'meal' && e.metric_data?.items) {
			e.metric_data.items.forEach(item => {
				calories += item.calories || 0
				protein += item.protein || 0
			})
		}
	})

	return { calories: Math.round(calories), protein: Math.round(protein) }
})

const todayStr = new Date().toLocaleDateString('en-US', {
  weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
})

onMounted(() => store.fetchEntries())

async function submit() {
  const { type, data } = metricFields.value.collect()
  if (!prose.value.trim() && !type) return
  await store.submitEntry(prose.value.trim(), type, data)
  prose.value = ''
  metricFields.value.reset()
  toastVisible.value = true
  setTimeout(() => toastVisible.value = false, 1800)
}

async function deleteEntry(id) {
  if (!confirm('Delete this entry?')) return
  await store.deleteEntry(id)
}

async function startEdit(entry) {
  editingEntry.value = entry
  editProse.value = entry.prose || ''
	await nextTick()
	if (entry.metric_type && entry.metric_data) {
		editMetricFields.value.populate(entry.metric_type, entry.metric_data)
	}
}

function cancelEdit() {
  editingEntry.value = null
  editProse.value = ''
}

async function saveEdit() {
  const { type, data } = editMetricFields.value.collect()
  await store.updateEntry(editingEntry.value.id, editProse.value.trim(), type, data)
  cancelEdit()
}

function exportDb() {
  window.location.href = `${store.API}/export/db`
}
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
.journal-date {
  font-family: 'DM Mono', monospace; font-size: 11px;
  color: var(--color-text-muted); letter-spacing: 0.08em;
  text-transform: uppercase; margin-left: auto;
}
.daily-summary {
	display: flex;
	justify-content: space-between;
	font-family: 'DM Mono', monospace;
	font-size: 12px;
	color: var(--color-text-muted);
	margin-bottom: 1.5rem;
	padding-bottom: 1rem;
	border-bottom: 0.5px solid var(--color-border);
}
.field-group { margin-bottom: 1.5rem; }
.field-label {
  display: block; font-family: 'DM Mono', monospace;
  font-size: 11px; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--color-text-muted); margin-bottom: 8px;
}
textarea {
  width: 100%; min-height: 180px; resize: vertical;
  font-family: 'Lora', serif; font-size: 16px; line-height: 1.75;
  color: var(--color-text-primary); background: var(--color-bg);
  border: 0.5px solid var(--color-border); border-radius: var(--radius-lg);
  padding: 14px 16px; outline: none; transition: border-color 0.15s;
}
textarea:focus { border-color: var(--color-border-strong); }
textarea::placeholder { color: var(--color-text-muted); font-style: italic; }
.submit-row {
  display: flex; align-items: center; gap: 12px; position: relative;
}
.submit-btn {
  height: 44px; padding: 0 24px;
  font-family: 'DM Mono', monospace; font-size: 12px;
  letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--color-text-primary); background: transparent;
  border: 0.5px solid var(--color-border-strong);
  border-radius: var(--radius-md); cursor: pointer;
  transition: background 0.12s, transform 0.1s;
}
.submit-btn:hover { background: var(--color-surface); }
.submit-btn:active { transform: scale(0.97); }
.toast {
  font-family: 'DM Mono', monospace; font-size: 11px;
  color: var(--color-success); opacity: 0; transition: opacity 0.2s;
}
.toast.show { opacity: 1; }
.entries-section {
  margin-top: 2.5rem; border-top: 0.5px solid var(--color-border); padding-top: 1.5rem;
}
.entries-title {
  font-family: 'DM Mono', monospace; font-size: 11px;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--color-text-muted); margin-bottom: 1rem;
}
.modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center;
  z-index: 100; padding: 1rem;
}
.modal {
  background: var(--color-bg);
  border-radius: var(--radius-lg);
  border: 0.5px solid var(--color-border-strong);
  padding: 1.5rem; width: 100%; max-width: 560px;
  max-height: 90vh; overflow-y: auto;
}
.modal-title {
  font-family: 'DM Mono', monospace; font-size: 11px;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--color-text-muted); margin-bottom: 1.5rem;
}
.modal-actions { display: flex; gap: 12px; margin-top: 1rem; }

.nav-link {
  font-family: 'DM Mono', monospace; font-size: 11px;
	letter-spacing: 0.08em; text-transform: uppercase;
	color: var(--color-text-muted); text-decoration: none;
}

.nav-link:hover { color: var(--color-text-primary); }

</style>
