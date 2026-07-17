<template>
  <div flex flex-col h-full w-full bg-gray-50>
    <!-- 顶部引擎选择栏 -->
    <div p-4 border-b bg-white shadow-sm>
      <div flex flex-wrap items-center gap-4>
        <span text-sm font-medium text-gray-600>语音引擎:</span>
        <el-radio-group v-model="engine">
          <el-radio-button value="sherpa">Sherpa(默认)</el-radio-button>
          <el-radio-button value="qwen">Qwen3-ASR/TTS-1.7B</el-radio-button>
        </el-radio-group>
        <span text-xs text-gray-400>模型需放置在后端 temp_source/model/voice 目录</span>
      </div>
    </div>

    <!-- 主体内容 -->
    <div flex-1 overflow-y-auto p-4>
      <div flex flex-col lg:flex-row gap-5 max-w-7xl mx-auto>
        <!-- ============ ASR 语音识别 ============ -->
        <el-card flex-1 min-w-0>
          <template #header>
            <div flex items-center gap-2>
              <span text-lg font-bold>🎤 语音识别 ASR</span>
              <el-tag size="small" type="success">{{ engine }}</el-tag>
            </div>
          </template>

          <el-tabs v-model="asrTab">
            <!-- 音频上传 -->
            <el-tab-pane label="音频上传" name="upload">
              <div flex flex-col gap-4>
                <div flex flex-wrap items-center gap-3>
                  <el-button type="primary" @click="triggerAudioInput">选择音频</el-button>
                  <input
                    ref="audioInputRef"
                    type="file"
                    hidden
                    accept="audio/*"
                    @change="handleAudioChange"
                  />
                  <span v-if="asrFile" text-gray-600 text-sm text-ellipsis max-w-60>
                    {{ asrFile.name }}
                  </span>
                </div>

                <audio v-if="asrAudioSrc" :src="asrAudioSrc" controls w-full />

                <el-button
                  type="success"
                  :loading="asrLoading"
                  :disabled="!asrFile || asrLoading"
                  @click="recognizeUploaded"
                >
                  {{ asrLoading ? '识别中...' : '开始识别' }}
                </el-button>

                <div v-if="asrResult || asrElapsed" mt-2>
                  <div flex items-center justify-between mb-2>
                    <span font-bold>识别结果</span>
                    <span v-if="asrElapsed" text-xs text-gray-400>
                      耗时 {{ asrElapsed.toFixed(3) }}s
                    </span>
                  </div>
                  <el-input
                    v-model="asrResult"
                    type="textarea"
                    :rows="5"
                    readonly
                    placeholder="识别结果将显示在此处"
                  />
                </div>
              </div>
            </el-tab-pane>

            <!-- 实时录音流式 -->
            <el-tab-pane label="实时录音(流式)" name="stream">
              <div flex flex-col gap-4>
                <div flex flex-wrap items-center gap-3>
                  <el-button
                    :type="recording ? 'danger' : 'primary'"
                    :icon="recording ? VideoPause : Microphone"
                    @click="recording ? stopRecording() : startRecording()"
                  >
                    {{ recording ? '停止录音' : '开始录音' }}
                  </el-button>
                  <el-tag v-if="recording" type="danger" effect="dark" flex items-center gap-1>
                    <span inline-block w-2 h-2 bg-white rounded-full animate-pulse></span>
                    录音中
                  </el-tag>
                  <el-button v-if="partialText || finalText" text @click="clearAsrStream">
                    清空
                  </el-button>
                </div>

                <el-alert
                  v-if="recording"
                  title="请允许浏览器使用麦克风权限"
                  type="info"
                  :closable="false"
                  show-icon
                />

                <div mt-2>
                  <div font-bold mb-2>实时识别</div>
                  <div
                    p-3
                    bg-gray-50
                    border
                    border-gray-200
                    rounded
                    min-h-24
                    text-sm
                    leading-relaxed
                    whitespace-pre-wrap
                    break-words
                  >
                    <span>{{ finalText }}</span>
                    <span v-if="partialText" text-blue-500>{{ partialText }}</span>
                    <span
                      v-if="recording"
                      inline-block w-2 h-5 ml-1 bg-current opacity-70 animate-blink align-middle
                    ></span>
                    <span v-if="!recording && !finalText && !partialText" text-gray-400>
                      点击"开始录音"后说话，识别结果将实时显示
                    </span>
                  </div>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-card>

        <!-- ============ TTS 语音合成 ============ -->
        <el-card flex-1 min-w-0>
          <template #header>
            <div flex items-center gap-2>
              <span text-lg font-bold>🔊 语音合成 TTS</span>
              <el-tag size="small" type="success">{{ engine }}</el-tag>
            </div>
          </template>

          <div flex flex-col gap-4>
            <el-input
              v-model="ttsText"
              type="textarea"
              :rows="5"
              placeholder="请输入需要合成的文本..."
            />

            <div flex flex-wrap items-center gap-4>
              <div flex items-center gap-2>
                <span text-sm>说话人:</span>
                <el-input-number v-model="ttsSpeaker" :min="0" :max="10" size="small" />
              </div>
              <div flex items-center gap-2 flex-1 min-w-40>
                <span text-sm>语速:</span>
                <el-slider v-model="ttsSpeed" :min="0.5" :max="2" :step="0.1" flex-1 />
                <span text-xs text-gray-500 w-10>{{ ttsSpeed.toFixed(1) }}x</span>
              </div>
            </div>

            <div flex flex-wrap gap-3>
              <el-button
                type="primary"
                :loading="ttsStreaming"
                :disabled="!ttsText.trim() || ttsStreaming"
                @click="playStream"
              >
                {{ ttsStreaming ? '合成播放中...' : '流式合成并播放' }}
              </el-button>
              <el-button
                type="success"
                :loading="ttsFileLoading"
                :disabled="!ttsText.trim() || ttsFileLoading"
                @click="synthesizeFile"
              >
                {{ ttsFileLoading ? '生成中...' : '生成音频文件' }}
              </el-button>
              <el-button
                v-if="ttsFileUrl"
                tag="a"
                :href="ttsFileUrl"
                download="tts.wav"
              >
                下载 wav
              </el-button>
            </div>

            <el-progress
              v-if="ttsStreaming"
              :percentage="100"
              :indeterminate="true"
              :show-text="false"
              status="success"
            />

            <audio v-if="ttsFileUrl" :src="ttsFileUrl" controls w-full />

            <el-alert
              v-if="ttsStatus"
              :title="ttsStatus"
              :type="ttsStatusType"
              :closable="false"
              show-icon
            />
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Microphone, VideoPause } from '@element-plus/icons-vue'
import type { VoiceEngine } from '@/types/voice'
import {
  recognizeAudio,
  synthesizeAudioFile,
  synthesizeAudioStream,
  buildAsrStreamUrl,
} from '@/api/voice'

