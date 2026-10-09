<script setup lang="ts">
import { useLayoutEditor } from '../../composables/layoutEditor/useLayoutEditor'
import PreviewFrame from '../PreviewFrame.vue'

// The canvas: the Design preview behind, the snaplines and one rectangle per placed container.
const ed = useLayoutEditor()
</script>

<template>
<div class="editor-canvas-wrap">
  <div
    :ref="(el) => (ed.canvasEl = el as HTMLElement | null)"
    class="editor-canvas"
    :class="{ 'handles-hidden': ed.preview.hideHandlerElements }"
    :style="ed.canvasStyle"
    @pointerdown="ed.onCanvasPointerDown"
    @dragover.prevent
    @drop.prevent="ed.onCanvasDrop"
  >
    <PreviewFrame
      v-if="ed.preview.designPreviewSrcdoc"
      class="editor-design-preview"
      :html="ed.preview.designPreviewSrcdoc"
      title="Active Design preview"
    />
    <div
      v-for="(line, i) in ed.snaplines"
      :key="`snapline-${i}`"
      class="canvas-snapline"
      :class="line.axis === 'h' ? 'canvas-snapline--h' : 'canvas-snapline--v'"
      :style="line.axis === 'h' ? { top: `${line.position}%` } : { left: `${line.position}%` }"
    ></div>
    <div
      v-for="c in ed.placedContainers"
      :key="c.id"
      class="editor-rect"
      :class="{ selected: ed.selectedId === c.id, locked: c.locked }"
      :style="ed.rectStyle(c)"
      @pointerdown="ed.onRectPointerDown($event, c, 'move')"
    >
      <span class="rect-label">{{ ed.contentFor(c).name }} <span class="rect-label-id">#{{ c.id }}</span></span>
      <div class="rect-toolbar">
        <button
          type="button"
          class="remove-handle"
          title="Remove from Layout"
          @pointerdown.stop.prevent
          @click.stop.prevent="ed.removeFromLayout(c.id)"
        >
          <i class="pi pi-minus"></i>
        </button>
        <button
          type="button"
          class="delete-handle"
          :class="{ disabled: !ed.canDeleteContainer(c) }"
          :title="ed.canDeleteContainer(c) ? 'Delete container entirely' : 'In use — cannot delete'"
          @pointerdown.stop.prevent
          @click.stop.prevent="ed.confirmDeleteContainer(c.id)"
        >
          <i class="pi pi-times"></i>
        </button>
      </div>
      <button
        type="button"
        class="lock-handle"
        :class="{ 'lock-handle--locked': c.locked }"
        :title="c.locked ? 'Unlock position' : 'Lock position'"
        @pointerdown.stop.prevent
        @click.stop.prevent="ed.toggleContainerLock(c)"
      >
        <i :class="c.locked ? 'pi pi-lock' : 'pi pi-lock-open'"></i>
      </button>
      <template v-if="!c.locked">
        <div class="resize-handle resize-handle--tl" @pointerdown="ed.onRectPointerDown($event, c, 'resize', 'tl')"></div>
        <div class="resize-handle resize-handle--tr" @pointerdown="ed.onRectPointerDown($event, c, 'resize', 'tr')"></div>
        <div class="resize-handle resize-handle--bl" @pointerdown="ed.onRectPointerDown($event, c, 'resize', 'bl')"></div>
        <div class="resize-handle resize-handle--br" @pointerdown="ed.onRectPointerDown($event, c, 'resize', 'br')"></div>
      </template>
    </div>
    <div v-if="ed.drawRect" class="editor-rect drawing-rect" :style="ed.drawRectStyle"></div>
  </div>
  <p class="hint">Drag a rectangle to move it, its corner handle to resize, or click-drag empty space to draw a new container.</p>
</div>
</template>

<style scoped>
.editor-canvas-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

/* "Disable Handlerelements": show only what ends up on a screen. */
.editor-canvas.handles-hidden {
  background: none;
}

.editor-canvas.handles-hidden .canvas-snapline,
.editor-canvas.handles-hidden .drawing-rect,
.editor-canvas.handles-hidden .rect-label,
.editor-canvas.handles-hidden .rect-toolbar,
.editor-canvas.handles-hidden .lock-handle,
.editor-canvas.handles-hidden .resize-handle {
  display: none;
}

