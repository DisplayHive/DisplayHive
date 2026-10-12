<script setup lang="ts">
// The "Community & Links", "Support the Project" and "Help wanted" sections of
// the dashboard. The two flags are the Settings page's hide switches.
defineProps<{ hideCommunityLinks: boolean; hideHelpingHand: boolean }>()
</script>

<template>
  <template v-if="!hideCommunityLinks">
    <!-- Community & Links -->
    <div class="community-section">
      <div class="community-heading">
        <i class="pi pi-users"></i>
        <span>Community &amp; Links</span>
      </div>
      <div class="community-grid">

        <a href="https://displayhive.org" target="_blank" rel="noopener" class="link-card link-card--web">
          <div class="link-card-icon"><i class="pi pi-globe"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Website</span>
            <span class="link-card-sub">displayhive.org</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

        <a href="https://github.com/DisplayHive/DisplayHive" target="_blank" rel="noopener" class="link-card link-card--github">
          <div class="link-card-icon"><i class="pi pi-github"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">GitHub</span>
            <span class="link-card-sub">DisplayHive</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

        <a href="https://t.me/DisplayHive" target="_blank" rel="noopener" class="link-card link-card--telegram">
          <div class="link-card-icon"><i class="pi pi-send"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Telegram</span>
            <span class="link-card-sub">Information channel</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

        <a href="https://t.me/DisplayHiveDicussion" target="_blank" rel="noopener" class="link-card link-card--telegram">
          <div class="link-card-icon"><i class="pi pi-comments"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Telegram</span>
            <span class="link-card-sub">Discussion &amp; Support</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

        <a href="https://chaos.social/@DisplayHive" target="_blank" rel="noopener" class="link-card link-card--mastodon">
          <div class="link-card-icon"><i class="pi pi-at"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Mastodon</span>
            <span class="link-card-sub">@DisplayHive@chaos.social</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

      </div>
    </div>

    <!-- Support us -->
    <div class="community-section">
      <div class="community-heading">
        <i class="pi pi-heart"></i>
        <span>Support the Project</span>
      </div>
      <p class="support-intro">DisplayHive is free and open source — a few ways to help.</p>
      <div class="community-grid">

        <a href="https://github.com/DisplayHive/DisplayHive/issues" target="_blank" rel="noopener" class="link-card link-card--bug">
          <div class="link-card-icon"><i class="pi pi-flag"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Found a bug?</span>
            <span class="link-card-sub">Open a GitHub issue</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

        <a href="https://t.me/DisplayHiveDicussion" target="_blank" rel="noopener" class="link-card link-card--idea">
          <div class="link-card-icon"><i class="pi pi-lightbulb"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Have an idea?</span>
            <span class="link-card-sub">Tell us on Telegram</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

        <a href="https://github.com/DisplayHive/DisplayHive" target="_blank" rel="noopener" class="link-card link-card--star">
          <div class="link-card-icon"><i class="pi pi-star"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Give us a star</span>
            <span class="link-card-sub">Star us on GitHub</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

        <a href="https://chaos.social/@DisplayHive" target="_blank" rel="noopener" class="link-card link-card--share">
          <div class="link-card-icon"><i class="pi pi-share-alt"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Spread the word</span>
            <span class="link-card-sub">Tell others about us</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

        <a href="https://github.com/DisplayHive/DisplayHive" target="_blank" rel="noopener" class="link-card link-card--code">
          <div class="link-card-icon"><i class="pi pi-code"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Contribute code</span>
            <span class="link-card-sub">Pull requests welcome</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

        <a href="https://github.com/DisplayHive/DisplayHive" target="_blank" rel="noopener" class="link-card link-card--audit">
          <div class="link-card-icon"><i class="pi pi-eye"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Audit the software</span>
            <span class="link-card-sub">Read through the code</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

        <a href="mailto:security@displayhive.org" class="link-card link-card--security">
          <div class="link-card-icon"><i class="pi pi-lock"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Security issue?</span>
            <span class="link-card-sub">security@displayhive.org</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

      </div>
    </div>
  </template>

    <!-- Help wanted -->
    <div v-if="!hideHelpingHand" class="community-section">
      <div class="community-heading">
        <i class="pi pi-compass"></i>
        <span>Where a helping hand goes a long way</span>
      </div>
      <p class="support-intro">Areas that would benefit most from a contribution right now.</p>
      <div class="community-grid">

        <div class="link-card link-card--static link-card--test">
          <div class="link-card-icon"><i class="pi pi-check-square"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Testing</span>
            <span class="link-card-sub">Run it, break it, tell us</span>
          </div>
        </div>

        <div class="link-card link-card--static link-card--design">
          <div class="link-card-icon"><i class="pi pi-palette"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Designs</span>
            <span class="link-card-sub">Ready-to-use layouts</span>
          </div>
        </div>

        <div class="link-card link-card--static link-card--contenttypes">
          <div class="link-card-icon"><i class="pi pi-file"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Content Types</span>
            <span class="link-card-sub">Reusable templates</span>
          </div>
        </div>

        <div class="link-card link-card--static link-card--sample">
          <div class="link-card-icon"><i class="pi pi-desktop"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Sample Applications</span>
            <span class="link-card-sub">Share what you've built</span>
          </div>
        </div>

        <div class="link-card link-card--static link-card--security">
          <div class="link-card-icon"><i class="pi pi-shield"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Security</span>
            <span class="link-card-sub">Fresh eyes catch bugs</span>
          </div>
        </div>

        <div class="link-card link-card--static link-card--quality">
          <div class="link-card-icon"><i class="pi pi-code"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Code Quality</span>
            <span class="link-card-sub">Read-throughs welcome</span>
          </div>
        </div>

      </div>
    </div>
