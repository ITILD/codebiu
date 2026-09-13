﻿<template>
  <!-- 严格推算结果面板: 按选中的参考体系分区展示 -->
  <div space-y-3>
    <div v-if="loading" flex items-center justify-center py-6 text-note-sub gap-2>
      <el-icon class="is-loading"><Loading /></el-icon>
      <span text-sm>正在推算参考信息...</span>
    </div>

    <template v-else-if="result">
      <!-- 五行八字 -->
      <section v-if="result.wuxing" class="ref-section">
        <div class="ref-title">☯ 五行八字</div>
        <!-- 四柱干支 -->
        <div grid grid-cols-4 gap-1.5 mb-2>
          <div
            v-for="p in result.wuxing.pillars" :key="p.label"
            rounded-lg bg-note-tint px-1 py-1.5 text-center
          >
            <div text-[10px] text-note-sub>{{ p.label }}</div>
            <div text-base font-bold text-note tracking-widest>{{ p.ganzhi }}</div>
            <div text-[10px] text-note-green>{{ p.wuxing }}</div>
          </div>
        </div>
        <!-- 五行分布条 -->
        <div flex items-center gap-2 flex-wrap mb-1.5>
          <span
            v-for="(num, w) in result.wuxing.counts" :key="w"
            text-xs px-1.5 py-0.5 rounded-md
            :class="num === 0 ? 'bg-note-card border border-dashed border-note text-note-sub' : 'bg-note-tint text-note'"
          >
            {{ w }} {{ num === 0 ? '缺' : num }}
          </span>
        </div>
        <div text-xs text-note leading-relaxed>
          日主 <b text-note-green>{{ result.wuxing.day_master }}</b>（{{ result.wuxing.strength }}），
          喜用：
          <el-tag v-for="w in result.wuxing.favorable" :key="w" size="small" effect="plain" class="!mx-0.5">
            {{ w }}
          </el-tag>
        </div>
        <div v-if="result.wuxing.canggan.length" mt-1.5 text-[10px] text-note-sub leading-relaxed>
          藏干：{{ result.wuxing.canggan.map((c) => `${c.branch}藏${c.hidden}`).join('；') }}
        </div>
      </section>

      <!-- 星座 -->
      <section v-if="result.constellation" class="ref-section">
        <div class="ref-title">✦ 星座</div>
        <div flex items-baseline gap-2 flex-wrap>
          <b text-base text-note>{{ result.constellation.name }}</b>
          <span text-xs text-note-sub>{{ result.constellation.date_range }}</span>
          <el-tag size="small" effect="plain" type="warning">{{ result.constellation.element }}象</el-tag>
        </div>
        <div mt-1 text-xs text-note-sub leading-relaxed>{{ result.constellation.traits }}</div>
      </section>

      <!-- 生肖 -->
      <section v-if="result.zodiac" class="ref-section">
        <div class="ref-title">🧧 生肖</div>
        <div flex items-baseline gap-2 flex-wrap>
          <b text-base text-note>{{ result.zodiac.name }}</b>
          <span text-xs text-note-sub>年柱 {{ result.zodiac.year_ganzhi }}</span>
        </div>
        <div mt-1 text-xs text-note-sub leading-relaxed>{{ result.zodiac.favorable_chars }}</div>
      </section>

      <!-- 塔罗牌 -->
      <section v-if="result.tarot" class="ref-section">
        <div class="ref-title">🃏 塔罗牌</div>
        <div flex items-baseline gap-2 flex-wrap>
          <b text-base text-note>{{ result.tarot.card }}</b>
          <span text-xs text-note-sub>生命灵数 {{ result.tarot.number }}</span>
        </div>
        <div mt-1 text-xs text-note-sub leading-relaxed>{{ result.tarot.meaning }}</div>
      </section>

      <!-- 姓氏五格基准 -->
      <section v-if="result.sancai" class="ref-section">
        <div class="ref-title">☰ 姓氏五格基准</div>
        <div flex items-baseline gap-2 flex-wrap>
          <span text-xs text-note-sub>康熙笔画：</span>
          <b text-note>{{ Object.entries(result.sancai.surname_strokes).map(([ch, n]) => `${ch}${n}`).join(' ') }}</b>
          <span text-xs text-note-sub>天格 {{ result.sancai.tian_ge }}</span>
        </div>
        <div v-if="result.sancai.estimated_chars.length" mt-1 text-[10px] text-note-sub>
          笔画为估计值的字：{{ result.sancai.estimated_chars.join('、') }}
        </div>
        <div mt-1 text-[10px] text-note-sub>{{ result.sancai.note }}</div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
/** 参考信息推算结果面板: 五行八字/星座/生肖/塔罗/姓氏五格基准分区展示 */
import type { ReferenceCalculateResult } from '../types/baby_name'

defineProps<{
  /** 推算结果(未选中的体系为 null, 不渲染) */
  result: ReferenceCalculateResult | null
  /** 推算中 */
  loading?: boolean
}>()
</script>

<style scoped>
/* 参考分区卡片: 统一标题行样式 */
.ref-section {
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--note-soft);
  border: 1px dashed var(--note-border);
}
.ref-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--note-accent);
  margin-bottom: 6px;
  font-family: var(--note-font-hand);
}
</style>
