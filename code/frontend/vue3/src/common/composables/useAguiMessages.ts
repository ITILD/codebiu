// AG-UI 事件 → 消息内容聚合器
// 把一次 run 的 AG-UI 事件流聚合为一条助手消息所需的
// content(正文) / blocks(过程区块) / interactions(交互卡片) / error
//
// 聚合语义对标官方 TS 客户端 @ag-ui/client 的 MessageQueue:
// - TEXT_MESSAGE_CONTENT 按 messageId 串联为一条消息
// - REASONING_MESSAGE_CONTENT 按推理段拼接为思考流
// - TOOL_CALL_RESULT 携带结构化工具结果(此处为知识检索引用)
// - CUSTOM 为协议扩展点(此处消费 rag.* 业务事件)
// 差异: 官方 MessageQueue 面向通用消息快照, 本聚合器面向本项目的
// 过程区块折叠 UI, 按(stream_event_type + node)分组, 观感与旧协议一致。
import { reactive } from 'vue'
import {
  AGUI_CUSTOM_NAME,
  type AguiEvent,
  type InteractionSpec,
  type MessageInteraction,
} from '@/common/types/agui'
import type { MessageBlock } from '@/common/types/chat'

/** 意图分析节点的 reasoning 沿用"意图分析"标签(对齐 legacy 协议观感) */
const INTENT_STEP = 'intent_analysis'

/**
 * 单次 run 的 AG-UI 事件聚合器(无状态依赖, 可直接实例化)
 *
 * 映射规则:
 * - TEXT_MESSAGE_CONTENT        → content(正文)
 * - CUSTOM rag.status           → status 进度块
 * - REASONING_MESSAGE_CONTENT   → 思考块(按当前步骤区分 agent/llm thinking)
 * - CUSTOM rag.intent_result    → 分析结论块(含结构化 data)
 * - TOOL_CALL_START/ARGS/RESULT → 检索块(RESULT 结构化 results 写入 data)
 * - CUSTOM rag.interaction      → 交互卡片(interactions)
 * - RUN_ERROR                   → error + 错误块
 * - STEP_STARTED                → currentStep(供思考块归属节点)
 */
class AguiMessageAggregator {
  /** 正文(TEXT_MESSAGE_CONTENT 累积) */
  content = ''
  /** 过程区块(进度/思考/检索/结论) */
  blocks: MessageBlock[] = []
  /** 交互卡片(澄清/知识缺口补充) */
  interactions: MessageInteraction[] = []
  /** 当前步骤名(STEP_STARTED) */
  currentStep = ''
  /** RUN_ERROR 错误文本 */
  error = ''

  private seq = 0
  private toolBlocks = new Map<string, MessageBlock>()

  /** 重置(复用实例时调用) */
  reset(): void {
    this.content = ''
    this.blocks = []
    this.interactions = []
    this.currentStep = ''
    this.error = ''
    this.seq = 0
    this.toolBlocks.clear()
  }

  /** 是否有可见输出(用于过滤空消息) */
  hasVisibleOutput(): boolean {
    return Boolean(
      this.content ||
        this.error ||
        this.blocks.some((b) => b.content) ||
        this.interactions.length
    )
  }

  applyEvent(event: AguiEvent): void {
    switch (event.type) {
      case 'STEP_STARTED':
        this.currentStep = event.stepName
        break

      case 'TEXT_MESSAGE_CONTENT':
        this.content += event.delta
        break

      case 'REASONING_MESSAGE_CONTENT': {
        // 意图分析阶段的推理沿用 agent_thinking 标签, 其余归 llm_thinking
        const eventType =
          this.currentStep === INTENT_STEP ? 'agent_thinking' : 'llm_thinking'
        this.appendBlock(eventType, this.currentStep || 'reasoning', event.delta)
        break
      }

      case 'TOOL_CALL_START': {
        const block = this.appendBlock('tool_call', event.toolCallName, '')
        this.toolBlocks.set(event.toolCallId, block)
        break
      }

      case 'TOOL_CALL_ARGS': {
        // 入参增量追加到对应工具调用块
        const block = this.toolBlocks.get(event.toolCallId)
        if (block) block.content += event.delta
        break
      }

      case 'TOOL_CALL_END':
        break

      case 'TOOL_CALL_RESULT': {
        // 结构化检索结果: 解析 JSON 写入块 data(渲染优先于文本)
        const block = this.toolBlocks.get(event.toolCallId)
        if (block) {
          try {
            block.data = JSON.parse(event.content) as unknown as Record<string, unknown>
          } catch {
            block.data = null
          }
        }
        break
      }

      case 'CUSTOM': {
        this.applyCustom(event.name, event.value)
        break
      }

      case 'RUN_ERROR':
        this.error = event.message
        this.appendBlock('error', '', event.message)
        break

      default:
        // RUN_STARTED/FINISHED、文本开合、推理开合、状态快照等不产生内容
        break
    }
  }

