<template>
  <div class="upload-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">上传视频</h2>
        <p class="page-sub">支持大文件断点续传。上传后可立即启动处理，也可在历史页查看任务详情。</p>
      </div>
    </div>

    <div class="upload-top">
      <section class="upload-main">
        <div
          class="drop-zone"
          :class="{ dragging: isDragging, uploading: isUploading, done: uploadDone && !isUploading }"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="onDrop"
          @click="!isUploading && fileInput?.click()"
        >
          <template v-if="!isUploading && !uploadDone">
            <div class="drop-icon">+</div>
            <p class="drop-text">点击或拖拽视频到这里</p>
            <p class="drop-hint">支持 mp4 / mov / avi</p>
          </template>

          <template v-if="isUploading">
            <div class="progress-wrap">
              <p class="uploading-name">正在上传：{{ currentFile?.name }}</p>
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
              </div>
              <p class="progress-text">{{ uploadProgress }}% · {{ uploadStatus }}</p>
            </div>
          </template>

          <template v-if="uploadDone && !isUploading">
            <div class="done-icon">OK</div>
            <p class="drop-text">上传完成</p>
            <p class="drop-hint">{{ currentFile?.name }} · 任务 #{{ createdTaskId }}</p>
          </template>
        </div>

        <input ref="fileInput" type="file" accept="video/*" style="display:none" @change="onFileChange" />

        <div v-if="uploadDone" class="done-actions">
          <button class="action-tile action-tile-primary" @click="startImmediately" :disabled="startingTask">
            {{ startingTask ? '启动中...' : '立即开始处理' }}
          </button>
          <button class="action-tile" @click="goTaskDetail" :disabled="!createdTaskId">查看任务详情</button>
          <button class="action-tile" @click="goHistory">前往历史任务</button>
          <button class="action-tile" @click="startNewUpload">继续上传</button>
        </div>

        <div v-if="statusMsg" class="status-toast" :class="statusLevel">{{ statusMsg }}</div>
      </section>

      <aside class="stats-panel card">
        <div class="stats-head">
          <h3>任务统计</h3>
          <button class="btn btn-ghost btn-xs" @click="loadStats" :disabled="statsLoading">{{ statsLoading ? '刷新中...' : '刷新' }}</button>
        </div>

        <div v-if="!stats || stats.trend_14d.length === 0" class="stats-empty">暂无统计数据</div>
        <div v-else ref="statsChartEl" class="stats-chart"></div>
      </aside>
    </div>

    <section class="video-section">
      <div class="section-header">
        <h3 class="section-title">上传视频历史</h3>
        <span class="section-hint">横向滚动查看</span>
      </div>

      <div v-if="videoHistory.length === 0" class="empty-state">
        <div class="empty-icon">[]</div>
        <p>暂无可预览视频</p>
      </div>
      <div v-else class="video-strip">
        <article v-for="task in videoHistory" :key="`v-${task.id}`" class="video-card card">
          <div class="video-frame">
            <video :src="`/api/uploads/${encodeURIComponent(task.upload_file!)}`" preload="metadata" controls muted></video>
          </div>
          <div class="video-body">
            <p class="video-title" :title="task.filename">{{ task.filename }}</p>
            <p class="video-sub">#{{ task.id }} · {{ statusLabel(task.status) }}</p>
            <div class="video-actions">
              <button class="btn btn-ghost btn-xs" @click="openSource(task.upload_file!, task.filename)">预览</button>
              <button
                v-if="task.status === 'uploaded' || task.status === 'failed'"
                class="btn btn-primary btn-xs"
                :disabled="cardStartingId === task.id"
                @click="startTask(task.id)"
              >{{ cardStartingId === task.id ? '启动中...' : '开始处理' }}</button>
              <button class="btn btn-ghost btn-xs" @click="router.push(`/history/${task.id}`)">详情</button>
            </div>
          </div>
        </article>
      </div>
    </section>

    <SourceVideoModal v-if="sourceFile" :file="sourceFile" :title="sourceTitle" @close="closeSource" />
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import SourceVideoModal from '../components/SourceVideoModal.vue'

interface TaskBrief {
  id: number
  filename: string
  status: string
  upload_file?: string | null
  created_at: string
}

interface TrendItem {
  date: string
  done: number
  failed: number
}

interface StatsPayload {
  total_tasks: number
  done_tasks: number
  failed_tasks: number
  processing_tasks: number
  uploaded_tasks: number
  success_rate: number
  avg_processing_seconds: number
  trend_14d: TrendItem[]
}

