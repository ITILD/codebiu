// 性别枚举
export enum GenderEnum {
  BOY = 'boy',
  GIRL = 'girl',
  UNKNOWN = 'unknown'
}

// 名字风格枚举
export enum NameStyleEnum {
  TRADITIONAL = 'traditional', // 传统
  MODERN = 'modern', // 现代
  LITERARY = 'literary', // 文艺
  SIMPLE = 'simple', // 简约
  UNIQUE = 'unique' // 独特
}

// 宝宝基本信息
export interface NameInfoBase {
  birth_date: string // 出生日期，考虑农历描述
  birth_time: string // 出生时间，考虑时辰描述
  gender: GenderEnum // 性别
  surname: string // 姓
}

// 宝宝额外信息
export interface NameInfoEX {
  name_length?: number // 名字长度
  other?: string // 补充信息，如首选发音、禁止字符、特殊字符、数字、风格、含义等
}

// 用于推测姓名信息的完整模型
export interface NameInfoPredictFull extends NameInfoBase, NameInfoEX {
}

// 推测姓名信息的完整请求模型
export interface NameInfoPredictFullRequest extends NameInfoPredictFull {
  model_id: string // 模型 ID
}

// 五行和星座偏好
export interface NameInfoPreference {
  wuxing_preference: string[] // 五行偏好，结合 name_length 按顺序每个字的属性，可以多个
  constellation_preference: string[] // 星座偏好
}

// 完整的宝宝信息（包含偏好）
export interface NameInfoFull extends NameInfoBase, NameInfoEX, NameInfoPreference {
}

// 推测结果基础
export interface NameInfoResultBase {
  name: string // 宝宝完整名字
}

// 名字解释
export interface NameInfoResultExplanation {
  explanation_wuxing: string // 名字的五行解释
  explanation_constellation: string // 名字的星座解释
  explanation_meaning: string // 名字的寓意解释
}

export interface NameInfoResponse {
  explanation_wuxing: string // 名字的五行解释
  explanation_constellation: string // 名字的星座解释
  explanation_meaning_list:string// 名字的寓意解释列表
}

// 推测结果和解释
export interface NameInfoResult extends NameInfoResultBase, NameInfoResultExplanation {
}

// 推测结果列表
export interface NameInfoResultList {
  results: NameInfoResult[] // 推测结果列表
}
