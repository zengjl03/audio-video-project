<template>
  <div class="task-detail-page" v-if="task">
    <section class="main-column">
      <section class="player card">
        <div class="player-wrap" v-if="task.upload_file">
          <video :src="`/api/uploads/${encodeURIComponent(task.upload_file)}`" controls preload="metadata"></video>
        </div>
        <div v-else class="player-empty">该任务没有可预览原视频</div>
      </section>

      <section class="video-info card">
        <div class="info-top">
          <h2 class="video-title" :title="task.filename">{{ task.filename }}</h2>
          <span :class="['status-chip', `status-${task.status}`]">{{ statusLabel(task.status) }}</span>
        </div>
        <p class="video-meta">任务 #{{ task.id }} · 创建于 {{ task.created_at }} · 更新于 {{ task.updated_at }}</p>
        <div class="video-info-actions">
          <button class="info-link-btn" @click="toggleLogs">{{ detailLogsOpen ? '收起日志' : '查看日志' }}</button>
          <button v-if="task.status === 'done'" class="info-link-btn" @click="openReport">结果报告</button>
        </div>

        <div v-if="detailLogsOpen" class="inline-logs">
          <div class="inline-head">
            <span>任务日志</span>
            <div class="inline-actions">
              <button class="inline-btn" @click="loadDetailLogs" :disabled="detailLogsLoading">
                {{ detailLogsLoading ? '刷新中...' : '刷新' }}
              </button>
              <a class="inline-link" :href="`/api/tasks/${task.id}/logs/raw`" target="_blank" rel="noopener">下载</a>
            </div>
          </div>
          <div v-if="detailLogsLoading" class="inline-empty">加载中...</div>
          <div v-else-if="detailLogLines.length === 0" class="inline-empty">暂无日志</div>
          <pre v-else class="inline-pre">{{ detailLogLines.join('\n') }}</pre>
        </div>
      </section>

      <section class="progress-panel card">
        <div class="progress-head">
          <strong>任务进度</strong>
          <span>{{ task.progress }}%</span>
        </div>

        <template v-if="task.status !== 'uploaded'">
          <div class="progress-track">
            <div class="progress-fill" :class="{ done: task.status === 'done', failed: task.status === 'failed' }" :style="{ width: task.progress + '%' }"></div>
          </div>
          <p class="progress-msg">{{ task.progress_msg || '等待更新...' }}</p>
        </template>
        <p v-else class="progress-msg">视频已上传，点击下方按钮开始处理</p>

        <div class="progress-actions">
          <button
            v-if="task.status === 'uploaded' || task.status === 'failed'"
            class="action-btn action-primary"
            :disabled="starting"
            @click="startTask"
          >{{ starting ? '启动中...' : '启动处理' }}</button>

          <button
            v-if="task.status === 'processing'"
            class="action-btn action-danger"
            :disabled="stopping"
            @click="stopTask"
          >{{ stopping ? '终止中...' : '终止任务' }}</button>
        </div>
      </section>

      <section class="result-panel card">
        <div class="panel-head">
          <h3>相关内容</h3>
          <span v-if="clips.length">{{ clips.length }} 个片段</span>
        </div>
        <div v-if="clips.length === 0" class="clips-empty">当前没有可展示片段</div>
        <div v-else class="clips-list">
          <article v-for="(clip, idx) in clips" :key="`${clip.clip_file}-${idx}`" class="clip-item">
            <div class="clip-top">
              <strong>{{ idx + 1 }}. {{ clip.title }}</strong>
              <span>{{ formatTime(clip.start_time) }} - {{ formatTime(clip.end_time) }}</span>
            </div>
            <p>{{ clip.description }}</p>
            <button class="clip-link" @click="openClipPreview(clip)">打开片段文件</button>
          </article>
        </div>
      </section>
    </section>

    <aside class="side-column">
      <section class="card side-block">
        <h3>同类任务推荐</h3>
        <p class="side-sub">按相同状态优先，其次按最近更新时间</p>
        <div v-if="relatedTasks.length === 0" class="related-empty">暂无推荐任务</div>
        <button
          v-for="item in relatedTasks"
          :key="item.id"
          class="related-item"
          @click="openRelatedPreview(item.id)"
        >
          <span class="related-name" :title="item.filename">{{ item.filename }}</span>
          <span class="related-meta">#{{ item.id }} · {{ statusLabel(item.status) }}</span>
        </button>
      </section>
    </aside>
  </div>

  <div v-if="relatedDialogOpen" class="dialog-mask" @click.self="closeRelatedPreview">
    <section class="dialog-card">
      <header class="dialog-head">
        <strong>相关任务详情</strong>
        <button class="dialog-close" @click="closeRelatedPreview" aria-label="关闭弹窗">×</button>
      </header>
      <div v-if="relatedDialogLoading" class="dialog-empty">加载中...</div>
      <div v-else-if="!relatedTaskPreview" class="dialog-empty">加载失败，请稍后重试</div>
      <template v-else>
        <div class="dialog-meta">
          <h4 :title="relatedTaskPreview.filename">{{ relatedTaskPreview.filename }}</h4>
          <p>
            任务 #{{ relatedTaskPreview.id }} ·
            {{ statusLabel(relatedTaskPreview.status) }} ·
            进度 {{ relatedTaskPreview.progress }}%
          </p>
          <p>创建于 {{ relatedTaskPreview.created_at }} · 更新于 {{ relatedTaskPreview.updated_at }}</p>
          <p v-if="relatedTaskPreview.progress_msg">{{ relatedTaskPreview.progress_msg }}</p>
        </div>
        <div class="dialog-clips">
          <h5>片段内容</h5>
          <div v-if="(relatedTaskPreview.result ?? []).length === 0" class="dialog-empty">暂无片段</div>
          <article v-for="(clip, idx) in (relatedTaskPreview.result ?? [])" :key="`${clip.clip_file}-${idx}`" class="dialog-clip-item">
            <div class="dialog-clip-top">
              <strong>{{ idx + 1 }}. {{ clip.title }}</strong>
              <span>{{ formatTime(clip.start_time) }} - {{ formatTime(clip.end_time) }}</span>
            </div>
            <p>{{ clip.description }}</p>
            <button class="clip-link" @click="openClipPreview(clip)">打开片段文件</button>
          </article>
        </div>
      </template>
    </section>
  </div>

  <div v-if="clipPreviewOpen" class="dialog-mask clip-preview-mask" @click.self="closeClipPreview">
    <section class="dialog-card clip-preview-card">
      <header class="dialog-head">
        <strong>{{ clipPreviewTitle || '片段预览' }}</strong>
        <button class="dialog-close" @click="closeClipPreview" aria-label="关闭弹窗">×</button>
      </header>
      <div class="clip-preview-body">
        <video v-if="clipPreviewUrl" :src="clipPreviewUrl" controls preload="metadata"></video>
      </div>
    </section>
  </div>

  <div v-if="!task" class="detail-empty card">
    <p v-if="loading">正在加载任务详情...</p>
    <p v-else>任务不存在或已删除</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { Clip, TaskItem } from '../types/task'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const starting = ref(false)