// 共享引擎
const engine = ref<VoiceEngine>('sherpa')

// ============ ASR 上传 ============
const asrTab = ref('upload')
const audioInputRef = ref<HTMLInputElement | null>(null)
const asrFile = ref<File | null>(null)
const asrAudioSrc = ref('')
const asrLoading = ref(false)
const asrResult = ref('')
const asrElapsed = ref(0)

const triggerAudioInput = () => audioInputRef.value?.click()

const handleAudioChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    asrFile.value = target.files[0]
    asrResult.value = ''
    asrElapsed.value = 0
    asrAudioSrc.value = URL.createObjectURL(asrFile.value)
  }
}

const recognizeUploaded = async () => {
  if (!asrFile.value) return
  asrLoading.value = true
  asrResult.value = ''
  try {
    const data = await recognizeAudio(asrFile.value, engine.value)
    asrResult.value = data.text
    asrElapsed.value = data.elapsed
  } catch (error) {
    ElMessage.error('识别失败: ' + (error instanceof Error ? error.message : '未知错误'))
  } finally {
    asrLoading.value = false
  }
}

// ============ ASR 实时录音流式 ============
const recording = ref(false)
const partialText = ref('')
const finalText = ref('')

let mediaStream: MediaStream | null = null
let audioCtx: AudioContext | null = null
let sourceNode: MediaStreamAudioSourceNode | null = null
let processorNode: ScriptProcessorNode | null = null
let silentGain: GainNode | null = null
let ws: WebSocket | null = null

