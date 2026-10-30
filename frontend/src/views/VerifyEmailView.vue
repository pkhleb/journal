<template>
  <div class="auth-wrap">
    <div class="auth-card">
      <h1 class="auth-title">{{ title }}</h1>
      <p class="message">{{ message }}</p>
      <button v-if="state === 'ready'" class="submit-btn" @click="verify">
	verify my email
      </button>
      <button v-else-if="state === 'loading'" class="submit-btn" disabled>
	please wait...
      </button>
      <router-link v-else-if="state === 'success'" to="/login" class="submit-btn" style="display:block;text-align:center;line-height:44px;text-decoration:none;">
        sign in
      </router-link>
      <router-link v-else to="/login" class="back-link">
	back to sign in to request a new link
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const token = route.query.token

// ready -> loading -> success | error. Verification only happens on an explicit
// click (POST), so mail scanners that open the link can't consume the token.
const state = ref(token ? 'ready' : 'error')
const title = ref(token ? 'verify your email' : 'invalid link')
const message = ref(token ? 'Confirm below to finish setting up your account.' : 'No verification token found.')

async function verify() {
  state.value = 'loading'
  title.value = 'verifying...'
  message.value = ''
  try {
    const res = await fetch(`/api/users/verify-email?token=${encodeURIComponent(token)}`, { method: 'POST' })
    if (res.ok) {
      title.value = 'email verified'
      message.value = 'Your account is verified. You can now sign in.'
      state.value = 'success'
    } else {
      const data = await res.json().catch(() => ({}))
      title.value = 'verification failed'
      message.value = typeof data.detail === 'string' ? data.detail : 'Something went wrong.'
      state.value = 'error'
    }
  } catch {
    title.value = 'verification failed'
    message.value = 'Something went wrong. Please try again.'
    state.value = 'error'
  }
}
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
  width: 100%;
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
.submit-btn:disbled { opacity: 0.5; cursor: not-allowed; }
.back-link {
  display: block;
  text-align: center;
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  text-decoration: none;
}
.back-link:hover { color: var(--color-text-primary); }
</style>
