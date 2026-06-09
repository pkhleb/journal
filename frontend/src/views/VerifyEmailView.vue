<template>
  <div class="auth-wrap">
    <div class="auth-card">
      <h1 class="auth-title">{{ title }}</h1>
      <p class="message">{{ message }}</p>
      <router-link v-if="success" to="/login" class="submit-btn" style="display:block;text-align:center;line-height:44px;text-decoration:none;">
        sign in
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const title = ref('verifying...')
const message = ref('')
const success = ref(false)

onMounted(async () => {
  const token = route.query.token
  if (!token) {
    title.value = 'invalid link'
    message.value = 'No verification token found.'
    return
  }

  try {
    const res = await fetch(`/api/users/verify-email?token=${token}`)
    if (res.ok) {
      title.value = 'email verified'
      message.value = 'Your account is verified. You can now sign in.'
      success.value = true
    } else {
      const data = await res.json()
      title.value = 'verification failed'
      message.value = data.detail || 'Something went wrong.'
    }
  } catch {
    title.value = 'verification failed'
    message.value = 'Something went wrong. Please try again.'
  }
})
</script>

<style scoped>
.auth-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}
.auth-card {
  width: 100%;
  max-width: 400px;
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  padding: 2rem;
  border: 0.5px solid var(--color-border);
}
.auth-title {
  font-family: 'Lora', serif;
  font-size: 22px;
  font-weight: 400;
  font-style: italic;
  color: var(--color-text-primary);
  margin-bottom: 1rem;
}
.message {
  font-family: 'Lora', serif;
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-bottom: 1.5rem;
  line-height: 1.6;
}
.submit-btn {
  height: 44px;
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-primary);
  background: transparent;
  border: 0.5px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.12s;
}
.submit-btn:hover { background: var(--color-bg); }
</style>
