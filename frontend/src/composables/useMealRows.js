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
		console.log('onFoodNameSelected - row:', JSON.stringify(row), 'known:', JSON.stringify(known))
		if (!known) return
		const qty = parseFloat(row.qty) || 1
		row.qty = qty
		if (known.cal_per_unit != null) row.calories = parseFloat((known.cal_per_unit * qty).toFixed(1))
		if (known.pro_per_unit != null) row.protein = parseFloat((known.pro_per_unit * qty).toFixed(1))
		console.log('after calc - row:', JSON.stringify(row))
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

	function collect() {
		const items = rows.value
			.filter(r => r.name || r.calories || r.protein)
			.map(r => ({
				name: 		r.name     || null,
				qty:      r.qty      !== '' ? parseFloat(r.qty)      : (r.calories !== '' || r.protein !== '' ? 1 : null),
				calories: r.calories !== '' ? parseFloat(r.calories) : null,
				protein:  r.protein  !== '' ? parseFloat(r.protein)  : null
			}))
		console.log('collect - rows:', JSON.stringify(rows.value), 'items:', JSON.stringify(items))
		return items.length ? items : null
	}

	return {
		rows,
		addRow,
		removeRow,
		reset,
		onFoodNameSelected,
		onQtyChanged,
		collect
	}
}