const router = useRouter()
const fileInput = ref<HTMLInputElement | null>(null)
const isDragging = ref(false)
const isUploading = ref(false)
const uploadDone = ref(false)
const uploadProgress = ref(0)
const uploadStatus = ref('')
const currentFile = ref<File | null>(null)
const createdTaskId = ref<number | null>(null)
const startingTask = ref(false)
const cardStartingId = ref<number | null>(null)
const statusMsg = ref('')
const statusLevel = ref<'success' | 'error' | 'info'>('info')
const tasks = ref<TaskBrief[]>([])
const sourceFile = ref<string | null>(null)
const sourceTitle = ref('')
const statsLoading = ref(false)
const stats = ref<StatsPayload | null>(null)
const statsChartEl = ref<HTMLDivElement | null>(null)
let statsChart: echarts.ECharts | null = null

const CHUNK_SIZE = 1 * 1024 * 1024
const videoHistory = computed(() => tasks.value.filter((t) => t.upload_file))

const statusLabel = (s: string) =>
  ({ pending: '等待', uploaded: '已上传', processing: '处理中', done: '已完成', failed: '失败' })[s] ?? s

function showStatus(msg: string, level: 'success' | 'error' | 'info' = 'info') {
  statusMsg.value = msg
  statusLevel.value = level
  setTimeout(() => { statusMsg.value = '' }, 2500)
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  const file = e.dataTransfer?.files[0]
  if (file) startUpload(file)
}

function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) startUpload(file)
}

function startNewUpload() {
  uploadDone.value = false
  uploadProgress.value = 0
  currentFile.value = null
  createdTaskId.value = null
  if (fileInput.value) fileInput.value.value = ''
}

function goHistory() { router.push('/history') }
function goTaskDetail() {
  if (!createdTaskId.value) return
  router.push(`/history/${createdTaskId.value}`)
}

async function loadTasks() {
  try {
    const res = await fetch('/api/tasks')
    const data = await res.json()
    tasks.value = Array.isArray(data) ? data : []
  } catch {
    tasks.value = []
  }
}

async function loadStats() {
  statsLoading.value = true
  try {
    const res = await fetch('/api/stats')
    const data = await res.json()
    stats.value = data
    await nextTick()
    renderStatsChart()
  } finally {
    statsLoading.value = false
  }
}

function renderStatsChart() {
  if (!statsChartEl.value || !stats.value || stats.value.trend_14d.length === 0) {
    if (statsChart) {
      statsChart.dispose()
      statsChart = null
    }
    return
  }
  if (!statsChart) statsChart = echarts.init(statsChartEl.value)
  const xData = stats.value.trend_14d.map((item) => item.date)
  const doneData = stats.value.trend_14d.map((item) => item.done)
  const failedData = stats.value.trend_14d.map((item) => item.failed)
  statsChart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const rows = Array.isArray(params) ? params : [params]
        const date = rows[0]?.axisValueLabel ?? ''
        const lines = rows.map((row: any) => `${row.marker}${row.seriesName}: ${row.value}`)
        return [date, ...lines].join('<br/>')
      }
    },
    legend: { top: 8, right: 12, itemHeight: 8, textStyle: { fontSize: 12 } },
    grid: { left: 34, right: 16, top: 36, bottom: 34 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: xData,
      name: '日期',
      nameLocation: 'middle',
      nameGap: 26,
      axisLabel: {
        color: '#64748b',
        fontSize: 11,
        formatter: (value: string) => value.slice(5)
      }
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: '#64748b', fontSize: 11 },
      splitLine: { lineStyle: { color: '#e2e8f0' } }
    },
    series: [
      {
        name: '成功',
        type: 'line',
        smooth: true,
        data: doneData,
        symbolSize: 6,
        lineStyle: { width: 2, color: '#22c55e' },
        itemStyle: { color: '#22c55e' },
        areaStyle: { color: 'rgba(34, 197, 94, 0.12)' }
      },
      {
        name: '失败',
        type: 'line',
        smooth: true,
        data: failedData,
        symbolSize: 6,
        lineStyle: { width: 2, color: '#ef4444' },
        itemStyle: { color: '#ef4444' },
        areaStyle: { color: 'rgba(239, 68, 68, 0.1)' }
      }
    ]
  })
}

function onResize() {
  statsChart?.resize()
}

