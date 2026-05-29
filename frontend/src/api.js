import { useAuthStore } from './stores/auth'
import router from './router'

export async function apiFetch(path, options = {}) {
  const auth = useAuthStore()

  const res = await fetch(`/api${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}),
      ...options.headers
    }
  })

  if (res.status === 401) {
    auth.clearAuth()
    router.push('/login')
    throw new Error('Unauthorized')
  }

  return res
}
