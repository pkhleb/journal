import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { DEFAULT_TIMEZONE } from '../utils/timezone'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || null)
  const user  = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isLoggedIn = computed(() => !!token.value)
  // A user cached before the timezone field existed is on the server default.
  const timezone = computed(() => user.value?.timezone || DEFAULT_TIMEZONE)

  function setAuth(newToken, newUser) {
    token.value = newToken
    user.value  = newUser
    localStorage.setItem('token', newToken)
    localStorage.setItem('user', JSON.stringify(newUser))
  }

  function clearAuth() {
    token.value = null
    user.value  = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  function setUser(newUser) {
    user.value = newUser
    localStorage.setItem('user', JSON.stringify(newUser))
  }

  return { token, user, isLoggedIn, timezone, setAuth, setUser, clearAuth }
})
