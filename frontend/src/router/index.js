import { createRouter, createWebHistory } from 'vue-router'
import JournalView from '../views/JournalView.vue'
import InventoryView from '../views/InventoryView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
		{ path: '/', component: JournalView },
		{ path: '/inventory', component: InventoryView }
	],
})

export default router
