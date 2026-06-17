<template>
  <div class="metric-section">
    <div class="metric-header">
      <label class="field-label">metric</label>
      <select v-model="selectedType" @change="onTypeChange">
        <option value="">— none —</option>
        <option value="weight">weight</option>
        <option value="exercise">exercise</option>
        <option value="sleep_quality">sleep quality</option>
        <option value="meal">meal</option>
      </select>
    </div>

    <div v-if="selectedType && selectedType !== 'meal'" class="metric-fields">
      <div v-for="field in METRIC_TYPES[selectedType]" :key="field.key" class="metric-field-row">
        <label>{{ field.label }}</label>
        <Combobox
          v-if="field.combobox"
          v-model="fieldValues[field.key]"
          :options="comboOptions(selectedType, field.key)"
          :placeholder="field.placeholder"
					@update:modelValue="onExerciseNameChange"
        />
        <input
          v-else
          :type="field.type"
          v-model="fieldValues[field.key]"
          :placeholder="field.placeholder"
          step="any"
        />
      </div>
    </div>

    <div v-if="selectedType === 'meal'" class="metric-fields">
      <div v-for="(row, i) in mealRows" :key="i">
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
						<input type="number" v-model="row.qty" placeholder="1.0" step="any" @input="onQtyChanged(i)" />
					</div>
          <div class="metric-field-row">
            <label>calories</label>
            <input type="number" v-model="row.calories" placeholder="0" step="any" />
          </div>
          <div class="metric-field-row">
            <label>protein</label>
            <input type="number" v-model="row.protein" placeholder="0" step="any" />
          </div>
        </div>
        <button v-if="mealRows.length > 1" class="meal-remove-btn" @click="removeMealRow(i)">remove</button>
        <div v-if="i < mealRows.length - 1" class="meal-divider" />
      </div>
      <button class="meal-add-btn" @click="addMealRow">+ add item</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useJournalStore } from '../stores/journal'
import Combobox from './Combobox.vue'
import { useMealRows } from '../composables/useMealRows'

const store = useJournalStore()
const emit = defineEmits(['exerciseFilter'])

const METRIC_TYPES = {
  weight:        [{ key: 'value',    label: 'lb',       type: 'number', placeholder: '0.0' }],
  sleep_quality: [{ key: 'value',    label: 'quality',  type: 'number', placeholder: '1–5' }],
  exercise: [
    { key: 'name',   label: 'name', type: 'text',   placeholder: 'e.g. squat', combobox: true },
    { key: 'weight', label: 'lbs',   type: 'number', placeholder: '0.0' },
    { key: 'reps',   label: 'reps', type: 'number', placeholder: '0' }
  ]
}

const selectedType = ref('')
const fieldValues  = ref({})
const { rows: mealRows, addRow: addMealRow, removeRow: removeMealRow,
				onFoodNameSelected, onQtyChanged, collect: collectMeal, reset: resetMeal } = useMealRows()

function populate(type, data) {
	if (!type || !data) return
	selectedType.value = type

	if (type === 'meal' && data.items) {
		mealRows.value = data.items.map(item => ({
			name:     item.name     || '',
			qty:      item.qty      ?? '',
			calories: item.calories ?? '',
			protein:  item.protein ?? ''
		}))
	  return
	}

	const fields = METRIC_TYPES[type]
	if (!fields) return
	fields.forEach(field => {
		if (data[field.key] != null) {
			fieldValues.value[field.key] = data[field.key]
		}
	})
}

defineExpose({ collect, reset, populate })

function onTypeChange() {
	fieldValues.value = {}
	resetMeal()
	emit('exerciseFilter', '')
}

function onExerciseNameChange(val) {
	if (selectedType.value === 'exercise') {
		emit('exerciseFilter', val)
	}
}

function comboOptions(type, field) {
  return [...new Set(
    store.entries
      .filter(e => e.metric_type === type && e.metric_data?.[field])
      .map(e => e.metric_data[field])
  )]
}

const knownFoodItems = computed(() =>
  [...new Set(
    store.entries
      .filter(e => e.metric_type === 'meal' && e.metric_data?.items)
      .flatMap(e => e.metric_data.items.map(i => i.name).filter(Boolean))
  )]
)

function collect() {
  if (!selectedType.value) return { type: null, data: null }
  if (selectedType.value === 'meal') {
    const items = collectMeal()
    return items ? { type: 'meal', data: { items } } : { type: null, data: null }
  }
  const data = {}
  let hasValue = false
  METRIC_TYPES[selectedType.value].forEach(field => {
    const val = fieldValues.value[field.key]
    if (val !== undefined && val !== '') {
      data[field.key] = field.type === 'number' ? parseFloat(val) : val
      hasValue = true
    }
  })
  return hasValue ? { type: selectedType.value, data } : { type: null, data: null }
}

function reset() {
  selectedType.value = ''
  fieldValues.value  = {}
	resetMeal()
}

</script>

<style scoped>
.metric-section {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 1.5rem;
}
.metric-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.field-label {
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}
select {
  flex: 1; height: 36px;
  font-family: 'DM Mono', monospace; font-size: 12px;
  color: var(--color-text-primary);
  background: var(--color-bg);
  border: 0.5px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 0 28px 0 10px;
  outline: none; cursor: pointer;
  appearance: none; -webkit-appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23888780' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;
}
.metric-fields { display: flex; flex-direction: column; gap: 10px; }
.metric-field-row { display: flex; align-items: center; gap: 10px; }
.metric-field-row label {
  font-family: 'DM Mono', monospace; font-size: 11px;
  letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--color-text-muted); min-width: 48px;
}
input[type="number"], input[type="text"] {
  flex: 1; height: 38px;
  font-family: 'DM Mono', monospace; font-size: 15px; font-weight: 500;
  color: var(--color-text-primary); background: var(--color-bg);
  border: 0.5px solid var(--color-border); border-radius: var(--radius-md);
  padding: 0 12px; outline: none;
  -moz-appearance: textfield;
}
input[type="text"] { font-weight: 400; font-family: 'Lora', serif; }
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button { -webkit-appearance: none; }
input:focus { border-color: var(--color-border-strong); }
.meal-row-fields { display: flex; flex-direction: column; gap: 8px; }
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
.meal-add-btn:hover { background: var(--color-bg); color: var(--color-text-primary); }
.meal-remove-btn {
  font-family: 'DM Mono', monospace; font-size: 10px;
  letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--color-text-muted); background: transparent;
  border: none; cursor: pointer; padding: 4px 0; margin-top: 4px;
}
.meal-remove-btn:hover { color: var(--color-text-primary); }
</style>
