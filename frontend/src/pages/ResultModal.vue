<template>
  <Teleport to="body">
    <div class="modal-mask" @click.self="$emit('close')">
      <div class="modal-box">
        <div class="modal-header">
          <span class="modal-title">处理结果：{{ task.filename }}</span>
          <button class="close-btn" @click="$emit('close')">✕</button>
        </div>

        <div class="modal-body">
          <!-- 无结果 -->
          <div v-if="!clips || clips.length === 0" class="empty-result">
            <p>暂无精彩片段结果，可能处理未完成或未识别到精彩内容。</p>
          </div>

          <!-- 精彩片段列表 -->
          <div v-else>
            <p class="clip-count">共识别到 <strong>{{ clips.length }}</strong> 个精彩片段</p>
            <div
              v-for="(clip, idx) in clips"
              :key="idx"
              class="clip-card"
              :class="{ active: activeIdx === idx }"
              @click="selectClip(idx)"
            >
              <div class="clip-meta">
                <span class="clip-num">片段 {{ idx + 1 }}</span>
                <span class="clip-title">{{ clip.title }}</span>
                <span class="clip-time">
                  {{ formatTime(clip.start_time) }} → {{ formatTime(clip.end_time) }}
                  （{{ (clip.end_time - clip.start_time).toFixed(1) }}s）
                </span>
              </div>
              <p class="clip-desc">{{ clip.description }}</p>

              <!-- 视频预览（展开时） -->
              <div v-if="activeIdx === idx && clip.clip_file" class="video-wrap">
                <video
                  :src="`/api/results/${clip.clip_file}`"
                  controls
                  autoplay
                  class="clip-video"
                ></video>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Clip, TaskItem } from '../types/task'

type ResultTask = Pick<TaskItem, 'id' | 'filename' | 'result'>

const props = defineProps<{ task: ResultTask }>()
defineEmits<{ (e: 'close'): void }>()

const activeIdx = ref<number | null>(null)
const clips = computed<Clip[]>(() => props.task.result ?? [])

function selectClip(idx: number) {
  activeIdx.value = activeIdx.value === idx ? null : idx
}

function formatTime(secs: number): string {
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: radial-gradient(circle at top, rgba(15, 118, 110, 0.4), rgba(15, 23, 42, 0.85));
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.modal-box {
  background: rgba(255, 255, 255, 0.98);
  border-radius: 20px;
  width: 100%;
  max-width: 760px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  box-shadow:
    0 30px 80px rgba(15, 23, 42, 0.7),
    0 0 0 1px rgba(148, 163, 184, 0.35);
  overflow: hidden;
}

.modal-header {
  padding: 16px 22px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: radial-gradient(circle at 0 0, #ecfdf5, #dcfce7);
  color: #0f172a;
}

.modal-title {
  font-size: 15px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.close-btn {
  background: transparent;
  border: none;
  color: #0f172a;
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 999px;
  flex-shrink: 0;
  transition:
    background 0.18s ease,
    transform 0.12s ease;
}
.close-btn:hover {
  background: rgba(15, 23, 42, 0.06);
  transform: translateY(-1px);
}

.modal-body {
  overflow-y: auto;
  padding: 20px 20px 18px;
  flex: 1;
}

.empty-result {
  color: #9ca3af;
  text-align: center;
  padding: 40px 0;
}

.clip-count {
  font-size: 14px;
  color: #6b7280;
  margin-bottom: 14px;
}

.clip-card {
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 14px;
  padding: 14px 16px;
  margin-bottom: 12px;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.12s ease,
    background 0.18s ease;
  background: #ffffff;
}
.clip-card:hover {
  border-color: rgba(34, 197, 94, 0.7);
  box-shadow:
    0 14px 36px rgba(15, 23, 42, 0.12),
    0 4px 10px rgba(15, 23, 42, 0.06);
  transform: translateY(-1px);
}
.clip-card.active {
  border-color: #16a34a;
  box-shadow:
    0 18px 46px rgba(79, 70, 229, 0.35),
    0 4px 10px rgba(15, 23, 42, 0.08);
  background: linear-gradient(135deg, #ecfdf5, #dcfce7);
}

.clip-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.clip-num {
  background: #16a34a;
  color: #fff;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
}

.clip-title {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
}
.clip-time {
  font-size: 12px;
  color: #6b7280;
  margin-left: auto;
}
.clip-desc {
  font-size: 13px;
  color: #4b5563;
  line-height: 1.6;
}

.video-wrap {
  margin-top: 12px;
  background: #000;
  border-radius: 10px;
  overflow: hidden;
}
.clip-video {
  width: 100%;
  max-height: 360px;
  display: block;
}
</style>
