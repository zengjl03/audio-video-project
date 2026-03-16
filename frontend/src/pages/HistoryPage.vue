<template>
  <div class="history-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">历史任务</h2>
        <p class="page-sub">点击任务卡片进入详情，日志可在卡片内直接展开。</p>
      </div>
      <button class="btn btn-ghost btn-lg" @click="loadTasks" :disabled="loading">
        {{ loading ? '加载中...' : '刷新任务' }}
      </button>
    </div>

    <div v-if="tasks.length === 0 && !loading" class="empty-state">
      <div class="empty-icon">o_o</div>
      <p>暂无任务记录</p>
      <span class="empty-hint">先去上传视频</span>
    </div>

    <div v-else class="task-list">
      <article
        v-for="task in tasks"
        :key="task.id"
        class="task-card"
        @click="goDetail(task.id)"
      >
        <div class="task-top">
          <div class="summary-main">
            <span class="task-id">#{{ task.id }}</span>
            <span class="task-name" :title="task.filename">{{ task.filename }}</span>
            <span :class="['badge', `badge-${task.status}`]">{{ statusLabel(task.status) }}</span>
          </div>
          <div class="summary-right">
            <span class="summary-time">{{ task.updated_at }}</span>
            <span class="summary-progress">{{ task.progress }}%</span>
          </div>
        </div>

        <div class="progress-block" v-if="task.status !== 'uploaded'">
          <div class="progress-track">
            <div
              class="progress-fill"
              :class="{ done: task.status === 'done', failed: task.status === 'failed' }"
              :style="{ width: task.progress + '%' }"
            ></div>
          </div>
          <p class="progress-msg">{{ task.progress_msg || '等待更新...' }}</p>
        </div>

        <div class="meta-row">
          <span>创建时间：{{ task.created_at }}</span>
          <span>更新时间：{{ task.updated_at }}</span>
        </div>

        <div class="quick-actions" @click.stop>
          <button
            v-if="task.status === 'uploaded' || task.status === 'failed'"
            class="action-btn action-primary"
            @click="startTask(task.id)"
            :disabled="startingId === task.id"
          >{{ startingId === task.id ? '启动中...' : '启动处理' }}</button>

          <button
            v-if="task.status === 'processing'"
            class="action-btn action-danger"
            @click="stopTask(task.id)"
            :disabled="stoppingId === task.id"
          >{{ stoppingId === task.id ? '终止中...' : '终止任务' }}</button>

          <button class="action-btn" @click="toggleTaskLogs(task.id)">
            {{ openedLogTaskId === task.id ? '收起日志' : '查看日志' }}
          </button>
          <button v-if="task.status === 'done'" class="action-btn" @click="openReport(task.id)">报告</button>
          <button class="action-btn" @click="deleteTask(task.id)">删除</button>
        </div>

        <div v-if="openedLogTaskId === task.id" class="inline-logs" @click.stop>
          <div class="inline-head">
            <span>任务日志</span>
            <div class="inline-actions">
              <button class="inline-btn" @click="loadTaskLogs(task.id)" :disabled="logLoadingId === task.id">
                {{ logLoadingId === task.id ? '刷新中...' : '刷新' }}
              </button>
              <a class="inline-link" :href="`/api/tasks/${task.id}/logs/raw`" target="_blank" rel="noopener">下载</a>
            </div>
          </div>
          <div v-if="logLoadingId === task.id" class="inline-empty">加载中...</div>
          <div v-else-if="getTaskLogLines(task.id).length === 0" class="inline-empty">暂无日志</div>
          <pre v-else class="inline-pre">{{ getTaskLogLines(task.id).join('\n') }}</pre>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { socket } from '../socket'
import type { TaskItem } from '../types/task'

const tasks = ref<TaskItem[]>([])
const loading = ref(false)
const startingId = ref<number | null>(null)
const stoppingId = ref<number | null>(null)
const openedLogTaskId = ref<number | null>(null)
const logLoadingId = ref<number | null>(null)
const taskLogs = ref<Record<number, string[]>>({})
const router = useRouter()

const statusLabel = (status: string) =>
  ({ pending: '等待', uploaded: '已上传', processing: '处理中', done: '已完成', failed: '失败' })[status] ?? status

async function loadTasks() {
  loading.value = true
  try {
    const res = await fetch('/api/tasks')
    tasks.value = await res.json()
  } finally {
    loading.value = false
  }
}

async function loadTaskLogs(id: number) {
  logLoadingId.value = id
  try {
    const res = await fetch(`/api/tasks/${id}/logs?tail=300`)
    const data = await res.json().catch(() => ({}))
    taskLogs.value[id] = Array.isArray(data.lines) ? data.lines : []
  } finally {
    logLoadingId.value = null
  }
}

async function toggleTaskLogs(id: number) {
  if (openedLogTaskId.value === id) {
    openedLogTaskId.value = null
    return
  }
  openedLogTaskId.value = id
  await loadTaskLogs(id)
}

async function startTask(id: number) {
  startingId.value = id
  try {
    await fetch(`/api/tasks/${id}/start`, { method: 'POST' })
    await loadTasks()
  } finally {
    startingId.value = null
  }
}

async function stopTask(id: number) {
  if (!confirm('确认终止该任务？')) return
  stoppingId.value = id
  try {
    await fetch(`/api/tasks/${id}/stop`, { method: 'POST' })
    await loadTasks()
  } finally {
    stoppingId.value = null
  }
}

async function deleteTask(id: number) {
  if (!confirm('确认删除该任务记录？')) return
  await fetch(`/api/tasks/${id}`, { method: 'DELETE' })
  tasks.value = tasks.value.filter((t) => t.id !== id)
  if (openedLogTaskId.value === id) openedLogTaskId.value = null
}

