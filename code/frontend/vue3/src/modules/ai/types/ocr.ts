// 类型定义
export interface Language {
  code: string
  name: string
}

// 
export interface TimingInfo {
  total?: number
  detect?: number
  'post-detect'?: number
  classify?: number
  'post-classify'?: number
  recognize?: number
  'post-recognize'?: number
}

export interface OcrResult {
  text: string
  score: number
  box: number[][]
  index: number
}

export interface OcrResponse {
  results: OcrResult[]
  ts?: TimingInfo
  layout?: number[][]
  background?: string
}

export interface OcrResponseWithTranslation extends OcrResponse {
  results_translate: OcrResult[]
}