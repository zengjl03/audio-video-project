<template>
  <nav class="breadcrumb" aria-label="breadcrumb">
    <RouterLink
      v-for="(item, idx) in items"
      :key="`${item.label}-${idx}`"
      :to="item.to || ''"
      class="crumb"
      :class="{ current: !item.to }"
      :aria-current="!item.to ? 'page' : undefined"
    >
      {{ item.label }}
    </RouterLink>
  </nav>
</template>

<script setup lang="ts">
interface BreadcrumbItem {
  label: string
  to?: string
}

defineProps<{
  items: BreadcrumbItem[]
}>()
</script>

<style scoped>
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  padding: 12px 16px;
  border-radius: 13px;
  background: linear-gradient(145deg, #eef8f5 0%, #e8f5f1 100%);
  border: 1px solid #d6ece5;
}

.crumb {
  position: relative;
  font-size: 15px;
  color: #4b5563;
  text-decoration: none;
  padding-right: 15px;
}

.crumb:not(:last-child)::after {
  content: '/';
  position: absolute;
  right: 2px;
  top: 0;
  color: #94a3b8;
}

.crumb:hover {
  color: #0f766e;
}

.crumb.current {
  color: #0f172a;
  font-weight: 700;
  pointer-events: none;
}
</style>
