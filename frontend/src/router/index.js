import { createRouter, createWebHistory } from 'vue-router'
import JournalView from '../views/JournalView.vue'
import InventoryView from '../views/InventoryView.vue'
import AnalyticsView from '../views/AnalyticsView.vue'
import { useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
		{ path: '/', component: JournalView, meta: {requiresAuth: true} },
		{ path: '/inventory', component: InventoryView, meta: {requiresAuth: true} },
		{ path: '/analytics', component: AnalyticsView, meta: {requiresAuth: true} },
		{ path: '/login', component: LoginView }
	],
})

router.beforeEach((to, from, next) => {
	const token = localStorage.getItem('token')
	if (to.meta.requiresAuth && !token) {
		next('/login')
	} else if (to.path === '/login' && token) {
		next('/')
	} else {
		next()
	}
})

export default router