const clearAsrStream = () => {
  partialText.value = ''
  finalText.value = ''
}

const startRecording = async () => {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true },
    })
  } catch (e) {
    ElMessage.error('无法访问麦克风: ' + (e as Error).message)
    return
  }

  partialText.value = ''
  finalText.value = ''
  recording.value = true

  audioCtx = new AudioContext()
  sourceNode = audioCtx.createMediaStreamSource(mediaStream)
  processorNode = audioCtx.createScriptProcessor(4096, 1, 1)
  // 静音输出节点，保持 ScriptProcessor 持续触发且不产生回声
  silentGain = audioCtx.createGain()
  silentGain.gain.value = 0

  ws = new WebSocket(buildAsrStreamUrl(engine.value))
  ws.binaryType = 'arraybuffer'

  ws.onopen = () => {
    processorNode!.onaudioprocess = (e: AudioProcessingEvent) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return
      const input = e.inputBuffer.getChannelData(0)
      const downsampled = downsampleBuffer(input, audioCtx!.sampleRate, 16000)
      const pcm16 = floatTo16BitPCM(downsampled)
      ws.send(pcm16)
    }
    sourceNode!.connect(processorNode!)
    processorNode!.connect(silentGain!)
    silentGain!.connect(audioCtx!.destination)
  }

  ws.onmessage = (ev: MessageEvent) => {
    try {
      const msg = JSON.parse(ev.data)
      if (msg.is_final) {
        if (msg.text) finalText.value += msg.text
        partialText.value = ''
      } else {
        partialText.value = msg.text || ''
      }
    } catch {
      /* ignore parse error */
    }
  }

  ws.onerror = () => {
    ElMessage.error('识别连接异常')
    stopRecording()
  }

  ws.onclose = () => {
    /* connection closed */
  }
}

const stopRecording = () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send('EOS')
  }
  try {
    ws?.close()
  } catch {
    /* ignore */
  }
  ws = null

  if (processorNode) {
    processorNode.disconnect()
    processorNode.onaudioprocess = null
  }
  if (sourceNode) sourceNode.disconnect()
  if (silentGain) silentGain.disconnect()
  if (audioCtx) {
    audioCtx.close()
    audioCtx = null
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop())
    mediaStream = null
  }
  processorNode = null
  sourceNode = null
  silentGain = null
  recording.value = false
}

// ============ TTS ============
const ttsText = ref('')
const ttsSpeaker = ref(0)
const ttsSpeed = ref(1.0)
const ttsStreaming = ref(false)
const ttsFileLoading = ref(false)
const ttsFileUrl = ref('')
const ttsStatus = ref('')
const ttsStatusType = ref<'success' | 'error' | 'info'>('info')

let playCtx: AudioContext | null = null

