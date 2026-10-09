<script setup lang="ts">
import { ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import type { DesignForm } from '../../types/designForm'
import { formatCss, formatHtml } from '../../utils/codeFormat'
import DesignPanel from './DesignPanel.vue'
import Button from 'primevue/button'

import { Codemirror } from 'vue-codemirror'
import { html as cmHtml } from '@codemirror/lang-html'
import { css as cmCss } from '@codemirror/lang-css'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView } from '@codemirror/view'

// The Design's hand-written background HTML and CSS: rendered last, so it always wins.
const form = defineModel<DesignForm>('form', { required: true })
const toast = useToast()

const cmHtmlExtensions = [cmHtml(), oneDark, EditorView.lineWrapping]
const cmCssExtensions = [cmCss(), oneDark, EditorView.lineWrapping]

// "Format" buttons on the HTML/CSS editors (Prettier, loaded on first use). A
// source that can't be parsed is left exactly as it is, with the reason shown.
const formatting = ref<'html' | 'css' | null>(null)
const formatEditor = async (which: 'html' | 'css') => {
  formatting.value = which
  try {
    const result = await (which === 'html' ? formatHtml(form.value.html) : formatCss(form.value.css))
    if (result.ok) {
      if (which === 'html') form.value.html = result.code
      else form.value.css = result.code
    } else {
      toast.add({ severity: 'warn', summary: `Could not format the ${which.toUpperCase()}`, detail: result.error, life: 6000 })
    }
  } finally {
    formatting.value = null
  }
}
</script>

<template>
  <DesignPanel
    title="Custom HTML and CSS"
    description="Hand-written background HTML/CSS — rendered last, so it always wins over every collapsible above."
    header-tour="designs-custom-html-header"
  >
    <div class="code-editors-row">
      <div class="code-editor-field">
        <div class="code-editor-header">
          <label>Background HTML</label>
          <Button
            icon="pi pi-align-left" label="Format" size="small" text
            :loading="formatting === 'html'" :disabled="!form.html.trim()"
            title="Auto-format the HTML (Prettier)"
            @click="formatEditor('html')"
          />
        </div>
        <Codemirror
          v-model="form.html"
          :extensions="cmHtmlExtensions"
          :style="{ height: '400px' }"
          :autofocus="false"
          :indent-with-tab="true"
          :tab-size="2"
        />
        <small class="hint">This renders once as the screen's static background — content containers are positioned on top of it via the Layouts page, not placed with tags here.</small>
      </div>
      <div class="code-editor-field">
        <div class="code-editor-header">
          <label>CSS Styles</label>
          <Button
            icon="pi pi-align-left" label="Format" size="small" text
            :loading="formatting === 'css'" :disabled="!form.css.trim()"
            title="Auto-format the CSS (Prettier)"
            @click="formatEditor('css')"
          />
        </div>
        <Codemirror
          v-model="form.css"
          :extensions="cmCssExtensions"
          :style="{ height: '400px' }"
          :autofocus="false"
          :indent-with-tab="true"
          :tab-size="2"
        />
      </div>
    </div>
  </DesignPanel>
</template>

<style scoped>
.hint {
  color: #888;
  font-size: 0.75rem;
}

.code-editors-row {
  display: flex;
  gap: 1rem;
}

.code-editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.code-editor-field {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.code-editor-field label {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--p-text-muted-color, #6b7280);
}

.code-editor-field .vue-codemirror {
  border: 1px solid var(--p-inputtext-border-color, #d1d5db);
  border-radius: 6px;
  overflow: hidden;
}
</style>
