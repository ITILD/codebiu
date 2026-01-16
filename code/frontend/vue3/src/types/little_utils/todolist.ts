// src/types/todolist.ts
interface TodolistBase {
  pid?: string;
  value?: number;
  name: string;
  description?: string;
  is_active?: boolean;
  start_at?: string; // ISO格式日期字符串
  end_at?: string; // ISO格式日期字符串
}

interface Todolist extends TodolistBase {
  id: string;
  created_at: string; // ISO格式日期字符串
  updated_at: string; // ISO格式日期字符串
}

interface TodolistCreate extends TodolistBase {
  name: string; // 必填字段
}

interface TodolistUpdate extends TodolistBase { }

// 通用配置对象 TODO
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
        placeholder: '请输入计划任务名称',
        rules: [
          { required: true, message: '请输入计划任务名称', trigger: 'blur' },
          { min: 1, max: 50, message: '长度在 1 到 50 个字符', trigger: 'blur' }
        ]
      }
    },

    {
      prop: 'value', label: '内容', width: 100, edit: {
        default: '',
        component: 'el-input',
        props: { min: 0, step: 1 },
        rules: [
          { max: 200, message: '长度不超过 200 个字符', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'description', label: '描述', width: 200, edit: {
        default: '',
        component: 'el-input',
        props: { type: 'textarea', rows: 3 },
        placeholder: '请输入计划任务描述',
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

export type { Todolist, TodolistCreate, TodolistUpdate };
export { config, formBase, rules };
