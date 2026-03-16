import { createRouter, createWebHashHistory } from 'vue-router'
import UploadPage from './pages/UploadPage.vue'
import HistoryPage from './pages/HistoryPage.vue'
import TaskDetailPage from './pages/TaskDetailPage.vue'
import PromptPage from './pages/PromptPage.vue'
import ResultDashboardPage from './pages/ResultDashboardPage.vue'

const routes = [
  { path: '/', component: UploadPage, name: 'upload' },
  { path: '/history', component: HistoryPage, name: 'history' },
  { path: '/history/:id', component: TaskDetailPage, name: 'task-detail' },
  { path: '/prompt', component: PromptPage, name: 'prompt' },
  { path: '/result/:id', component: ResultDashboardPage, name: 'result-dashboard' }
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes
})
