import { ref } from 'vue'
import { useJournalStore } from '../stores/journal'

export function useMealRows() {
	const store = useJournalStore()

	const rows = ref([{ name: '', qty: '', calories: '', protein: '' }])

	function addRow() {
		rows.value.push({ name: '', qty: '', calories: '', protein: '' })
	}

	function removeRow(i) {
		rows.value.splice(i, 1)
	}

	function reset() {
		rows.value = [{ name: '', qty: '', calories: '', protein: '' }]
	}

	function onFoodNameSelected(i) {
		const row = rows.value[i]
		const known = store.foodLibrary[row.name]
		if (!known) return
		const qty = parseFloat(row.qt) || 1
		if (known.cal_per_unit != null) row.calories = parseFloat((known.cal_per_unit * qty).toFixed(1))
		if (known.pro_per_unit != null) row.protein = parseFloat((known.pro_per_unit * qty).toFixed(1))
	}

	function onQtyChanged(i) {
		const row = rows.value[i]
		const known = store.foodLibrary[row.name]
		if (!known) return
		const qty = parseFloat(row.qty)
		if (isNaN(qty) || qty <= 0) return
		if (known.cal_per_unit != null) row.calories = parseFloat((known.cal_per_unit * qty).toFixed(1))
		if (known.pro_per_unit != null) row.protein = parseFloat((known.pro_per_unit * qty).toFixed(1))
	}

	function onNutritionChanged(i) {
		const row = rows.value[i]
		const known = store.foodLibrary[row.name]
		if (!known || !row.qty) return
		const qty = parseFloat(row.qty)
		const newVal = parseFloat(row[field])
		if (isNaN(qty) || isNaN(newVal)) return
		const storedVal = field === 'calories'
			? known.cal_per_unit * qty
			: known.pro_per_unit * qty
		if (Math.abs(newVal - storedVal) < 0.5) return
		const update = confirm(
			`"${row.name}" has stored ${field} of ${storedVal.toFixed(1)} for qty ${qty},\n\nYou entered ${newVal}. Update stored values?`
		)
		if (update) {
			const perUnit = newVal / qty
			if (field === 'calories') known.cal_per_unit = perUnit
			else known.pro_per_unit = perUnit
		}
	}


	function collect() {
		const items = rows.value
			.filter(r => r.name || r.calories || r.protein)
			.map(r => ({
				name: 		r.name     || null,
				qty:      r.qty      !== '' ? parseFloat(r.qty)      : null,
				calories: r.calories !== '' ? parseFloat(r.calories) : null,
				protein:  r.protein  !== '' ? parseFloat(r.protein)  : null
			}))
		return items.length ? items : null
	}

	return {
		rows,
		addRow,
		removeRow,
		reset,
		onFoodNameSelected,
		onQtyChanged,
		onNutritionChanged,
		collect
	}
}
