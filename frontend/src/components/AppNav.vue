<template>
  <header class="app-nav">
    <div class="app-nav__inner">
      <div class="app-nav__brand">
        <span class="brand-icon">◆</span>
        智能育儿视频分析
      </div>
      <nav class="app-nav__links">
        <RouterLink to="/" class="app-nav__item" exact-active-class="active">首页</RouterLink>
        <RouterLink to="/history" class="app-nav__item" active-class="active">历史任务</RouterLink>
        <RouterLink to="/prompt" class="app-nav__item" active-class="active">Prompt</RouterLink>
      </nav>
    </div>
  </header>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<style scoped>
.app-nav {
  position: fixed;
  inset: 0 0 auto 0;
  z-index: 100;
  height: var(--app-nav-height);
  background: var(--color-surface-glass);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: var(--shadow-nav);
  border-bottom: 1px solid var(--color-border);
}

.app-nav__inner {
  width: min(var(--app-content-max-width), var(--app-content-width));
  height: 100%;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.app-nav__brand {
  display: flex;
  align-items: center;
  gap: 11px;
  font-size: 21px;
  font-weight: 800;
  letter-spacing: -0.2px;
  color: var(--color-brand-700);
  white-space: nowrap;
}

.brand-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: var(--color-brand-500);
  color: #fff;
  border-radius: 10px;
  font-size: 14px;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(15, 155, 132, 0.3);
}

.app-nav__links {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: none;
}

.app-nav__links::-webkit-scrollbar {
  display: none;
}

.app-nav__item {
  color: var(--color-text-muted);
  text-decoration: none;
  font-size: 14px;
  font-weight: 600;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  transition: background 0.15s ease, color 0.15s ease;
  white-space: nowrap;
}

.app-nav__item:hover {
  background: var(--color-brand-soft);
  color: var(--color-brand-600);
}

.app-nav__item.active {
  background: var(--color-brand-500);
  color: #fff;
  box-shadow: 0 2px 6px rgba(15, 155, 132, 0.25);
}

@media (max-width: 768px) {
  .app-nav__inner {
    width: 100%;
    padding: 0 16px;
  }
  .app-nav__brand {
    font-size: 17px;
  }
  .brand-icon {
    width: 32px;
    height: 32px;
    font-size: 13px;
  }
  .app-nav__item {
    font-size: 13px;
    padding: 8px 12px;
  }
}
</style>
