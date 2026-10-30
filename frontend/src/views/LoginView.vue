<template>
  <div class="auth-wrap">
    <div class="auth-card">
      <h1 class="auth-title">{{ isRegistering ? 'create account' : 'welcome back' }}</h1>

      <div class="field-group">
        <label class="field-label">email</label>
        <input type="email" v-model="email" placeholder="you@example.com" @keydown.enter="submit" />
      </div>

      <div v-if="isRegistering" class="field-group">
        <label class="field-label">username</label>
        <input type="text" v-model="username" placeholder="yourname" @keydown.enter="submit" />
      </div>

      <div class="field-group">
        <label class="field-label">password</label>
        <input type="password" v-model="password" placeholder="••••••••" @keydown.enter="submit" />
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <div v-if="awaitingVerification" class="notice">
	<p v-if="justRegistered">
	  Account created. We sent a verification link to {{ email }}. Click it, then sign in.
	</p>
	<button class="toggle-btn" @click="resend" :disabled="resending || cooldown > 0">
	  {{ resending ? 'sending...' : cooldown > 0 ? `resend in ${cooldown}s` : 'resend verification email' }}
	</button>
	<p v-if="resendMsg" class="notice-msg">{{ resendMsg }}</p>
      </div>

      <div class="actions">
        <button class="submit-btn" @click="submit" :disabled="loading">
          {{ loading ? 'please wait...' : isRegistering ? 'create account' : 'sign in' }}
        </button>
        <button class="toggle-btn" @click="toggleMode">
          {{ isRegistering ? 'already have an account?' : 'create an account' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const isRegistering = ref(false)

const awaitingVerification = ref(false)
const justRegistered = ref(false)
const resending = ref(false)
const resendMsg = ref('')
const cooldown = ref(0)
let cooldownTimer = null

function resetVerificationState() {
  awaitingVerification.value = false
  justRegistered.value = false
  resendMsg.value = ''
}

function toggleMode() {
  isRegistering.value = !isRegistering.value
  error.value = ''
  resetVerificationState()
}

function startCooldown(seconds = 30) {
  cooldown.value = seconds
  clearInterval(cooldownTimer)
  cooldownTimer = setInterval(() => {
    cooldown.value -= 1
    if (cooldown.value <= 0) clearInterval(cooldownTimer)
  }, 1000)
}

onUnmounted(() => clearInterval(cooldownTimer))

async function resend() {
  if (!email.value) {
    resendMsg.value = 'Enter your email above first.'
    return
  }
  resending.value = true
  resendMsg.value = ''
  try {
    const res = await fetch(
      `/api/users/resend-verification?email=${encodeURIComponent(email.value)}`,
      { method: 'POST' }
    )
    if (res.ok) {
      resendMsg.value = 'If that account is awaiting verification, a new link is on its way.'
      startCooldown()
    } else if (res.status === 429) {
      resendMsg.value = 'Too many requests. Wait a minute and try again.'
      startCooldown(60)
    } else {
      resendMsg.vallue = 'Could not resend. Please try again.'
    }
  } catch {
    resendMsg.value = 'Could not resend. Please try again.'
  } finally {
    resending.value = false
  }
}

async function submit() {
  error.value = ''
  resetVerificationState()
  loading.value = true

  try {
    if (isRegistering.value) {
      const res = await fetch('/api/users/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.value, username: username.value, password: password.value })
      })
      if (!res.ok) {
        const data = await res.json()
        error.value = data.detail || 'Registration failed'
        return
      }
      // New accounts must verify their email before they can log in.
      awaitingVerification.value = true
      justRegistered.value = true
      isRegistering.value = false
      password.value = ''
      startCooldown()
      return
    }

    // Login
    const form = new URLSearchParams()
    form.append('username', email.value)
    form.append('password', password.value)

    const res = await fetch('/api/users/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form
    })

    if (!res.ok) {
      const data = await res.json()
      error.value = data.detail || 'Incorrect email or password'
      if (res.status === 403 && /not verified/i.test(data.detail || '')) {
        awaitingVerification.value = true
      }
      return
    }

    const { access_token } = await res.json()
    // Fetch user info
    const meRes = await fetch('/api/users/me', {
      headers: { Authorization: `Bearer ${access_token}` }
    })
    const user = await meRes.json()

    auth.setAuth(access_token, user)
    router.push('/')
  } catch (e) {
    error.value = 'Something went wrong'
  } finally {
    loading.value = false
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
  margin-bottom: 1.5rem;
}
.field-group { margin-bottom: 1rem; }
.field-label {
  display: block;
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  margin-bottom: 6px;
}
input {
  width: 100%; height: 40px;
  font-family: 'Lora', serif; font-size: 15px;
  color: var(--color-text-primary);
  background: var(--color-bg);
  border: 0.5px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 0 12px; outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}
input:focus { border-color: var(--color-border-strong); }
input::placeholder { color: var(--color-text-muted); }
.error {
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  color: #e24b4a;
  margin-bottom: 1rem;
}
.notice {
  display: flex; flex-direction: column; align-items: flex-start; gap: 6px;
  margin-bottom: 1rem;
  font-family: 'Lora', serif; font-size: 14px; line-height: 1.6;
  color: var(--color-text-secondary);
}
.notice p { margin: 0; }
.notice-msg {
  font-family: 'DM Mono', monospace; font-size: 11px;
  color: var(--color-text-muted);
}
.toggle-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.actions { display: flex; flex-direction: column; gap: 8px; margin-top: 1.5rem; }
.submit-btn {
  height: 44px;
  font-family: 'DM Mono', monospace; font-size: 12px;
  letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--color-text-primary); background: transparent;
  border: 0.5px solid var(--color-border-strong);
  border-radius: var(--radius-md); cursor: pointer;
  transition: background 0.12s;
}
.submit-btn:hover { background: var(--color-bg); }
.submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.toggle-btn {
  font-family: 'DM Mono', monospace; font-size: 11px;
  letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--color-text-muted); background: transparent;
  border: none; cursor: pointer; padding: 4px 0;
  transition: color 0.12s;
}
.toggle-btn:hover { color: var(--color-text-primary); }
</style>
