// src/types/template.ts
interface TemplateBase {
  pid?: string;
  value?: number;
  name: string;
  description?: string;
  is_active?: boolean;
}

interface Template extends TemplateBase {
  id: string;
  created_at: string; // ISO格式日期字符串
  updated_at: string; // ISO格式日期字符串
}

interface TemplateCreate extends TemplateBase {
  name: string; // 必填字段
}

interface TemplateUpdate {
  pid?: string;
  value?: number;
  name?: string;
  description?: string;
  is_active?: boolean;
}

// 通用配置对象
const config = {
  // search
  // add
  // download
  tableColumns: [
    // { prop: 'id', label: 'ID', width: 180 },
    {
      prop: 'name', label: '名称', width: 100, edit: {
        default: '',
        component: 'el-input',
        placeholder: '请输入模板名称',
        rules: [
          { required: true, message: '请输入模板名称', trigger: 'blur' },
          { min: 1, max: 50, message: '长度在 1 到 50 个字符', trigger: 'blur' }
        ]
      }
    },
  
    {
      prop: 'value', label: '数值', width: 100, edit: {
        default: 0,
        component: 'el-input-number',
        props: { min: 0, step: 1 },
        rules: [
          { required: true, message: '请输入数值', trigger: 'blur' },
          { type: 'number', min: 0, message: '数值必须大于等于0', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'description', label: '描述', width: 200, edit: {
        default: '',
        component: 'el-input',
        props: { type: 'textarea', rows: 3 },
        placeholder: '请输入模板描述',
        rules: [
          { max: 200, message: '长度不超过 200 个字符', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'created_at',
      label: '创建时间',
      width: 180,
      formatter: (value: string | number | Date) => new Date(value).toLocaleString()
    },
    // //////////////////////////////////操作/////////////////////////
    {
      prop: 'detail', label: '操作', width: 100, button_list: {
        "edit": {
          label: '编辑',
          fuc_type: 'click', fuc: (row: any) => {
            alert('点击了编辑')
          }
        },
        "delete": {
          type: 'danger', label: '删除', fuc_type: 'click', fuc: (row: any) => {
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

export type { Template, TemplateCreate, TemplateUpdate };
export { config, formBase, rules };