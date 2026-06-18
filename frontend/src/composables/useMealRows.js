import { ref } from 'vue'
import { useJournalStore } from '../stores/journal'

export function useMealRows() {
	const store = useJournalStore()

	const rows = ref([{ name: '', qty: '', calories: '', protein: '' , caffeine: '' }])

	function addRow() {
		rows.value.push({ name: '', qty: '', calories: '', protein: '', caffeine: '' })
	}

	function removeRow(i) {
		rows.value.splice(i, 1)
	}

	function reset() {
		rows.value = [{ name: '', qty: '', calories: '', protein: '', caffeine: '' }]
	}

	function onFoodNameSelected(i) {
		const row = rows.value[i]
		const known = store.foodLibrary[row.name]
		console.log('onFoodNameSelected fired - row.qty BEFORE:', JSON.stringify(row.qty))
		if (!known) return
		const qty = parseFloat(row.qty) || 1
		console.log('calculated qty:', qty)
		row.qty = qty
		if (known.cal_per_unit != null) row.calories = parseFloat((known.cal_per_unit * qty).toFixed(1))
		if (known.pro_per_unit != null) row.protein = parseFloat((known.pro_per_unit * qty).toFixed(1))
		if (known.caf_per_unit != null) row.caffeine = parseFloat((known.caf_per_unit * qty).toFixed(1))
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
		if (known.caf_per_unit != null) row.caffeine = parseFloat((known.caf_per_unit * qty).toFixed(1))
	}

	function collect() {
		const items = rows.value
			.filter(r => r.name || r.calories || r.protein || r.caffeine)
			.map(r => ({
				name: 		r.name     || null,
				qty:      r.qty      !== '' ? parseFloat(r.qty)      : (r.calories !== '' || r.protein !== '' ? 1 : null || r.caffeine !== '' ? 1: null),
				calories: r.calories !== '' ? parseFloat(r.calories) : null,
				protein:  r.protein  !== '' ? parseFloat(r.protein)  : null,
				caffeine: r.caffeine !== '' ? parseFloat(r.caffeine) : null
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
