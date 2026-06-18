<template>
  <div class="journal-wrap">
    <div class="journal-header">
      <h1 class="journal-title">inventory</h1>
      <router-link to="/" class="nav-link">journal</router-link>
    </div>

    <div class="field-group">
      <label class="field-label">meal name</label>
      <input type="text" v-model="mealName" placeholder="e.g. chicken and rice batch" />
    </div>

    <div class="meal-rows">
      <div v-for="(row, i) in rows" :key="i">
        <div class="meal-row-fields">
          <div class="metric-field-row">
            <label>item</label>
            <Combobox
              v-model="row.name"
              :options="knownFoodItems"
              placeholder="e.g. chicken"
							@update:modelValue="onFoodNameSelected(i)"
            />
          </div>
					<div class="metric-field-row">
						<label>qty</label>
            <input type="number" v-model="row.qty" placeholder="1.0" @input = "onQtyChanged(i)" step="any" />
					</div>
          <div class="metric-field-row">
            <label>calories</label>
            <input type="number" v-model="row.calories" placeholder="0" step="any" />
          </div>
          <div class="metric-field-row">
            <label>protein</label>
            <input type="number" v-model="row.protein" placeholder="0" step="any" />
          </div>
					<div class="metric-field-row">
						<label>caffeine</label>
						<input type="number" v-model="row.caffeine" placeholder="0" step="any" />
					</div>
        </div>
        <button v-if="rows.length > 1" class="meal-remove-btn" @click="removeRow(i)">remove</button>
        <div v-if="i < rows.length - 1" class="meal-divider" />
      </div>
      <button class="meal-add-btn" @click="addRow">+ add item</button>
    </div>

    <div class="submit-row">
      <button class="submit-btn" @click="save">Save to inventory</button>
      <span class="toast" :class="{ show: toastVisible }">saved</span>
    </div>

    <div v-if="store.inventoryItems.length" class="entries-section">
      <p class="entries-title">prepped meals</p>
      <div v-for="item in store.inventoryItems" :key="item.id" class="entry-card">
        <div class="entry-meta">
          <span class="entry-name">{{ item.name }}</span>
          <span class="entry-ts">{{ formatDate(item.created_at) }}</span>
        </div>
        <div class="entry-metric-data">
          <div v-for="food in item.items" :key="food.name" class="metric-chip">
            <span>item</span>{{ food.name }}
            <template v-if="food.calories != null"><span style="margin-left:6px;">cal</span>{{ food.calories }}</template>
            <template v-if="food.protein != null"><span style="margin-left:6px;">pro</span>{{ food.protein }}</template>
						<template v-if="food.caffeine != null"><span style="margin-left:6px;">caf</span>{{ food.caffeine }}</template>
          </div>
          <div class="metric-chip totals">
            <span>total cal</span>{{ totalCalories(item) }}
            <span style="margin-left:6px;">pro</span>{{ totalProtein(item) }}
						<span style="margin-left:6px;">caf</span>{{ totalCaffeine(item) }}
          </div>
        </div>
        <div class="entry-actions">
          <button class="action-btn consume" @click="consume(item.id)">consume</button>
          <button class="action-btn danger" @click="remove(item.id)">delete</button>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">
      no prepped meals yet
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useJournalStore } from '../stores/journal'
import Combobox from '../components/Combobox.vue'
import { useMealRows } from '../composables/useMealRows'

const { rows, addRow, removeRow, onFoodNameSelected, onQtyChanged, collect: collectMeal, reset: resetMeal } = useMealRows()

const store = useJournalStore()

const mealName = ref('')
const toastVisible = ref(false)

onMounted(() => {
  store.fetchInventory()
  store.fetchEntries()
})

const knownFoodItems = computed(() =>
  [...new Set(
    store.entries
      .filter(e => e.metric_type === 'meal' && e.metric_data?.items)
      .flatMap(e => e.metric_data.items.map(i => i.name).filter(Boolean))
  )]
)

async function save() {
  if (!mealName.value.trim()) return
  const items = collectMeal()
  if (!items) return
  await store.createInventoryItem(mealName.value.trim(), items)
  mealName.value = ''
	resetMeal()
  toastVisible.value = true
  setTimeout(() => toastVisible.value = false, 1800)
}

async function consume(id) {
  await store.consumeInventoryItem(id)
  toastVisible.value = true
  setTimeout(() => toastVisible.value = false, 1800)
}

async function remove(id) {
  if (!confirm('Delete this prepped meal?')) return
  await store.deleteInventoryItem(id)
}