const stopping = ref(false)
const task = ref<TaskItem | null>(null)
const allTasks = ref<TaskItem[]>([])
const detailLogsOpen = ref(false)
const detailLogsLoading = ref(false)
const detailLogLines = ref<string[]>([])
const relatedDialogOpen = ref(false)
const relatedDialogLoading = ref(false)
const relatedTaskPreview = ref<TaskItem | null>(null)
const clipPreviewOpen = ref(false)
const clipPreviewTitle = ref('')
const clipPreviewUrl = ref('')

const clips = computed<Clip[]>(() => task.value?.result ?? [])

const relatedTasks = computed(() => {
  const current = task.value
  if (!current) return []
  return allTasks.value
    .filter((item) => item.id !== current.id)
    .sort((a, b) => {
      const scoreA = (a.status === current.status ? 1000 : 0) + new Date(a.updated_at).getTime()
      const scoreB = (b.status === current.status ? 1000 : 0) + new Date(b.updated_at).getTime()
      return scoreB - scoreA
    })
    .slice(0, 8)
})

const statusLabel = (status: string) =>
  ({ pending: '等待', uploaded: '已上传', processing: '处理中', done: '已完成', failed: '失败' })[status] ?? status

async function loadTask() {
  loading.value = true
  try {
    const id = route.params.id
    const [taskRes, listRes] = await Promise.all([
      fetch(`/api/tasks/${id}`),
      fetch('/api/tasks')
    ])

    if (!taskRes.ok) {
      task.value = null
      return
    }

    task.value = await taskRes.json()
    const list = await listRes.json().catch(() => [])
    allTasks.value = Array.isArray(list) ? list : []
  } finally {
    loading.value = false
  }
}

async function loadDetailLogs() {
  if (!task.value) return
  detailLogsLoading.value = true
  try {
    const res = await fetch(`/api/tasks/${task.value.id}/logs?tail=300`)
    const data = await res.json().catch(() => ({}))
    detailLogLines.value = Array.isArray(data.lines) ? data.lines : []
  } finally {
    detailLogsLoading.value = false
  }
}

async function toggleLogs() {
  detailLogsOpen.value = !detailLogsOpen.value
  if (detailLogsOpen.value) await loadDetailLogs()
}