function openReport(id: number) { router.push(`/result/${id}`) }
function goDetail(id: number) { router.push(`/history/${id}`) }
function getTaskLogLines(id: number) { return taskLogs.value[id] ?? [] }

function onTaskUpdate(payload: { task_id: number; progress: number; msg: string; status: string }) {
  const task = tasks.value.find((t) => t.id === payload.task_id)
  if (!task) return
  task.progress = payload.progress
  task.progress_msg = payload.msg
  task.status = payload.status
  if (payload.status === 'done' || payload.status === 'failed') {
    fetch(`/api/tasks/${payload.task_id}`).then((r) => r.json()).then((u) => Object.assign(task, u))
  }
}

onMounted(() => { loadTasks(); socket.on('task_update', onTaskUpdate) })
onUnmounted(() => { socket.off('task_update', onTaskUpdate) })
</script>

<style scoped>
.history-page { padding-bottom: 36px; }

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 22px;
  gap: 16px;
}

.page-title { font-size: 32px; margin: 0 0 6px; }
.page-sub { font-size: 16px; margin: 0; color: var(--color-text-subtle); }

.btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: 10px;
  border: 1px solid transparent;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s, box-shadow 0.15s, transform 0.1s;
  white-space: nowrap;
  font-size: 14px;
  padding: 9px 16px;
}
.btn-lg { min-height: 46px; padding: 10px 18px; font-size: 15px; }
.btn:active { transform: scale(0.97); }
.btn:disabled { opacity: 0.55; cursor: not-allowed; transform: none; }

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

.empty-state {
  border: 1.5px dashed var(--color-border-strong);
  border-radius: var(--radius-lg);
  padding: 64px 26px;
  color: var(--color-text-subtle);
  text-align: center;
  background: var(--color-brand-50);
  font-size: 17px;
}
.empty-icon { font-size: 38px; margin-bottom: 10px; }
.empty-hint { display: block; font-size: 14px; margin-top: 8px; }

.task-list { display: flex; flex-direction: column; gap: 14px; }

.task-card {
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 16px;
  background:
    radial-gradient(120% 100% at 100% 0%, rgba(255,255,255,0.75) 0%, rgba(255,255,255,0) 42%),
    linear-gradient(140deg, #fdfefe 0%, #f7fbfa 70%, #f4f8f7 100%);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
  transition: box-shadow 0.2s ease, transform 0.2s ease;
  padding: 18px 20px;
  cursor: pointer;
}
.task-card:hover {
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.1);
  transform: translateY(-1px);
  border-color: rgba(15, 155, 132, 0.4);
}

.task-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.summary-main { display: flex; align-items: center; gap: 10px; min-width: 0; }
.task-id { color: var(--color-text-subtle); font-size: 13px; font-weight: 700; flex-shrink: 0; }
.task-name { font-size: 17px; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.summary-right { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
.summary-time { font-size: 13px; color: var(--color-text-subtle); }
.summary-progress { font-size: 14px; font-weight: 700; color: var(--color-brand-700); }

.progress-block { margin-top: 12px; }
.progress-track { height: 10px; border-radius: 999px; background: #e5f2ee; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, var(--color-brand-400), var(--color-brand-300)); transition: width 0.35s ease; }
.progress-fill.done { background: linear-gradient(90deg, #0f9b84, #2dc9a6); }
.progress-fill.failed { background: #f87171; }
.progress-msg { margin: 8px 0 0; color: var(--color-text-subtle); font-size: 14px; }

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 14px;
  color: var(--color-text-subtle);
  margin-top: 10px;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.action-btn {
  min-height: 42px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  color: var(--color-text-muted);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  padding: 0 12px;
  transition: 0.15s;
}
.action-btn:hover:not(:disabled) {
  border-color: var(--color-brand-300);
  color: var(--color-brand-700);
  background: var(--color-brand-50);
}
.action-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.action-primary {
  background: linear-gradient(135deg, var(--color-brand-500), var(--color-brand-400));
  color: #fff;
  border-color: var(--color-brand-500);
}
.action-primary:hover:not(:disabled) {
  color: #fff;
  background: linear-gradient(135deg, var(--color-brand-600), var(--color-brand-500));
  border-color: var(--color-brand-600);
}
.action-danger {
  background: #fff4f4;
  color: #c0392b;
  border-color: #fecaca;
}
.action-danger:hover:not(:disabled) {
  background: #fee2e2;
  color: #b42318;
}

.badge {
  font-size: 12px;
  font-weight: 700;
  border-radius: 999px;
  padding: 4px 10px;
  border: 1px solid transparent;
  flex-shrink: 0;
}
.badge-pending { background: #f1f5f9; color: #475569; border-color: #e2e8f0; }
.badge-uploaded { background: var(--color-brand-100); color: var(--color-brand-700); border-color: var(--color-brand-200); }
.badge-processing { background: #fef9c3; color: #854d0e; border-color: #fde68a; }
.badge-done { background: var(--color-brand-50); color: var(--color-brand-700); border-color: var(--color-brand-200); }
.badge-failed { background: #fff5f5; color: #c0392b; border-color: #fecaca; }

.inline-logs {
  margin-top: 12px;
  border: 1px solid #dbe3ee;
  border-radius: 12px;
  background: #fff;
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

@media (max-width: 980px) {
  .summary-time { display: none; }
}

@media (max-width: 640px) {
  .page-header { flex-direction: column; }
  .task-top { flex-direction: column; }
  .summary-right { width: 100%; justify-content: space-between; }
}
</style>