function totalCalories(item) {
  return item.items.reduce((s, i) => s + (i.calories || 0), 0)
}

function totalProtein(item) {
  return item.items.reduce((s, i) => s + (i.protein || 0), 0)
}

function totalCaffeine(item) {
	return item.items.reduce((s, i) => s + (i.caffeine || 0), 0)
}

function formatDate(ts) {
  return new Date(ts).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric'
  })
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
.nav-link {
  font-family: 'DM Mono', monospace; font-size: 11px;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--color-text-muted); margin-left: auto;
  text-decoration: none;
}
.nav-link:hover { color: var(--color-text-primary); }
.field-group { margin-bottom: 1.5rem; }
.field-label {
  display: block; font-family: 'DM Mono', monospace;
  font-size: 11px; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--color-text-muted); margin-bottom: 8px;
}
input[type="text"], input[type="number"] {
  width: 100%; height: 38px;
  font-family: 'Lora', serif; font-size: 15px;
  color: var(--color-text-primary); background: var(--color-bg);
  border: 0.5px solid var(--color-border); border-radius: var(--radius-md);
  padding: 0 12px; outline: none; transition: border-color 0.15s;
  -moz-appearance: textfield;
}
input[type="number"] { font-family: 'DM Mono', monospace; font-weight: 500; }
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button { -webkit-appearance: none; }
input:focus { border-color: var(--color-border-strong); }
input::placeholder { color: var(--color-text-muted); font-size: 13px; }
.meal-rows { margin-bottom: 1.5rem; }
.meal-row-fields { display: flex; flex-direction: column; gap: 8px; }
.metric-field-row { display: flex; align-items: center; gap: 10px; }
.metric-field-row label {
  font-family: 'DM Mono', monospace; font-size: 11px;
  letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--color-text-muted); min-width: 48px;
}
.metric-field-row input { width: auto; }
.meal-divider { height: 0.5px; background: var(--color-border); margin: 10px 0; }
.meal-add-btn {
  margin-top: 10px; width: 100%;
  font-family: 'DM Mono', monospace; font-size: 11px;
  letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--color-text-muted); background: transparent;
  border: 0.5px dashed var(--color-border-strong);
  border-radius: var(--radius-md); padding: 8px 16px; cursor: pointer;
  transition: background 0.12s, color 0.12s;
}
.meal-add-btn:hover { background: var(--color-surface); color: var(--color-text-primary); }
.meal-remove-btn {
  font-family: 'DM Mono', monospace; font-size: 10px;
  letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--color-text-muted); background: transparent;
  border: none; cursor: pointer; padding: 4px 0; margin-top: 4px;
}
.meal-remove-btn:hover { color: var(--color-text-primary); }
.submit-row { display: flex; align-items: center; gap: 12px; margin-bottom: 1.5rem; }
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
.entry-card {
  background: var(--color-surface); border-radius: var(--radius-lg);
  padding: 14px 16px; margin-bottom: 10px;
}
.entry-meta {
  display: flex; justify-content: space-between;
  align-items: center; margin-bottom: 8px;
}
.entry-name {
  font-family: 'Lora', serif; font-size: 15px; font-style: italic;
  color: var(--color-text-primary);
}
.entry-ts {
  font-family: 'DM Mono', monospace; font-size: 11px; color: var(--color-text-muted);
}
.entry-metric-data { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.metric-chip {
  font-family: 'DM Mono', monospace; font-size: 12px;
  color: var(--color-text-secondary); background: var(--color-bg);
  border: 0.5px solid var(--color-border); border-radius: var(--radius-md); padding: 4px 10px;
}
.metric-chip span {
  color: var(--color-text-muted); font-size: 10px;
  margin-right: 4px; text-transform: uppercase; letter-spacing: 0.05em;
}
.metric-chip.totals { margin-left: auto; }
.entry-actions {
  display: flex; gap: 8px; margin-top: 10px;
  padding-top: 10px; border-top: 0.5px solid var(--color-border);
}
.action-btn {
  font-family: 'DM Mono', monospace; font-size: 10px;
  letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--color-text-muted); background: transparent;
  border: none; cursor: pointer; padding: 2px 0; transition: color 0.12s;
}
.action-btn:hover { color: var(--color-text-primary); }
.action-btn.danger:hover { color: #e24b4a; }
.action-btn.consume:hover { color: var(--color-success); }
.empty-state {
  font-family: 'Lora', serif; font-style: italic;
  font-size: 14px; color: var(--color-text-muted);
  text-align: center; padding: 2rem 0;
}
</style>