async function startTask() {
  if (!task.value) return
  starting.value = true
  try {
    const res = await fetch(`/api/tasks/${task.value.id}/start`, { method: 'POST' })
    if (!res.ok) return
    await loadTask()
  } finally {
    starting.value = false
  }
}

async function stopTask() {
  if (!task.value) return
  if (!confirm('确认终止该任务？')) return
  stopping.value = true
  try {
    const res = await fetch(`/api/tasks/${task.value.id}/stop`, { method: 'POST' })
    if (!res.ok) return
    await loadTask()
  } finally {
    stopping.value = false
  }
}

function openReport() {
  if (!task.value) return
  router.push(`/result/${task.value.id}`)
}

async function openRelatedPreview(id: number) {
  relatedDialogOpen.value = true
  relatedDialogLoading.value = true
  relatedTaskPreview.value = null
  try {
    const res = await fetch(`/api/tasks/${id}`)
    if (!res.ok) return
    relatedTaskPreview.value = await res.json()
  } finally {
    relatedDialogLoading.value = false
  }
}

function closeRelatedPreview() {
  relatedDialogOpen.value = false
  relatedDialogLoading.value = false
  relatedTaskPreview.value = null
}

function openClipPreview(clip: Clip) {
  clipPreviewTitle.value = clip.title || clip.clip_file
  clipPreviewUrl.value = `/api/results/${encodeURIComponent(clip.clip_file)}`
  clipPreviewOpen.value = true
}

function closeClipPreview() {
  clipPreviewOpen.value = false
  clipPreviewTitle.value = ''
  clipPreviewUrl.value = ''
}

function formatTime(secs: number): string {
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

watch(() => route.params.id, async () => {
  detailLogsOpen.value = false
  detailLogLines.value = []
  closeClipPreview()
  await loadTask()
})
onMounted(loadTask)
</script>

<style scoped>
.task-detail-page {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(280px, 1fr);
  gap: 20px;
  padding-bottom: 36px;
}

.card {
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 17px;
  background: #fff;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
}

.main-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.player { overflow: hidden; }
.player-wrap {
  background: #000;
  aspect-ratio: 16 / 9;
}
.player-wrap video {
  width: 100%;
  height: 100%;
  display: block;
}
.player-empty {
  min-height: 260px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  font-size: 16px;
}

.video-info {
  padding: 12px 14px;
}

.info-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}

.video-title {
  margin: 0;
  font-size: 18px;
  line-height: 1.35;
  color: #0f172a;
}

.video-meta {
  margin: 6px 0 0;
  font-size: 12px;
  color: #64748b;
}

.video-info-actions {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.info-link-btn {
  min-height: 30px;
  border: 1px solid #dbe5ec;
  border-radius: 8px;
  background: #fff;
  color: #475569;
  font-size: 12px;
  padding: 0 10px;
  cursor: pointer;
}
.info-link-btn:hover {
  border-color: #7dd3c0;
  color: #0f766e;
  background: #f0faf7;
}

.inline-logs {
  margin-top: 10px;
  border: 1px solid #dbe3ee;
  border-radius: 12px;
  overflow: hidden;
}
.inline-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  font-size: 13px;
  font-weight: 700;
}
.inline-actions { display: flex; gap: 8px; align-items: center; }
.inline-btn {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  color: #334155;
  font-size: 12px;
  padding: 4px 8px;
  cursor: pointer;
}
.inline-link {
  color: #0f766e;
  font-size: 12px;
  text-decoration: none;
}
.inline-empty {
  padding: 14px;
  font-size: 13px;
  color: #64748b;
}
.inline-pre {
  margin: 0;
  padding: 12px;
  max-height: 260px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.55;
  color: #0f172a;
  background: #f8fafc;
  font-family: ui-monospace, Menlo, Consolas, monospace;
}

.status-chip {
  border-radius: 999px;
  border: 1px solid transparent;
  padding: 4px 9px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}