/* Rectangles stay in place and clickable (select / drag), just invisible. */
.editor-canvas.handles-hidden .editor-rect,
.editor-canvas.handles-hidden .editor-rect.selected {
  background: transparent;
  border-color: transparent;
}

.canvas-snapline {
  position: absolute;
  background: #e11d48;
  pointer-events: none;
  z-index: 4;
}

.canvas-snapline--h {
  left: 0;
  right: 0;
  height: 1px;
}

.canvas-snapline--v {
  top: 0;
  bottom: 0;
  width: 1px;
}

.editor-canvas {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: repeating-linear-gradient(
      0deg, rgba(128, 128, 128, 0.08) 0, rgba(128, 128, 128, 0.08) 1px, transparent 1px, transparent 10%
    ),
    repeating-linear-gradient(
      90deg, rgba(128, 128, 128, 0.08) 0, rgba(128, 128, 128, 0.08) 1px, transparent 1px, transparent 10%
    );
  border: 1px solid var(--p-content-border-color, #ccc);
  border-radius: 6px;
  overflow: hidden;
  touch-action: none;
  cursor: crosshair;
}

.editor-design-preview {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: none;
  /* Let clicks/drags fall through to the canvas underneath — the iframe is
     a separate document, so without this it would swallow the pointer
     events that drive drawing/moving/resizing containers. */
  pointer-events: none;
}

.editor-rect {
  position: absolute;
  box-sizing: border-box;
  background: rgba(37, 99, 171, 0.15);
  border: 2px solid #2563ab;
  border-radius: 4px;
  cursor: move;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-start;
  overflow: hidden;
}

.editor-rect.selected {
  background: rgba(37, 99, 171, 0.3);
  border-color: #1e3a5f;
  z-index: 2;
}

.editor-rect.drawing-rect {
  background: rgba(76, 175, 80, 0.2);
  border: 2px dashed #4caf50;
  pointer-events: none;
}

.rect-label {
  font-size: 0.7rem;
  font-weight: 600;
  color: #1e3a5f;
  background: rgba(255, 255, 255, 0.7);
  padding: 1px 4px;
  border-radius: 3px;
  margin: 3px;
  pointer-events: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: calc(100% - 6px);
}

.rect-label-id {
  font-weight: 400;
  color: #64748b;
}

.resize-handle {
  position: absolute;
  width: 14px;
  height: 14px;
  background: #2563ab;
  border: 1px solid white;
  border-radius: 2px;
  z-index: 3;
}

.resize-handle--tl {
  top: 2px;
  left: 2px;
  cursor: nwse-resize;
}

.resize-handle--br {
  bottom: 2px;
  right: 2px;
  cursor: nwse-resize;
}

.resize-handle--tr {
  top: 2px;
  right: 2px;
  cursor: nesw-resize;
}

.resize-handle--bl {
  bottom: 2px;
  /* Offset from the true bottom-left corner (left: 2px) — that spot is
     reserved for .lock-handle, which is always rendered there. */
  left: 20px;
  cursor: nesw-resize;
}

.rect-toolbar {
  position: absolute;
  top: 2px;
  right: 2px;
  display: flex;
  gap: 2px;
  z-index: 4;
}

.remove-handle,
.delete-handle {
  width: 16px;
  height: 16px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid white;
  border-radius: 2px;
  cursor: pointer;
  font-size: 0.6rem;
  line-height: 1;
  color: white;
}

.remove-handle {
  background: #c62828;
}

.remove-handle:hover {
  background: #e53935;
}

.delete-handle {
  background: #c62828;
}

.delete-handle:hover {
  background: #e53935;
}

.delete-handle.disabled {
  background: #999;
  cursor: not-allowed;
}

.lock-handle {
  position: absolute;
  bottom: 2px;
  left: 2px;
  z-index: 4;
  width: 16px;
  height: 16px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid white;
  border-radius: 2px;
  cursor: pointer;
  font-size: 0.6rem;
  line-height: 1;
  color: white;
  background: rgba(30, 58, 95, 0.7);
}

.lock-handle:hover {
  background: #1e3a5f;
}

.lock-handle--locked {
  background: #c62828;
}

.lock-handle--locked:hover {
  background: #e53935;
}

.editor-rect.locked {
  cursor: not-allowed;
  border-style: dashed;
}

.hint {
  color: var(--p-text-muted-color, #888);
  font-size: 0.75rem;
  margin: 0;
}
</style>