const playStream = async () => {
  if (!ttsText.value.trim()) return
  // 停止之前的播放
  if (playCtx) {
    try {
      await playCtx.close()
    } catch {
      /* ignore */
    }
  }
  ttsStreaming.value = true
  ttsStatus.value = '正在流式合成并播放...'
  ttsStatusType.value = 'info'

  playCtx = new AudioContext()
  let nextStart = playCtx.currentTime
  let received = 0

  await synthesizeAudioStream(
    {
      text: ttsText.value,
      engine: engine.value,
      speaker: ttsSpeaker.value,
      speed: ttsSpeed.value,
    },
    (pcm: Uint8Array, sampleRate: number) => {
      if (!playCtx) return
      const float32 = int16ToFloat32(pcm)
      if (float32.length === 0) return
      received += float32.length
      const buffer = playCtx.createBuffer(1, float32.length, sampleRate)
      buffer.copyToChannel(float32, 0)
      const src = playCtx.createBufferSource()
      src.buffer = buffer
      src.connect(playCtx.destination)
      const now = playCtx.currentTime
      if (nextStart < now) nextStart = now
      src.start(nextStart)
      nextStart += float32.length / sampleRate
    },
    (error: string) => {
      ttsStatus.value = '流式合成失败: ' + error
      ttsStatusType.value = 'error'
      ttsStreaming.value = false
    },
    () => {
      ttsStatus.value = received > 0 ? '播放完成' : '未收到音频数据'
      ttsStatusType.value = received > 0 ? 'success' : 'error'
      ttsStreaming.value = false
    }
  )
}

const synthesizeFile = async () => {
  if (!ttsText.value.trim()) return
  ttsFileLoading.value = true
  ttsStatus.value = '正在生成音频文件...'
  ttsStatusType.value = 'info'
  if (ttsFileUrl.value) {
    URL.revokeObjectURL(ttsFileUrl.value)
    ttsFileUrl.value = ''
  }
  try {
    const blob = await synthesizeAudioFile({
      text: ttsText.value,
      engine: engine.value,
      speaker: ttsSpeaker.value,
      speed: ttsSpeed.value,
    })
    ttsFileUrl.value = URL.createObjectURL(blob)
    ttsStatus.value = '音频文件生成完成'
    ttsStatusType.value = 'success'
  } catch (error) {
    ttsStatus.value = '生成失败: ' + (error instanceof Error ? error.message : '未知错误')
    ttsStatusType.value = 'error'
  } finally {
    ttsFileLoading.value = false
  }
}

// ============ 音频工具函数 ============
const downsampleBuffer = (buffer: Float32Array, fromRate: number, toRate: number): Float32Array => {
  if (toRate >= fromRate) return buffer
  const ratio = fromRate / toRate
  const newLen = Math.round(buffer.length / ratio)
  const result = new Float32Array(newLen)
  let offsetResult = 0
  let offsetBuffer = 0
  while (offsetResult < newLen) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio)
    let accum = 0
    let count = 0
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i]
      count++
    }
    result[offsetResult] = count > 0 ? accum / count : 0
    offsetResult++
    offsetBuffer = nextOffsetBuffer
  }
  return result
}

const floatTo16BitPCM = (input: Float32Array): ArrayBuffer => {
  const buffer = new ArrayBuffer(input.length * 2)
  const view = new DataView(buffer)
  for (let i = 0; i < input.length; i++) {
    let s = Math.max(-1, Math.min(1, input[i]))
    s = s < 0 ? s * 0x8000 : s * 0x7fff
    view.setInt16(i * 2, s, true)
  }
  return buffer
}

const int16ToFloat32 = (input: Uint8Array): Float32Array => {
  const n = Math.floor(input.length / 2)
  const result = new Float32Array(n)
  const view = new DataView(input.buffer, input.byteOffset, input.byteLength)
  for (let i = 0; i < n; i++) {
    result[i] = view.getInt16(i * 2, true) / 32768
  }
  return result
}

// ============ 清理 ============
onUnmounted(() => {
  if (recording.value) stopRecording()
  if (playCtx) {
    try {
      playCtx.close()
    } catch {
      /* ignore */
    }
  }
  if (ttsFileUrl.value) URL.revokeObjectURL(ttsFileUrl.value)
  if (asrAudioSrc.value) URL.revokeObjectURL(asrAudioSrc.value)
})
</script>
