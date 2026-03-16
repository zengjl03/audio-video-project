<template>
  <div>
    <div class="head">
      <h2>结果可视化报告</h2>
      <p v-if="task">任务 #{{ task.id }} · {{ task.filename }}</p>
    </div>

    <div v-if="loading" class="empty">正在加载任务结果...</div>
    <div v-else-if="!task" class="empty">任务不存在或暂无数据。</div>
    <div v-else>
      <section class="metrics">
        <article class="metric">
          <span>精彩片段</span>
          <strong>{{ clips.length }}</strong>
        </article>
        <article class="metric">
          <span>平均时长</span>
          <strong>{{ avgDuration.toFixed(1) }}s</strong>
        </article>
        <article class="metric">
          <span>总覆盖时长</span>
          <strong>{{ totalDuration.toFixed(1) }}s</strong>
        </article>
      </section>

      <section class="block">
        <h3>教育互动指标（启发式）</h3>
        <div class="bars">
          <div class="bar-row" v-for="item in scoreItems" :key="item.label">
            <span>{{ item.label }}</span>
            <div class="bar-track"><div class="bar-fill" :style="{ width: item.value + '%' }"></div></div>
            <em>{{ item.value }}%</em>
          </div>
        </div>
      </section>

      <section class="block">
        <h3>时间线</h3>
        <div class="timeline">
          <div v-for="(clip, idx) in clips" :key="`${clip.clip_file}-${idx}`" class="line-item">
            <div class="line-top">
              <strong>{{ idx + 1 }}. {{ clip.title }}</strong>
              <span>{{ formatTime(clip.start_time) }} - {{ formatTime(clip.end_time) }}</span>
            </div>
            <p>{{ clip.description }}</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import type { Clip, TaskItem } from '../types/task'

const route = useRoute()
const loading = ref(false)
const task = ref<TaskItem | null>(null)

const clips = computed<Clip[]>(() => task.value?.result ?? [])
const totalDuration = computed(() => clips.value.reduce((acc, c) => acc + (c.end_time - c.start_time), 0))
const avgDuration = computed(() => (clips.value.length ? totalDuration.value / clips.value.length : 0))

const scoreItems = computed(() => {
  const text = clips.value.map((c) => `${c.title} ${c.description}`).join(' ').toLowerCase()
  const normalize = (n: number) => Math.min(100, Math.max(0, n))
  return [
    { label: '鼓励性语言', value: normalize((text.match(/鼓励|赞|很好|不错|支持/g)?.length ?? 0) * 12 + 20) },
    { label: '提问引导', value: normalize((text.match(/为什么|怎么|吗|问/g)?.length ?? 0) * 10 + 18) },
    { label: '互动频次', value: normalize(clips.value.length * 14 + 10) },
  ]
})

async function loadTask() {
  loading.value = true
  try {
    const id = route.params.id
    const res = await fetch(`/api/tasks/${id}`)
    if (!res.ok) {
      task.value = null
      return
    }
    task.value = await res.json()
  } finally {
    loading.value = false
  }
}

function formatTime(secs: number): string {
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

onMounted(loadTask)
</script>

<style scoped>
.head h2 {
  margin: 0;
  font-size: 24px;
}
.head p {
  margin: 6px 0 14px;
  font-size: 14px;
  color: #64748b;
}
.empty {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 24px;
  text-align: center;
  color: #94a3b8;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.metric {
  border: 1px solid #dbe3ee;
  border-radius: 10px;
  background: #fff;
  padding: 10px 12px;
}
.metric span {
  font-size: 12px;
  color: #64748b;
}
.metric strong {
  display: block;
  margin-top: 4px;
  font-size: 22px;
  color: #0f172a;
}
.block {
  margin-top: 12px;
  border: 1px solid #dbe3ee;
  border-radius: 12px;
  background: #fff;
  padding: 12px;
}
.block h3 {
  margin: 0 0 10px;
  font-size: 15px;
}
.bar-row {
  display: grid;
  grid-template-columns: 92px 1fr 46px;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.bar-row span,
.bar-row em {
  font-size: 12px;
  color: #475569;
  font-style: normal;
}
.bar-track {
  height: 8px;
  border-radius: 999px;
  background: #e2e8f0;
}
.bar-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #60a5fa, #0ea5e9);
}
.timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.line-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 8px 10px;
}
.line-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}
.line-top strong {
  font-size: 13px;
  color: #0f172a;
}
.line-top span {
  color: #64748b;
  font-size: 12px;
  white-space: nowrap;
}
.line-item p {
  margin: 6px 0 0;
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
}
@media (max-width: 800px) {
  .metrics {
    grid-template-columns: 1fr;
  }
}
</style>
