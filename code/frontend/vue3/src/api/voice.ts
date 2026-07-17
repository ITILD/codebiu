/**
 * 语音 ASR/TTS 相关 API
 */
import { http_base_server } from '@/utils/http'
import { useAuthStore } from '@/stores/auth'
import type { ASRResponse, TTSRequest, VoiceEngine } from '@/types/voice'

// 后端接口前缀(与 utils/http.ts 中 http_base_server 一致)
const API_PREFIX = '/base_server'
const authHeader = (): Record<string, string> => {
  const token = useAuthStore().authState.tokens.access.token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/**
 * 语音识别(音频上传)
 * @param audio 音频文件
 * @param engine 引擎 sherpa/qwen
 */
export const recognizeAudio = async (audio: File | Blob, engine: VoiceEngine = 'sherpa') => {
  const formData = new FormData()
  formData.append('audio', audio)
  formData.append('engine', engine)
  return http_base_server.post<ASRResponse>('/ai/voice/asr', formData)
}

/**
 * 语音合成 - 返回完整音频文件(WAV)
 * @param req TTS 请求
 * @returns Blob(audio/wav)
 */
export const synthesizeAudioFile = async (req: TTSRequest) => {
  // 直接使用 fetch 以获取 Blob
  const resp = await fetch(`${API_PREFIX}/ai/voice/tts/file`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeader()
    },
    body: JSON.stringify({
      text: req.text,
      engine: req.engine ?? 'sherpa',
      speaker: req.speaker ?? 0,
      speed: req.speed ?? 1.0,
      sample_rate: req.sample_rate ?? 22050
    })
  })
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`
    try {
      const err = await resp.json()
      if (typeof err.detail === 'string') msg = err.detail
    } catch { /* ignore */ }
    throw new Error(msg)
  }
  return resp.blob()
}

/**
 * 语音合成 - 流式返回 PCM，边收边播
 * @param req TTS 请求
 * @param onChunk 收到 PCM 字节(Uint8Array)及采样率回调
 * @param onError 错误回调
 * @param onComplete 完成回调
 */
export const synthesizeAudioStream = async (
  req: TTSRequest,
  onChunk: (pcm: Uint8Array, sampleRate: number) => void,
  onError?: (error: string) => void,
  onComplete?: () => void
) => {
  let resp: Response
  try {
    resp = await fetch(`${API_PREFIX}/ai/voice/tts/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeader()
      },
      body: JSON.stringify({
        text: req.text,
        engine: req.engine ?? 'sherpa',
        speaker: req.speaker ?? 0,
        speed: req.speed ?? 1.0,
        sample_rate: req.sample_rate ?? 22050
      })
    })
  } catch (e) {
    onError?.((e as Error).message || '请求失败')
    return
  }
  if (!resp.ok || !resp.body) {
    let msg = `HTTP ${resp.status}`
    try {
      const err = await resp.json()
      if (typeof err.detail === 'string') msg = err.detail
    } catch { /* ignore */ }
    onError?.(msg)
    return
  }

  const sampleRate = Number(resp.headers.get('x-sample-rate') || 22050)
  const reader = resp.body.getReader()
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      if (value && value.length > 0) {
        onChunk(value, sampleRate)
      }
    }
    onComplete?.()
  } catch (e) {
    onError?.((e as Error).message || '流式读取失败')
  }
}

/**
 * 构建 ASR 流式识别 WebSocket 地址
 * @param engine 引擎
 */
export const buildAsrStreamUrl = (engine: VoiceEngine = 'sherpa') => {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const token = useAuthStore().authState.tokens.access.token
  const params = new URLSearchParams({ engine })
  if (token) params.append('token', token)
  return `${proto}//${window.location.host}${API_PREFIX}/ai/voice/asr/stream?${params.toString()}`
}
