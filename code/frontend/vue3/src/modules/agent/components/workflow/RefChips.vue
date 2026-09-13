<template>
  <!-- 上游节点引用快捷插入(点击追加 {{节点ID}} 占位符) -->
  <div class="flex flex-wrap items-center gap-1 mt-1.5">
    <span class="text-[11px] text-note-sub shrink-0">插入引用:</span>
    <button
      v-for="u in upstreams" :key="u.id"
      type="button"
      class="px-1.5 py-0.5 rounded-md bg-note-soft border border-note text-[11px] font-mono text-note-sub
             hover:text-note-green hover:border-note-green transition-colors"
      :title="`插入 ${u.id} 的输出引用`"
      @click="$emit('insert', `{{${u.id}}}`)"
    >
      {{ '{' }}{{ u.id }}{{ '}' }}
    </button>
  </div>
</template>

<script setup lang="ts">
// 上游节点引用 chips(生成 {{node_id}} 模板占位符)
defineProps<{
  /** 上游节点列表 */
  upstreams: Array<{ id: string; label: string }>
}>()

defineEmits<{
  /** 插入引用文本 */
  insert: [refText: string]
}>()
</script>