async function startTask(id: number) {
  cardStartingId.value = id
  try {
    const res = await fetch(`/api/tasks/${id}/start`, { method: 'POST' })
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      showStatus(d.error || '启动失败', 'error')
      return
    }
    showStatus('任务已启动', 'success')
    await loadTasks()
    await loadStats()
  } finally {
    cardStartingId.value = null
  }
}

async function startImmediately() {
  if (!createdTaskId.value) return
  startingTask.value = true
  try {
    const res = await fetch(`/api/tasks/${createdTaskId.value}/start`, { method: 'POST' })
    if (res.ok) {
      showStatus('任务已启动，正在跳转...', 'success')
      setTimeout(() => router.push(`/history/${createdTaskId.value}`), 900)
    } else {
      const d = await res.json().catch(() => ({}))
      showStatus(d.error || '启动失败', 'error')
    }
  } catch {
    showStatus('网络错误', 'error')
  } finally {
    startingTask.value = false
  }
}

function openSource(file: string, title: string) { sourceFile.value = file; sourceTitle.value = title }
function closeSource() { sourceFile.value = null; sourceTitle.value = '' }

async function startUpload(file: File) {
  currentFile.value = file
  isUploading.value = true
  uploadDone.value = false
  uploadProgress.value = 0
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE)
  const identifier = `${Date.now()}-${file.size}-${file.name.replace(/[^a-zA-Z0-9]/g, '')}`
  for (let i = 1; i <= totalChunks; i++) {
    try {
      const chk = await fetch(`/api/upload/check?resumableIdentifier=${identifier}&resumableChunkNumber=${i}`)
      if (chk.status === 200) {
        uploadProgress.value = Math.round((i / totalChunks) * 95)
        uploadStatus.value = `恢复分块 ${i}/${totalChunks}`
        continue
      }
    } catch {
      // ignore
    }
    const start = (i - 1) * CHUNK_SIZE
    const chunk = file.slice(start, Math.min(start + CHUNK_SIZE, file.size))
    const fd = new FormData()
    fd.append('file', chunk)
    fd.append('resumableChunkNumber', String(i))
    fd.append('resumableTotalChunks', String(totalChunks))
    fd.append('resumableIdentifier', identifier)
    fd.append('resumableFilename', file.name)
    uploadStatus.value = `上传分块 ${i}/${totalChunks}`
    const res = await fetch('/api/upload/chunk', { method: 'POST', body: fd })
    if (!res.ok) {
      showStatus('上传失败，请重试', 'error')
      isUploading.value = false
      return
    }
    const data = await res.json()
    uploadProgress.value = Math.round((i / totalChunks) * 95)
    if (data.status === 'complete') {
      uploadProgress.value = 100
      uploadStatus.value = '上传完成'
      createdTaskId.value = data.task_id
      isUploading.value = false
      uploadDone.value = true
      await loadTasks()
      await loadStats()
      return
    }
  }
  isUploading.value = false
}

onMounted(() => {
  loadTasks()
  loadStats()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (statsChart) {
    statsChart.dispose()
    statsChart = null
  }
})
</script>

<style scoped>
.upload-page { padding-bottom: 32px; }
.page-header { margin-bottom: 24px; }

.upload-top {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  align-items: start;
  margin-bottom: 28px;
}

.upload-main { min-width: 0; }

.stats-panel {
  padding: 14px;
  border-radius: 14px;
}

.stats-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.stats-head h3 {
  margin: 0;
  font-size: 16px;
}

.stats-empty {
  border: 1px dashed #dbe3ee;
  border-radius: 10px;
  padding: 16px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}

.stats-chart {
  width: 100%;
  height: 260px;
  border: 1px solid #dbe3ee;
  border-radius: 10px;
  background: #fff;
}

.drop-zone {
  border: 1.5px dashed var(--color-border-strong);
  border-radius: var(--radius-lg);
  min-height: 250px;
  padding: 44px 24px;
  background: linear-gradient(160deg, #f7faf9 0%, #f2f8f6 100%);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s, transform 0.2s;
  text-align: center;
}

.drop-zone:hover,
.drop-zone.dragging {
  border-color: var(--color-brand-400);
  background: linear-gradient(160deg, #eef8f4 0%, #e8f7f2 100%);
  transform: translateY(-1px);
}

.drop-zone.uploading { cursor: default; }
.drop-zone.done {
  border-color: var(--color-brand-400);
  background: linear-gradient(160deg, #f7faf9 0%, #eef8f4 100%);
  cursor: default;
}

.drop-icon, .done-icon {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 14px;
}

.drop-icon {
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  color: var(--color-brand-600);
  box-shadow: var(--shadow-xs);
}

.done-icon {
  background: var(--color-brand-500);
  color: #fff;
  box-shadow: 0 4px 12px rgba(15,155,132,0.3);
}

.drop-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text-main);
  margin: 0 0 6px;
}

.drop-hint {
  color: var(--color-text-subtle);
  font-size: 13px;
  margin: 0;
}

.progress-wrap { width: min(480px, 100%); }
.uploading-name {
  font-size: 14px;
  color: var(--color-text-muted);
  margin: 0 0 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-bar {
  height: 8px;
  border-radius: 999px;
  background: var(--color-brand-100);
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-brand-400), var(--color-brand-300));
  transition: width 0.35s ease;
}

