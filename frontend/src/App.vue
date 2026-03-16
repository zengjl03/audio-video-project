<template>
  <div class="app-shell">
    <AppNav />
    <main class="app-main">
      <BreadcrumbNav :items="globalBreadcrumbs" class="global-breadcrumb" />
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'

import AppNav from './components/AppNav.vue'
import BreadcrumbNav from './components/BreadcrumbNav.vue'

const route = useRoute()

const routeLabelMap: Record<string, string> = {
  upload: '上传',
  history: '历史任务',
  'task-detail': '任务详情',
  prompt: 'Prompt',
  'result-dashboard': '结果看板',
}

const globalBreadcrumbs = computed(() => {
  const name = String(route.name || '')
  if (!name || name === 'upload') {
    return [{ label: '首页' }]
  }

  if (name === 'task-detail') {
    const id = route.params.id ? String(route.params.id) : ''
    return [
      { label: '首页', to: '/' },
      { label: '历史任务', to: '/history' },
      { label: id ? `任务 #${id}` : '任务详情' }
    ]
  }

  if (name === 'result-dashboard') {
    const id = route.params.id ? String(route.params.id) : ''
    return [
      { label: '首页', to: '/' },
      { label: '历史任务', to: '/history' },
      { label: id ? `结果 #${id}` : '结果看板' }
    ]
  }

  return [
    { label: '首页', to: '/' },
    { label: routeLabelMap[name] || '页面' }
  ]
})
</script>




