<script setup lang="ts">
import { ref, computed } from 'vue'

// Shown by App.vue while the server still uses pre-DATA_DIR locations for
// media or the SQLite file (application/paths.py → `legacy_data_paths` in the
// connect-time status message, sent only to holders of settings.page). It
// goes away on its own once nothing is left in the old locations.

type LegacyPath = { kind: string; path: string }

const props = defineProps<{
  legacyPaths: LegacyPath[]
  /** 'docker' | 'nixos' | 'manual' — set by the Docker image / NixOS module. */
  deployment?: string
  dataDir?: string | null
}>()

const expanded = ref(false)

const KIND_LABELS: Record<string, string> = {
  media: 'media files',
  media_previews: 'media previews',
  media_renditions: 'media renditions',
}

const what = computed(() => {
  const labels = props.legacyPaths.map((p) => KIND_LABELS[p.kind] || p.kind)
  return labels.length > 1 ? `${labels.slice(0, -1).join(', ')} and ${labels[labels.length - 1]}` : labels[0]
})

const hasMedia = computed(() => props.legacyPaths.length > 0)
const dataDir = computed(() => props.dataDir || '/var/lib/displayhive')

// Shell commands for a manual install: move each legacy location to its new
// place under DATA_DIR (the database is not part of this: DATABASE_URL is required).
const moveCommands = computed(() => {
  const lines = [`mkdir -p ${dataDir.value}`]
  for (const p of props.legacyPaths) {
    lines.push(`mv ${p.path} ${dataDir.value}/${p.kind}`)
  }
  return lines.join('\n')
})

const composeSnippet = `    volumes:
      - media:/data/media
      - media_previews:/data/media_previews
      - media_renditions:/data/media_renditions`

const docsUrl = 'https://docs.displayhive.org/user/installation/#moving-data-to-data_dir'
</script>

<template>
  <div class="legacy-data-banner" data-testid="legacy-data-banner">
    <div class="ldb-summary">
      <i class="pi pi-exclamation-circle"></i>
      <span>
        DisplayHive still keeps {{ what }} in the old location inside the app directory, where an update or
        redeploy can lose them. Move them to the data directory (<code>DATA_DIR</code>).
      </span>
      <button type="button" class="ldb-toggle" :aria-expanded="expanded" @click="expanded = !expanded">
        {{ expanded ? 'Hide steps' : 'Show migration steps' }}
        <i :class="expanded ? 'pi pi-chevron-up' : 'pi pi-chevron-down'"></i>
      </button>
    </div>

    <div v-if="expanded" class="ldb-steps">
      <p>Still in use: <code v-for="p in legacyPaths" :key="p.path" class="ldb-path">{{ p.path }}</code></p>

      <template v-if="deployment === 'docker'">
        <p>
          <strong>Docker:</strong> nothing needs copying. In <code>compose.yml</code>, mount your existing volumes at
          the new paths, then run <code>docker compose up -d</code>:
        </p>
        <pre>{{ composeSnippet }}</pre>
      </template>

      <template v-else-if="deployment === 'nixos'">
        <p>
          <strong>NixOS:</strong> the module now keeps data in
          <code>services.displayhive.instances.&lt;name&gt;.dataDirectory</code> (default
          <code>/var/lib/displayhive/&lt;name&gt;</code>). Stop the service, move the files, then rebuild:
        </p>
        <pre>systemctl stop displayhive-&lt;name&gt;
{{ moveCommands }}
chown -R displayhive-&lt;name&gt;: {{ dataDir }}
nixos-rebuild switch</pre>
      </template>

      <template v-else>
        <p><strong>Manual install:</strong> stop DisplayHive, move the files, set <code>DATA_DIR</code>, start it again:</p>
        <pre>{{ moveCommands }}
export DATA_DIR={{ dataDir }}   # e.g. in your systemd unit or .env</pre>
      </template>

      <p v-if="hasMedia" class="ldb-note">
        Media URLs (<code>/static/media/…</code>) stay the same. Only if your reverse proxy serves
        <code>/static/media</code> straight from disk, point it to the new directory.
      </p>
      <p>
        <a :href="docsUrl" target="_blank" rel="noopener">Full guide in the documentation</a>
        — this notice disappears once nothing is left in the old locations.
      </p>
    </div>
  </div>
</template>

<style scoped>
/* Fixed amber + dark text in both themes, like the red security banner in
   App.vue: maintenance notice chrome, not a themed surface (see
   docs/developer/styleguide.md → "What to leave alone"). */
.legacy-data-banner {
  background: #f59e0b;
  color: #1f2937;
  font-size: 0.85rem;
  padding: 0.5rem 1rem;
}

.ldb-summary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-weight: 600;
  text-align: center;
  flex-wrap: wrap;
}

.ldb-toggle {
  background: rgba(0, 0, 0, 0.12);
  border: none;
  border-radius: 4px;
  color: inherit;
  font: inherit;
  padding: 0.15rem 0.5rem;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.ldb-toggle:hover {
  background: rgba(0, 0, 0, 0.2);
}

.ldb-steps {
  max-width: 820px;
  margin: 0.5rem auto 0.25rem;
}

.ldb-steps p {
  margin: 0.4rem 0;
}

.ldb-steps code,
.ldb-steps pre {
  background: rgba(0, 0, 0, 0.12);
  border-radius: 4px;
  font-size: 0.8rem;
}

.ldb-steps code {
  padding: 0.05rem 0.3rem;
}

.ldb-path + .ldb-path {
  margin-left: 0.35rem;
}

.ldb-steps pre {
  padding: 0.5rem 0.75rem;
  margin: 0.25rem 0 0.5rem;
  overflow-x: auto;
  white-space: pre;
}

.ldb-steps a {
  color: inherit;
  font-weight: 600;
  text-decoration: underline;
}

.ldb-note {
  opacity: 0.85;
}
</style>