</template>

<style scoped>
/* Community section */
.community-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.community-heading {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--p-text-muted-color, #9ca3af);
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--p-surface-200, #e5e7eb);
}
.community-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.75rem;
}
.link-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  border-radius: 0.65rem;
  border: 1px solid var(--p-surface-200, #e5e7eb);
  border-left: 4px solid transparent;
  background: var(--p-surface-0, #fff);
  text-decoration: none;
  color: inherit;
  transition: box-shadow 0.15s, transform 0.15s;
}
.link-card:hover {
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
  text-decoration: none;
}
.link-card--web    { border-left-color: #06b6d4; }
.link-card--github { border-left-color: #374151; }
.link-card--telegram { border-left-color: #2ca5e0; }
.link-card--mastodon { border-left-color: #6364ff; }
.link-card--bug      { border-left-color: #ef4444; }
.link-card--idea     { border-left-color: #f59e0b; }
.link-card--star     { border-left-color: #eab308; }
.link-card--share    { border-left-color: #8b5cf6; }
.link-card--code     { border-left-color: #10b981; }
.link-card--audit    { border-left-color: #06b6d4; }
.link-card--security { border-left-color: #f97316; }
.link-card--test     { border-left-color: #ef4444; }
.link-card--design   { border-left-color: #8b5cf6; }
.link-card--contenttypes { border-left-color: #6366f1; }
.link-card--sample   { border-left-color: #06b6d4; }
.link-card--quality  { border-left-color: #14b8a6; }
.link-card-icon {
  font-size: 1.4rem;
  flex-shrink: 0;
  width: 2rem;
  text-align: center;
}
.link-card--web      .link-card-icon { color: #06b6d4; }
.link-card--github   .link-card-icon { color: #374151; }
.link-card--telegram .link-card-icon { color: #2ca5e0; }
.link-card--mastodon  .link-card-icon { color: #6364ff; }
.link-card--bug       .link-card-icon { color: #ef4444; }
.link-card--idea      .link-card-icon { color: #f59e0b; }
.link-card--star      .link-card-icon { color: #eab308; }
.link-card--share     .link-card-icon { color: #8b5cf6; }
.link-card--code      .link-card-icon { color: #10b981; }
.link-card--audit     .link-card-icon { color: #06b6d4; }
.link-card--security  .link-card-icon { color: #f97316; }
.link-card--test      .link-card-icon { color: #ef4444; }
.link-card--design    .link-card-icon { color: #8b5cf6; }
.link-card--contenttypes .link-card-icon { color: #6366f1; }
.link-card--sample    .link-card-icon { color: #06b6d4; }
.link-card--quality   .link-card-icon { color: #14b8a6; }
/* Non-link cards (e.g. "Help wanted" items with no target URL) */
.link-card--static {
  cursor: default;
}
.link-card--static:hover {
  box-shadow: none;
  transform: none;
}
.link-card-body {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  flex: 1;
  min-width: 0;
}
.link-card-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--p-text-color, #111827);
  white-space: nowrap;
}
.link-card-sub {
  font-size: 0.75rem;
  color: var(--p-text-muted-color, #9ca3af);
  line-height: 1.4;
}
.link-card-arrow {
  font-size: 0.75rem;
  color: var(--p-text-muted-color, #d1d5db);
  flex-shrink: 0;
}
.support-intro {
  margin: 0;
  font-size: 0.85rem;
  color: var(--p-text-muted-color, #9ca3af);
  font-style: italic;
}
.dark-mode .link-card {
  background: var(--p-surface-800, #1e293b);
  border-color: var(--p-surface-700, #334155);
}
.dark-mode .link-card:hover {
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
}
.dark-mode .community-heading {
  border-bottom-color: var(--p-surface-700, #334155);
}
.dark-mode .detail-sep,
.dark-mode .link-card-arrow {
  color: var(--p-surface-600, #4b5563);
}
</style>
