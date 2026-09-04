// 语音 ASR/TTS 类型定义

/** 语音引擎(空串表示"自动": 由后端按 model_config 表解析默认方案) */
export type VoiceEngine = 'sherpa' | 'qwen' | ''

/** TTS 请求 */
export interface TTSRequest {
  text: string
  engine?: VoiceEngine
  speaker?: number
  speed?: number
  sample_rate?: number
}

/** ASR 识别结果 */
export interface ASRResponse {
  text: string
  engine: VoiceEngine
  elapsed: number
}

/** ASR 流式消息(WebSocket) */
export interface ASRStreamMessage {
  text: string
  is_final: boolean
  engine: VoiceEngine
}
