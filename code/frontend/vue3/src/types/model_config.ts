// src/types/model_config.ts

// 模型服务类型枚举
enum ModelServerType {
  OPENAI = "openai",
  DASHSCOPE = "dashscope",
  VLLM = "vllm",
  OLLAMA = "ollama",
  AWS = "aws"
}

// 模型类型枚举
enum ModelType {
  CHAT = "chat",
  EMBEDDINGS = "embeddings",
  RERANK = "rerank"
}

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

// 通用配置对象
const config = {
  tableColumns: [
    {
      prop: 'model_type', 
      label: '模型类型', 
      width: 100, 
      enum: {
        [ModelType.CHAT]: '对话',
        [ModelType.EMBEDDINGS]: '嵌入',
        [ModelType.RERANK]: '重排'
      },
      edit: {
        default: ModelType.CHAT,
        component: 'el-select',
        placeholder: '请选择模型类型',
        options: [
          { label: '对话', value: ModelType.CHAT },
          { label: '嵌入', value: ModelType.EMBEDDINGS },
          { label: '重排', value: ModelType.RERANK }
        ],
        rules: [
          { required: true, message: '请选择模型类型', trigger: 'change' }
        ]
      }
    },
    {
      prop: 'server_type', 
      label: '服务类型', 
      width: 100, 
      enum: {
        [ModelServerType.OPENAI]: 'OpenAI',
        [ModelServerType.DASHSCOPE]: 'DashScope',
        [ModelServerType.VLLM]: 'VLLM',
        [ModelServerType.OLLAMA]: 'Ollama',
        [ModelServerType.AWS]: 'AWS'
      },
      edit: {
        default: ModelServerType.OPENAI,
        component: 'el-select',
        placeholder: '请选择服务类型',
        options: [
          { label: 'OpenAI', value: ModelServerType.OPENAI },
          { label: 'DashScope', value: ModelServerType.DASHSCOPE },
          { label: 'VLLM', value: ModelServerType.VLLM },
          { label: 'Ollama', value: ModelServerType.OLLAMA },
          { label: 'AWS', value: ModelServerType.AWS }
        ],
        rules: [
          { required: true, message: '请选择服务类型', trigger: 'change' }
        ]
      }
    },
    {
      prop: 'model', 
      label: '模型标识', 
      width: 150,
      edit: {
        default: '',
        component: 'el-input',
        placeholder: '请输入模型标识名称',
        rules: [
          { required: true, message: '请输入模型标识名称', trigger: 'blur' },
          { min: 1, max: 100, message: '长度在 1 到 100 个字符', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'url', 
      label: 'API地址', 
      width: 200,
      edit: {
        default: '',
        component: 'el-input',
        placeholder: '请输入API基础URL',
        rules: [
          { max: 500, message: '长度不超过 500 个字符', trigger: 'blur' }
        ]
      }
    },
    // api_key
    {
      prop: 'api_key', 
      label: 'API密钥', 
      width: 200,
      edit: {
        default: '',
        component: 'el-input',
        placeholder: '请输入API密钥',
        rules: [
          { max: 500, message: '长度不超过 500 个字符', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'pay_in', 
      label: '输入成本', 
      width: 100,
      edit: {
        default: 0.0,
        component: 'el-input-number',
        props: { min: 0, step: 0.0001, precision: 4 },
        rules: [
          { type: 'number', min: 0, message: '成本必须大于等于0', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'pay_out', 
      label: '输出成本', 
      width: 100,
      edit: {
        default: 0.0,
        component: 'el-input-number',
        props: { min: 0, step: 0.0001, precision: 4 },
        rules: [
          { type: 'number', min: 0, message: '成本必须大于等于0', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'input_tokens', 
      label: '输入Token', 
      width: 100,
      edit: {
        default: 8192,
        component: 'el-input-number',
        props: { min: 1, step: 1 },
        rules: [
          { required: true, message: '请输入输入Token数', trigger: 'blur' },
          { type: 'number', min: 1, message: 'Token数必须大于0', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'out_tokens', 
      label: '输出Token', 
      width: 100,
      edit: {
        default: 8192,
        component: 'el-input-number',
        props: { min: 1, step: 1 },
        rules: [
          { required: true, message: '请输入输出Token数', trigger: 'blur' },
          { type: 'number', min: 1, message: 'Token数必须大于0', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'temperature', 
      label: '温度系数', 
      width: 100,
      edit: {
        default: 0.7,
        component: 'el-input-number',
        props: { min: 0, max: 2, step: 0.1 },
        rules: [
          { type: 'number', min: 0, max: 2, message: '温度系数必须在0-2之间', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'timeout', 
      label: '超时时间', 
      width: 100,
      edit: {
        default: 60,
        component: 'el-input-number',
        props: { min: 1, step: 1 },
        rules: [
          { required: true, message: '请输入超时时间', trigger: 'blur' },
          { type: 'number', min: 1, message: '超时时间必须大于0', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'no_think', 
      label: '禁用思考', 
      width: 100,
      edit: {
        default: false,
        component: 'el-switch',
        rules: []
      }
    },
    {
      prop: 'created_at',
      label: '创建时间',
      width: 180,
      formatter: (value: string | number | Date) => new Date(value).toLocaleString()
    },
    {
      prop: 'detail', 
      label: '操作', 
      width: 150, 
      button_list: {
        "edit": {
          label: '编辑',
          fuc_type: 'click', 
          fuc: (row: any) => {
            alert('点击了编辑')
          }
        },
        "delete": {
          type: 'danger', 
          label: '删除', 
          fuc_type: 'click', 
          fuc: (row: any) => {
            alert('点击了删除')
          }
        },
      }
    },
  ],
};

// 获取表单验证规则
const formBase: any = {}
const rules: any = {};
config.tableColumns.forEach(field => {
  if (field.edit) {
    formBase[field.prop] = field.edit.default;
  }
  if (field.edit && field.edit.rules) {
    rules[field.prop] = field.edit.rules;
  }
});

export { ModelServerType, ModelType };
export type { ModelConfig, ModelConfigCreate, ModelConfigUpdate };
export { config, formBase, rules };