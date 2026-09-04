// src/types/model_config.ts
// 模型配置类型定义(多类型模型: chat/embeddings/rerank/ocr/asr/tts)

/** 模型服务方案(与后端 ModelServerType 对齐) */
enum ModelServerType {
  OPENAI = "openai",
  DASHSCOPE = "dashscope",
  VLLM = "vllm",
  OLLAMA = "ollama",
  AWS = "aws",
  SHERPA = "sherpa",
  QWEN = "qwen",
}

/** 模型类型(与后端 ModelType 对齐) */
enum ModelType {
  CHAT = "chat",
  EMBEDDINGS = "embeddings",
  RERANK = "rerank",
  OCR = "ocr",
  ASR = "asr",
  TTS = "tts",
}

/** 模型类型显示选项 */
const modelTypeOptions: { label: string; value: ModelType }[] = [
  { label: '对话', value: ModelType.CHAT },
  { label: '嵌入', value: ModelType.EMBEDDINGS },
  { label: '重排', value: ModelType.RERANK },
  { label: 'OCR', value: ModelType.OCR },
  { label: '语音识别', value: ModelType.ASR },
  { label: '语音合成', value: ModelType.TTS },
]

/** 模型类型标签样式(element-plus tag type) */
const modelTypeTagType: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
  [ModelType.CHAT]: 'primary',
  [ModelType.EMBEDDINGS]: 'success',
  [ModelType.RERANK]: 'warning',
  [ModelType.OCR]: 'danger',
  [ModelType.ASR]: 'info',
  [ModelType.TTS]: 'info',
}

/** API 类方案(远程推理: 需要 url/api_key) */
const API_SERVER_OPTIONS = [
  { label: 'OpenAI', value: ModelServerType.OPENAI },
  { label: 'DashScope', value: ModelServerType.DASHSCOPE },
  { label: 'VLLM', value: ModelServerType.VLLM },
  { label: 'Ollama', value: ModelServerType.OLLAMA },
  { label: 'AWS', value: ModelServerType.AWS },
]

/** 本地推理方案(模型路径等放 extra) */
const LOCAL_SERVER_OPTIONS = [
  { label: 'Sherpa-ONNX', value: ModelServerType.SHERPA },
  { label: 'Qwen(Transformers)', value: ModelServerType.QWEN },
]

/**
 * 按模型类型返回可用的服务方案(与后端 server_types_for 对齐)
 * - 语音/OCR 类(asr/tts/ocr): sherpa/qwen 本地推理
 * - 其余(chat/embeddings/rerank): openai/dashscope/vllm/ollama/aws
 */
const serverTypeOptionsFor = (modelType: string) =>
  [ModelType.ASR, ModelType.TTS, ModelType.OCR].includes(modelType as ModelType)
    ? LOCAL_SERVER_OPTIONS
    : API_SERVER_OPTIONS

/** 模型类型中文标签 */
const modelTypeLabel = (type: string) =>
  modelTypeOptions.find(o => o.value === type)?.label ?? type

/** 方案中文标签 */
const serverTypeLabel = (type: string) =>
  [...API_SERVER_OPTIONS, ...LOCAL_SERVER_OPTIONS].find(o => o.value === type)?.label ?? type

interface ModelConfigBase {
  model_type: ModelType;
  server_type: ModelServerType;
  model: string;
  url?: string;
  api_key?: string;
  pay_in?: number;
  pay_out?: number;
  input_tokens?: number;
  out_tokens?: number;
  temperature?: number;
  timeout?: number;
  no_think?: boolean;
  /** 扩展配置(语音类: 模型路径/设备/线程等) */
  extra?: Record<string, any>;
}

interface ModelConfig extends ModelConfigBase {
  id: string;
  user_id: string;
  created_at: string; // ISO格式日期字符串
  updated_at: string; // ISO格式日期字符串
}

interface ModelConfigCreate extends ModelConfigBase {
  model: string; // 必填字段
}

interface ModelConfigUpdate {
  model_type?: ModelType;
  server_type?: ModelServerType;
  model?: string;
  url?: string;
  api_key?: string;
  pay_in?: number;
  pay_out?: number;
  input_tokens?: number;
  out_tokens?: number;
  temperature?: number;
  timeout?: number;
  no_think?: boolean;
  extra?: Record<string, any>;
}

/** extra 各方案常用键说明(编辑表单提示用) */
const extraKeyHints: Record<string, string[]> = {
  [ModelServerType.SHERPA]: [
    'asr_tokens: ASR tokens 文件(相对模型目录)',
    'tts_model / tts_tokens / tts_lexicon / tts_dict_dir: TTS 各文件路径',
    'num_threads: 推理线程数',
    'max_num_sentences: TTS 单次合成句数',
  ],
  [ModelServerType.QWEN]: [
    'device: 推理设备(cpu/cuda)',
  ],
}

export {
  ModelServerType,
  ModelType,
  modelTypeOptions,
  modelTypeTagType,
  API_SERVER_OPTIONS,
  LOCAL_SERVER_OPTIONS,
  serverTypeOptionsFor,
  modelTypeLabel,
  serverTypeLabel,
  extraKeyHints,
  type ModelConfigBase,
  type ModelConfig,
  type ModelConfigCreate,
  type ModelConfigUpdate,
}