.progress-text { font-size: 12px; color: var(--color-text-subtle); margin: 0; }

.done-actions {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(2, minmax(180px, 1fr));
  gap: 12px;
}

.action-tile {
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: 12px;
  min-height: 54px;
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all 0.15s;
}
.action-tile:hover:not(:disabled) {
  border-color: var(--color-brand-300);
  color: var(--color-brand-700);
  background: var(--color-brand-50);
  transform: translateY(-1px);
}
.action-tile:disabled { opacity: 0.55; cursor: not-allowed; }

.action-tile-primary {
  border-color: var(--color-brand-500);
  color: #fff;
  background: linear-gradient(135deg, var(--color-brand-500), var(--color-brand-400));
  box-shadow: 0 6px 20px rgba(15, 155, 132, 0.22);
}
.action-tile-primary:hover:not(:disabled) {
  color: #fff;
  border-color: var(--color-brand-600);
  background: linear-gradient(135deg, var(--color-brand-600), var(--color-brand-500));
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, box-shadow 0.15s, transform 0.1s;
  white-space: nowrap;
  font-size: 13px;
  padding: 7px 14px;
}
.btn:active { transform: scale(0.97); }
.btn:disabled { opacity: 0.55; cursor: not-allowed; transform: none; }
.btn-xs { font-size: 11px; padding: 4px 9px; }

.btn-ghost {
  background: var(--color-surface);
  color: var(--color-text-muted);
  border-color: var(--color-border);
}
.btn-ghost:hover:not(:disabled) {
  background: var(--color-brand-50);
  color: var(--color-brand-600);
  border-color: var(--color-brand-200);
}

.btn-primary {
  background: var(--color-brand-500);
  color: #fff;
  border-color: var(--color-brand-500);
  box-shadow: 0 2px 8px rgba(15,155,132,0.25);
}
.btn-primary:hover:not(:disabled) {
  background: var(--color-brand-600);
  box-shadow: 0 4px 12px rgba(15,155,132,0.35);
}

.status-toast {
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  display: inline-block;
  border: 1px solid transparent;
}
.status-toast.success { background: var(--color-brand-50); color: var(--color-brand-700); border-color: var(--color-brand-200); }
.status-toast.error { background: #fff5f5; color: #c0392b; border-color: #fecaca; }
.status-toast.info { background: #eff6ff; color: #1e40af; border-color: #bfdbfe; }

.video-section { margin-top: 8px; }
.section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}
.section-title { margin: 0; font-size: 15px; font-weight: 700; color: var(--color-text-main); }
.section-hint { font-size: 12px; color: var(--color-text-subtle); }

.empty-state {
  border: 1.5px dashed var(--color-border-strong);
  border-radius: var(--radius-lg);
  padding: 32px 24px;
  color: var(--color-text-subtle);
  text-align: center;
  background: var(--color-brand-50);
  font-size: 13px;
}
.empty-icon { font-size: 28px; margin-bottom: 8px; }

.video-strip {
  display: flex;
  gap: 14px;
  overflow-x: auto;
  padding-bottom: 8px;
  scrollbar-width: thin;
  scrollbar-color: var(--color-border) transparent;
}

.video-card {
  flex: 0 0 280px;
  overflow: hidden;
  border-radius: var(--radius-md);
}

.video-frame { aspect-ratio: 16/9; background: #000; }
.video-frame video { width: 100%; height: 100%; display: block; }

.video-body { padding: 10px 12px 12px; }
.video-title { margin: 0 0 3px; font-size: 12px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.video-sub { margin: 0 0 10px; color: var(--color-text-subtle); font-size: 11px; }
.video-actions { display: flex; gap: 6px; flex-wrap: wrap; }

@media (max-width: 900px) {
  .done-actions { grid-template-columns: 1fr; }
}
</style>