.status-pending { background: #f1f5f9; color: #475569; border-color: #e2e8f0; }
.status-uploaded { background: #dff5ef; color: #116655; border-color: #bceadf; }
.status-processing { background: #fef3c7; color: #92400e; border-color: #fde68a; }
.status-done { background: #dcfce7; color: #166534; border-color: #bbf7d0; }
.status-failed { background: #fee2e2; color: #991b1b; border-color: #fecaca; }

.action-btn {
  min-height: 44px;
  border-radius: 10px;
  border: 1px solid #dce5ea;
  background: #fff;
  color: #334155;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: 0.15s;
  padding: 0 12px;
}
.action-btn:hover:not(:disabled) {
  border-color: #7dd3c0;
  background: #f0faf7;
  color: #0f766e;
}
.action-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.action-primary {
  border-color: #10b981;
  color: #fff;
  background: linear-gradient(135deg, #10b981, #14b8a6);
}
.action-primary:hover:not(:disabled) {
  color: #fff;
  background: linear-gradient(135deg, #059669, #0d9488);
}
.action-danger {
  border-color: #fecaca;
  color: #b91c1c;
  background: #fff5f5;
}

.progress-panel { padding: 16px 18px; }
.progress-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 9px;
  font-size: 15px;
}
.progress-track {
  height: 10px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #14b8a6, #34d399);
  transition: width 0.35s ease;
}
.progress-fill.done { background: linear-gradient(90deg, #16a34a, #22c55e); }
.progress-fill.failed { background: #ef4444; }
.progress-msg { margin: 10px 0 0; color: #64748b; font-size: 14px; }

.progress-actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.result-panel { padding: 16px 18px 18px; }
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.panel-head h3 {
  margin: 0;
  font-size: 20px;
  color: #0f172a;
}
.panel-head span {
  font-size: 14px;
  color: #64748b;
}
.clips-empty {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 20px;
  text-align: center;
  color: #94a3b8;
  font-size: 15px;
}
.clips-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.clip-item {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  background: #fcfefe;
}
.clip-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.clip-top strong {
  font-size: 15px;
  color: #0f172a;
}
.clip-top span {
  font-size: 13px;
  color: #64748b;
  white-space: nowrap;
}
.clip-item p {
  margin: 7px 0;
  font-size: 14px;
  color: #475569;
  line-height: 1.55;
}
.clip-link {
  border: none;
  background: none;
  padding: 0;
  font-size: 14px;
  color: #0f766e;
  font-weight: 700;
  cursor: pointer;
}
.clip-link:hover { text-decoration: underline; }

.side-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.side-block {
  padding: 16px;
}
.side-block h3 {
  margin: 0 0 5px;
  font-size: 18px;
  color: #0f172a;
}
.side-sub {
  margin: 0 0 12px;
  font-size: 14px;
  color: #64748b;
}
.related-empty {
  font-size: 14px;
  color: #94a3b8;
  padding: 9px 0;
}
.related-item {
  width: 100%;
  border: 1px solid #dbe6e2;
  border-radius: 12px;
  background: #fff;
  padding: 11px 12px;
  text-align: left;
  margin-bottom: 8px;
  cursor: pointer;
}
.related-item:hover {
  border-color: #86efac;
  background: #f0fdf4;
}
.related-name {
  display: block;
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.related-meta {
  display: block;
  margin-top: 3px;
  font-size: 13px;
  color: #64748b;
}

.dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 16px;
}
.dialog-card {
  width: min(760px, 100%);
  max-height: min(85vh, 840px);
  overflow: auto;
  border-radius: 16px;
  border: 1px solid #dbe5ec;
  background: #fff;
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.2);
}
.dialog-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid #e2e8f0;
}
.dialog-close {
  width: 32px;
  height: 32px;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #fff;
  color: #334155;
  font-size: 20px;
  cursor: pointer;
}
.dialog-meta {
  padding: 14px 16px 8px;
}
.dialog-meta h4 {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}
.dialog-meta p {
  margin: 7px 0 0;
  font-size: 13px;
  color: #64748b;
}
.dialog-clips {
  padding: 0 16px 16px;
}
.dialog-clips h5 {
  margin: 8px 0 10px;
  font-size: 15px;
  color: #1e293b;
}
.dialog-empty {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  padding: 16px;
  font-size: 14px;
  color: #94a3b8;
  text-align: center;
}
.dialog-clip-item {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  background: #fcfefe;
  margin-bottom: 10px;
}
.dialog-clip-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.dialog-clip-top strong {
  font-size: 15px;
  color: #0f172a;
}
.dialog-clip-top span {
  font-size: 13px;
  color: #64748b;
  white-space: nowrap;
}
.dialog-clip-item p {
  margin: 7px 0;
  font-size: 14px;
  color: #475569;
  line-height: 1.55;
}
.clip-preview-mask {
  z-index: 60;
}
.clip-preview-card {
  width: min(900px, 100%);
}
.clip-preview-body {
  padding: 12px;
}
.clip-preview-body video {
  width: 100%;
  max-height: 72vh;
  display: block;
  background: #000;
  border-radius: 10px;
}

.detail-empty {
  padding: 20px;
  color: #64748b;
  font-size: 16px;
}

@media (max-width: 1080px) {
  .task-detail-page { grid-template-columns: 1fr; }
}

@media (max-width: 520px) {
  .info-top { flex-direction: column; align-items: flex-start; }
}
</style>
