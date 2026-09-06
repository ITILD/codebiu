// src/modules/template/api/face.ts
/**
 * 人脸特征标准化接口(纯前端实现)
 * - extractFaceFeature: 从 MediaPipe FaceLandmarker 的 blendshapes 提取定长 L2 归一化特征向量
 * - cosineSimilarity / compareFaceFeatures: 两向量余弦相似度与阈值匹配判定(人脸匹配基础能力)
 * 接口以 (version, dim) 标准化, 未来可平滑替换为后端 embedding 服务或几何描述子, 调用方无感
 */

/** MediaPipe blendshape 类目(FaceLandmarkerResult.faceBlendshapes[].categories 项) */
export interface FaceBlendshapeCategory {
  index?: number
  score: number
  categoryName: string
  displayName?: string
}

/** 标准化人脸特征向量 */
export interface FaceFeatureVector {
  /** 提取器版本(维度/归一化方式变更时递增) */
  version: string
  /** 向量维度 */
  dim: number
  /** L2 归一化后的特征数据 */
  data: number[]
  /** 来源描述(如捕获时间) */
  source?: string
}

/** 两个人脸特征向量的比较结果 */
export interface FaceCompareResult {
  /** 余弦相似度 [-1, 1] */
  similarity: number
  /** 余弦距离 [0, 2] = 1 - 相似度 */
  distance: number
  /** 是否判定为同一人(相似度 >= 阈值) */
  matched: boolean
}

/** 当前特征提取器标识 */
export const FACE_FEATURE_VERSION = 'blendshapes-l2-v1'
/** 默认匹配阈值 */
export const DEFAULT_MATCH_THRESHOLD = 0.92

/**
 * 从 blendshape 类目提取标准化特征向量
 * @param categories MediaPipe 输出的 blendshape 类目(52 维, 顺序固定)
 * @param source 来源描述
 * @returns L2 归一化后的特征向量; 输入为空时返回 null
 */
export function extractFaceFeature(
  categories: FaceBlendshapeCategory[] | null | undefined,
  source?: string
): FaceFeatureVector | null {
  if (!categories || categories.length === 0) return null
  // 按 index 稳定排序, 保证任意两帧的维度顺序一致
  const sorted = [...categories].sort((a, b) => (a.index ?? 0) - (b.index ?? 0))
  const data = normalizeVector(sorted.map((c) => c.score))
  return { version: FACE_FEATURE_VERSION, dim: data.length, data, source }
}

/**
 * 向量 L2 归一化(零向量原样返回, 避免除零)
 */
export function normalizeVector(v: number[]): number[] {
  let norm = 0
  for (const x of v) norm += x * x
  norm = Math.sqrt(norm)
  if (norm === 0) return [...v]
  return v.map((x) => x / norm)
}

/**
 * 余弦相似度: 支持传裸数组或 FaceFeatureVector
 * @returns 相似度 [-1, 1]; 维度不一致时返回 NaN
 */
export function cosineSimilarity(
  a: number[] | FaceFeatureVector,
  b: number[] | FaceFeatureVector
): number {
  const va = Array.isArray(a) ? a : a.data
  const vb = Array.isArray(b) ? b : b.data
  if (va.length !== vb.length) return NaN
  let dot = 0
  let na = 0
  let nb = 0
  for (let i = 0; i < va.length; i++) {
    dot += va[i] * vb[i]
    na += va[i] * va[i]
    nb += vb[i] * vb[i]
  }
  if (na === 0 || nb === 0) return 0
  return dot / (Math.sqrt(na) * Math.sqrt(nb))
}

/**
 * 比较两个人脸特征: 余弦相似度 + 阈值匹配判定
 * @returns 维度不一致时返回 null
 */
export function compareFaceFeatures(
  a: number[] | FaceFeatureVector,
  b: number[] | FaceFeatureVector,
  threshold: number = DEFAULT_MATCH_THRESHOLD
): FaceCompareResult | null {
  const similarity = cosineSimilarity(a, b)
  if (Number.isNaN(similarity)) return null
  return {
    similarity,
    distance: 1 - similarity,
    matched: similarity >= threshold,
  }
}
