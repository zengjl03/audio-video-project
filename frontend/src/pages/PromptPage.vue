<template>
  <div class="prompt-page">
    <h2 class="page-title">Prompt 管理</h2>
    <p class="page-sub">使用结构化模板，正文格式固定。你只能修改下方有限参数，保存后对新任务生效。</p>

    <div v-if="loadHint" class="hint">{{ loadHint }}</div>

    <section class="editor card">
      <div class="editor-head">可编辑参数</div>

      <div class="grid">
        <label class="field">
          <span>核心任务</span>
          <input v-model="editable.coreTask" maxlength="120" placeholder="例如：识别完整家庭事件并返回时间戳" />
          <small>{{ editable.coreTask.length }}/120</small>
        </label>

        <label class="field">
          <span>关键约束提示</span>
          <input v-model="editable.eventGapNote" maxlength="120" placeholder="例如：不同事件之间时间间隔可能小于5秒" />
          <small>{{ editable.eventGapNote.length }}/120</small>
        </label>

        <label class="field field-inline">
          <span>长停顿阈值（秒）</span>
          <input v-model.number="editable.longPauseSec" type="number" min="1" max="10" />
        </label>

        <label class="field field-wide">
          <span>补充要求（可选）</span>
          <textarea v-model="editable.extraRules" maxlength="220" rows="3" placeholder="例如：优先保留亲子互动、笑声、情绪高点的上下文"></textarea>
          <small>{{ editable.extraRules.length }}/220</small>
        </label>
      </div>

      <div class="template-bar">
        <button v-for="item in templates" :key="item.name" @click="applyTemplate(item)">{{ item.name }}</button>
      </div>
    </section>

    <section class="preview card">
      <div class="preview-head">
        <span>Prompt 模板预览（只读）</span>
        <span v-if="updatedAt" class="updated-at">最后更新：{{ updatedAt }}</span>
      </div>
      <textarea class="preview-textarea" :value="generatedPrompt" readonly spellcheck="false"></textarea>
      <div class="preview-footer">
        <div>
          <span class="char-count">{{ generatedPrompt.length }} 字符</span>
          <span v-if="hasChanges" class="unsaved">有未保存修改</span>
        </div>
        <div class="actions">
          <button class="btn-reset" @click="resetEditable" :disabled="!hasChanges">撤销</button>
          <button class="btn-save" @click="savePrompt" :disabled="saving || !hasChanges">
            {{ saving ? '保存中...' : '保存 Prompt' }}
          </button>
        </div>
      </div>
    </section>

    <div v-if="toast" class="toast" :class="toastLevel">{{ toast }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

type EditableState = {
  coreTask: string
  eventGapNote: string
  longPauseSec: number
  extraRules: string
}

type TemplatePreset = {
  name: string
  values: EditableState
}

const DEFAULT_EDITABLE: EditableState = {
  coreTask: '识别完整家庭生活事件并返回时间戳',
  eventGapNote: '不同事件之间时间间隔可能较小（小于5秒）',
  longPauseSec: 3,
  extraRules: '优先保留有明确亲子互动、欢笑和情绪变化的事件。'
}

const templates: TemplatePreset[] = [
  {
    name: '完整事件识别（推荐）',
    values: {
      coreTask: '识别完整家庭生活事件并返回时间戳',
      eventGapNote: '不同事件之间时间间隔可能较小（小于5秒），不要仅按时间硬切分',
      longPauseSec: 3,
      extraRules: '优先保证语义完整；同一事件中的准备、过程、结果尽量合并。'
    }
  },
  {
    name: '亲子互动链路',
    values: {
      coreTask: '识别亲子互动链路完整的事件并返回时间戳',
      eventGapNote: '当提问-回应-反馈连续出现时，即使间隔短也应视为同一事件',
      longPauseSec: 4,
      extraRules: '重点保留家长引导、孩子回应、情绪反馈三段式互动。'
    }
  },
  {
    name: '家庭欢笑高光',
    values: {
      coreTask: '识别家庭欢笑和开心高光事件并返回时间戳',
      eventGapNote: '笑声、惊喜、夸奖等高光片段前后应补足必要上下文',
      longPauseSec: 3,
      extraRules: '优先保留情绪高点；避免将纯信息性闲聊误识别为高光事件。'
    }
  },
  {
    name: '育儿教学场景',
    values: {
      coreTask: '识别育儿教学与行为引导事件并返回时间戳',
      eventGapNote: '同一教学目标下的示范、练习、纠正应尽量合并',
      longPauseSec: 4,
      extraRules: '关注鼓励性表达、规则说明、行为纠偏，输出可复盘事件。'
    }
  },
  {
    name: '家庭日常活动',
    values: {
      coreTask: '识别家庭日常活动事件并返回时间戳',
      eventGapNote: '做饭、收纳、游戏等活动中多人连续协作不应被拆散',
      longPauseSec: 5,
      extraRules: '突出场景切换边界：客厅/厨房/餐桌等空间变化可作为拆分参考。'
    }
  },
  {
    name: '严格边界拆分',
    values: {
      coreTask: '识别语义边界清晰的完整事件并返回时间戳',
      eventGapNote: '仅在明显话题转换、场景切换或长停顿时拆分事件',
      longPauseSec: 2,
      extraRules: '减少跨主题合并，控制事件粒度更细，适合精细回看。'
    }
  }
]
const editable = reactive<EditableState>({ ...DEFAULT_EDITABLE })
const originalSnapshot = ref('')
const updatedAt = ref<string | null>(null)
const saving = ref(false)
const toast = ref('')
const toastLevel = ref<'success' | 'error'>('success')
const loadHint = ref('')

const hasChanges = computed(() => snapshot(editable) !== originalSnapshot.value)

const generatedPrompt = computed(() => buildPrompt(editable))

function snapshot(v: EditableState): string {
  return JSON.stringify(v)
}

function encodeForMeta(text: string): string {
  return text.replace(/\n/g, '\\n').replace(/\r/g, '')
}

function decodeFromMeta(text: string): string {
  return text.replace(/\\n/g, '\n')
}

function buildPrompt(v: EditableState): string {
  const extra = v.extraRules.trim() || '无'
  return `<!-- EDITABLE_PARAMS
CORE_TASK=${v.coreTask}
EVENT_GAP_NOTE=${v.eventGapNote}
LONG_PAUSE_SEC=${Math.min(10, Math.max(1, Number(v.longPauseSec) || 3))}
EXTRA_RULES=${encodeForMeta(extra)}
-->

## 核心任务：${v.coreTask}

[非常重要] ${v.eventGapNote}

你是一位专业的家庭生活场景内容结构分析师，你的任务是**从转录文本片段中识别完整的家庭生活事件**，并将每个事件内部的语音文本片段进行合并，返回每个完整事件的完整时间戳。

### 完整事件的特征：
- 语义完整性：一个完整事件应包含完整的家庭生活场景或话题
- 时间连续性：事件内部片段在时间上连续或紧密相关
- 逻辑连贯性：事件内部互动围绕同一主题或场景展开

---

## 输入格式
你将收到一个 JSON 对象：
{
  "segments": [
    { "text": "...", "start_time": 0.0, "end_time": 1.2 }
  ]
}

---

## 事件识别原则
### 事件合并规则：
- 同一场景不同环节应合并
- 连续且相关的对话应合并
- 在明显话题转换、场景切换、长停顿处划分事件
- 结合上下文线索（称呼、语气、动作描述）判断延续关系

### 事件拆分规则：
- 明显话题转换
- 明显场景切换
- 长停顿超过 ${v.longPauseSec} 秒且内容不相关

### 事件不可拆分规则：
- 明显前后逻辑链
- 引用内容可由上下文判断为同一事件
- 同一话题连续叙述不应被简短回应打断

---

## 时间戳合并规则
- start_time：事件第一个相关片段的开始时间
- end_time：事件最后一个相关片段的结束时间
- 使用秒数格式（如 12.5）

---

## 输出格式
输出必须是严格 JSON，不允许额外解释：
{
  "events": [
    {
      "title": "事件标题",
      "description": "事件描述",
      "start_time": 0.07,
      "end_time": 15.5,
      "content": "合并后的完整文本"
    }
  ]
}

字段约束：
- title：4-8 个汉字或 16 字符以内
- 必须覆盖输入中 95% 以上有价值家庭场景内容
- 若全文仅为不可用噪声，可直接返回 {}

---

## 用户补充要求
${extra}`
}

function parseEditable(content: string): EditableState | null {
  const m = content.match(/<!--\s*EDITABLE_PARAMS([\s\S]*?)-->/)
  if (!m) return null
  const block = m[1] ?? ''
  const lines = block.split('\n').map((x) => x.trim()).filter(Boolean)
  const map: Record<string, string> = {}
  for (const line of lines) {
    const idx = line.indexOf('=')
    if (idx <= 0) continue
    map[line.slice(0, idx)] = line.slice(idx + 1)
  }

  const longPauseSec = Number(map.LONG_PAUSE_SEC)
  if (!map.CORE_TASK || !map.EVENT_GAP_NOTE || Number.isNaN(longPauseSec)) return null

  return {
    coreTask: map.CORE_TASK,
    eventGapNote: map.EVENT_GAP_NOTE,
    longPauseSec: Math.min(10, Math.max(1, longPauseSec)),
    extraRules: decodeFromMeta(map.EXTRA_RULES || '')
  }
}

function applyTemplate(t: TemplatePreset) {
  editable.coreTask = t.values.coreTask
  editable.eventGapNote = t.values.eventGapNote
  editable.longPauseSec = t.values.longPauseSec
  editable.extraRules = t.values.extraRules
}

function resetEditable() {
  const obj = JSON.parse(originalSnapshot.value) as EditableState
  editable.coreTask = obj.coreTask
  editable.eventGapNote = obj.eventGapNote
  editable.longPauseSec = obj.longPauseSec
  editable.extraRules = obj.extraRules
}

function showToast(msg: string, level: 'success' | 'error' = 'success') {
  toast.value = msg
  toastLevel.value = level
  setTimeout(() => {
    toast.value = ''
  }, 2500)
}

async function loadPrompt() {
  try {
    const res = await fetch('/api/prompt')
    const data = await res.json()
    const content = String(data.content || '')
    const parsed = parseEditable(content)

    if (parsed) {
      editable.coreTask = parsed.coreTask
      editable.eventGapNote = parsed.eventGapNote
      editable.longPauseSec = parsed.longPauseSec
      editable.extraRules = parsed.extraRules
      loadHint.value = ''
    } else {
      editable.coreTask = DEFAULT_EDITABLE.coreTask
      editable.eventGapNote = DEFAULT_EDITABLE.eventGapNote
      editable.longPauseSec = DEFAULT_EDITABLE.longPauseSec
      editable.extraRules = DEFAULT_EDITABLE.extraRules
      loadHint.value = '检测到旧版自由文本 Prompt。已切换为结构化模板模式，保存后将覆盖为新模板。'
    }

    originalSnapshot.value = snapshot(editable)
    updatedAt.value = data.updated_at ?? null
  } catch {
    showToast('加载 Prompt 失败', 'error')
  }
}

async function savePrompt() {
  const payload = generatedPrompt.value
  saving.value = true
  try {
    const res = await fetch('/api/prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: payload })
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      showToast(data.error || '保存失败', 'error')
      return
    }
    const data = await res.json()
    originalSnapshot.value = snapshot(editable)
    updatedAt.value = data.updated_at
    showToast('保存成功')
  } catch {
    showToast('网络错误，保存失败', 'error')
  } finally {
    saving.value = false
  }
}

onMounted(loadPrompt)
</script>

<style scoped>
.prompt-page { display: flex; flex-direction: column; gap: 12px; }

.hint {
  border: 1px solid #fcd34d;
  background: #fffbeb;
  color: #92400e;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
}

.card {
  border: 1px solid #dbe3ee;
  border-radius: 12px;
  background: #fff;
}

.editor { padding: 12px; }
.editor-head { font-size: 14px; font-weight: 700; margin-bottom: 10px; }

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.field { display: flex; flex-direction: column; gap: 6px; }
.field span { font-size: 13px; color: #334155; }
.field small { font-size: 11px; color: #64748b; text-align: right; }
.field input,
.field textarea {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
}
.field-inline input { max-width: 120px; }
.field-wide { grid-column: 1 / -1; }

.template-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.template-bar button {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
  padding: 6px 10px;
  cursor: pointer;
}

.preview { overflow: hidden; }
.preview-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 12px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  font-size: 13px;
  font-weight: 600;
}
.updated-at { font-size: 12px; color: #64748b; font-weight: 400; }

.preview-textarea {
  width: 100%;
  min-height: 420px;
  border: none;
  outline: none;
  resize: vertical;
  padding: 12px;
  font-size: 13px;
  line-height: 1.7;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  background: #fcfcfd;
}

.preview-footer {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border-top: 1px solid #e2e8f0;
  background: #f8fafc;
}
.char-count { font-size: 12px; color: #64748b; }
.unsaved { margin-left: 8px; font-size: 12px; color: #92400e; }
.actions { display: flex; gap: 8px; }

.btn-reset,
.btn-save {
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  font-size: 12px;
  padding: 6px 10px;
  cursor: pointer;
}
.btn-reset { background: #fff; color: #334155; }
.btn-save { background: #0f766e; color: #fff; border-color: #0f766e; }
.btn-save:disabled,
.btn-reset:disabled { opacity: 0.6; cursor: not-allowed; }

.toast {
  margin-top: 4px;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
  display: inline-block;
}
.toast.success { background: #e2e8f0; color: #0f172a; }
.toast.error { background: #fee2e2; color: #991b1b; }

@media (max-width: 920px) {
  .grid { grid-template-columns: 1fr; }
}
</style>


