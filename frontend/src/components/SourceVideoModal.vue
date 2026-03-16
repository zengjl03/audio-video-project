<template>
  <Teleport to="body">
    <div class="modal-mask" @click.self="$emit('close')">
      <div class="modal-box">
        <div class="modal-header">
          <span class="modal-title">原始视频 · {{ title || file }}</span>
          <button class="close-btn" @click="$emit('close')">×</button>
        </div>
        <div class="modal-body">
          <video :src="`/api/uploads/${encodeURIComponent(file)}`" class="source-video" controls autoplay></video>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
defineProps<{
  file: string
  title?: string
}>()

defineEmits<{ (e: 'close'): void }>()
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 999;
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(2, 6, 23, 0.66);
}

.modal-box {
  width: min(980px, 100%);
  max-height: 88vh;
  overflow: hidden;
  border-radius: 14px;
  background: #f8fafc;
  box-shadow: 0 22px 55px rgba(2, 6, 23, 0.4);
  border: 1px solid rgba(148, 163, 184, 0.35);
}

.modal-header {
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.25);
  background: #eef2f7;
}

.modal-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.close-btn {
  width: 32px;
  height: 32px;
  border: 1px solid rgba(148, 163, 184, 0.45);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-size: 18px;
  color: #334155;
}

.modal-body {
  padding: 14px;
}

.source-video {
  width: 100%;
  max-height: calc(88vh - 100px);
  border-radius: 10px;
  display: block;
  background: #000;
}
</style>