  private applyCustom(name: string, value: Record<string, unknown>): void {
    if (name === AGUI_CUSTOM_NAME.STATUS) {
      this.appendBlock(
        'status',
        String(value.node || ''),
        String(value.message || '')
      )
    } else if (name === AGUI_CUSTOM_NAME.INTENT_RESULT) {
      this.appendBlock(
        'agent_thinking_conclusion',
        this.currentStep || INTENT_STEP,
        String(value.conclusion || ''),
        value
      )
    } else if (name === AGUI_CUSTOM_NAME.INTERACTION) {
      const spec = value as unknown as InteractionSpec
      if (spec && spec.interaction_id) {
        this.interactions.push({ spec, responded: false, response: null })
      }
    }
  }

  /**
   * 追加过程区块: 与上一块同(事件类型+节点)时连续合并, 否则新开块
   * (对齐 legacy appendEvent 的分组规则, 保证渲染观感一致)
   */
  private appendBlock(
    streamEventType: string,
    nodeName: string,
    content: string,
    data?: Record<string, unknown> | null
  ): MessageBlock {
    const last = this.blocks[this.blocks.length - 1]
    if (
      last &&
      last.stream_event_type === streamEventType &&
      last.node_name === nodeName
    ) {
      last.content += content
      if (data != null && last.data == null) last.data = data
      return last
    }
    const block: MessageBlock = {
      id: `agui-${this.seq++}-${Date.now()}`,
      node_name: nodeName,
      type: 'process',
      content,
      stream_event_type: streamEventType,
      ...(data != null ? { data } : {}),
    }
    this.blocks.push(block)
    return block
  }
}

/** 聚合结果的响应式快照(每次事件后同步, 深层变更触发视图更新) */
export interface AguiMessageSnapshot {
  content: string
  blocks: MessageBlock[]
  interactions: MessageInteraction[]
  error: string
}

/**
 * AG-UI 消息聚合 composable: 流式期间把事件聚合结果挂到助手占位消息
 *
 * 用法:
 *   const { message, applyEvent, reset, hasVisibleOutput } = useAguiMessages()
 *   streamAguiEvents(url, body, { onEvent: applyEvent })
 */
export function useAguiMessages() {
  const aggregator = new AguiMessageAggregator()
  const message = reactive<AguiMessageSnapshot>({
    content: '',
    blocks: [],
    interactions: [],
    error: '',
  })

  /** 同步聚合结果到响应式快照(拷贝引用, 保证深层更新触发渲染) */
  const applyEvent = (event: AguiEvent): void => {
    aggregator.applyEvent(event)
    message.content = aggregator.content
    message.blocks = aggregator.blocks.map((b) => ({ ...b }))
    message.interactions = aggregator.interactions.map((i) => ({
      spec: { ...i.spec },
      responded: i.responded,
      response: i.response ? { ...i.response } : null,
    }))
    message.error = aggregator.error
  }

  const reset = (): void => {
    aggregator.reset()
    message.content = ''
    message.blocks = []
    message.interactions = []
    message.error = ''
  }

  const hasVisibleOutput = (): boolean => aggregator.hasVisibleOutput()

  return { message, applyEvent, reset, hasVisibleOutput }
}
