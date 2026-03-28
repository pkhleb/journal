<template>
  <div class="cb-wrap">
    <input
      type="text"
      :placeholder="placeholder"
      v-model="inputVal"
      autocomplete="off"
      @input="onInput"
      @focus="onFocus"
      @blur="onBlur"
      @keydown="onKeydown"
    />
    <div class="cb-dropdown" :class="{ open: isOpen }">
      <div
        v-if="filtered.length === 0 && inputVal"
        class="cb-empty"
      >enter to use "{{ inputVal }}"</div>
      <div
        v-for="(opt, i) in filtered"
        :key="opt"
        class="cb-option"
        :class="{ active: i === activeIdx }"
        @mousedown.prevent="select(opt)"
      >{{ opt }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  modelValue: String,
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue'])

const inputVal = ref(props.modelValue || '')
const isOpen = ref(false)
const activeIdx = ref(-1)

const filtered = computed(() => {
  if (!inputVal.value) return props.options
  return props.options.filter(o =>
    o.toLowerCase().includes(inputVal.value.toLowerCase())
  )
})

function onInput() {
  emit('update:modelValue', inputVal.value)
  isOpen.value = true
  activeIdx.value = -1
}

function onFocus() {
  isOpen.value = true
}

function onBlur() {
  setTimeout(() => { isOpen.value = false }, 150)
}

function select(opt) {
  inputVal.value = opt
  emit('update:modelValue', opt)
  isOpen.value = false
}

function onKeydown(e) {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIdx.value = Math.min(activeIdx.value + 1, filtered.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIdx.value = Math.max(activeIdx.value - 1, 0)
  } else if (e.key === 'Enter' && activeIdx.value >= 0) {
    e.preventDefault()
    select(filtered.value[activeIdx.value])
  } else if (e.key === 'Escape') {
    isOpen.value = false
  }
}
</script>

<style scoped>
.cb-wrap { position: relative; flex: 1; }
.cb-dropdown {
  position: absolute; top: 42px; left: 0; right: 0; z-index: 10;
  background: var(--color-bg);
  border: 0.5px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  overflow: hidden; display: none;
}
.cb-dropdown.open { display: block; }
.cb-option {
  padding: 9px 12px; font-size: 14px;
  color: var(--color-text-primary); cursor: pointer;
}
.cb-option:hover, .cb-option.active { background: var(--color-surface); }
.cb-empty { padding: 9px 12px; font-size: 13px; color: var(--color-text-muted); font-style: italic; }
</style>
