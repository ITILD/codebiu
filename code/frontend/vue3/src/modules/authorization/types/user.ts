// src/modules/authorization/types/user.ts
interface UserBase {
  username: string;
  password: string;
  dept_id?: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  is_active?: boolean;
}

interface User extends UserBase {
  id: string;
  created_at: string;
  updated_at: string;
}

interface UserCreate extends UserBase {
  username: string;
  password: string;
}

interface UserUpdate {
  username?: string;
  password?: string;
  dept_id?: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  is_active?: boolean;
}

// 表格列配置类型(动态表单渲染所需的宽松类型)
interface TableColumnEdit {
  default?: any;
  component: string;
  placeholder?: string;
  rules?: any[];
  props?: Record<string, any>;
}

interface TableColumn {
  prop: string;
  label: string;
  width?: number;
  formatter?: (value: string | number | Date) => string;
  button_list?: Record<string, {
    type?: any;
    label: string;
    fuc_type: string;
    fuc: (row: any) => void;
  }>;
  edit?: TableColumnEdit;
}

// 通用配置对象
const config: { tableColumns: TableColumn[] } = {
  // search
  // add
  // download
  tableColumns: [
    {
      prop: 'username', label: '用户名', width: 120, edit: {
        default: '',
        component: 'el-input',
        placeholder: '请输入用户名',
        rules: [
          { required: true, message: '请输入用户名', trigger: 'blur' },
          { min: 3, max: 50, message: '长度在 3 到 50 个字符', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'email', label: '邮箱', width: 150, edit: {
        default: '',
        component: 'el-input',
        placeholder: '请输入邮箱地址',
        rules: [
          { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'phone', label: '电话', width: 120, edit: {
        default: '',
        component: 'el-input',
        placeholder: '请输入电话号码',
        rules: [
          { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号码', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'nickname', label: '昵称', width: 100, edit: {
        default: '',
        component: 'el-input',
        placeholder: '请输入昵称',
        rules: [
          { max: 50, message: '长度不超过 50 个字符', trigger: 'blur' }
        ]
      }
    },
    {
      prop: 'is_active', label: '状态', width: 80, edit: {
        default: true,
        component: 'el-switch',
        props: { activeText: '启用', inactiveText: '禁用' }
      }
    },
    {
      prop: 'created_at',
      label: '创建时间',
      width: 180,
      formatter: (value: string | number | Date) => new Date(value).toLocaleString()
    },
    {
      prop: 'updated_at',
      label: '更新时间',
      width: 180,
      formatter: (value: string | number | Date) => new Date(value).toLocaleString()
    },
    // //////////////////////////////////操作/////////////////////////
    {
      prop: 'detail', label: '操作', width: 120, button_list: {
        "edit": {
          label: '编辑',
          fuc_type: 'click', fuc: (row: unknown) => {
            alert('点击了编辑')
          }
        },
        "delete": {
          type: 'danger', label: '删除', fuc_type: 'click', fuc: (row: unknown) => {
            alert('点击了删除')
          }
        },
      }
    },
  ],
};

// 获取表单验证规则
const formBase: Record<string, any> = {}
const rules: Record<string, any> = {};
config.tableColumns.forEach(field => {
  if (field.edit) {
    formBase[field.prop] = field.edit.default;
  }
  if (field.edit && field.edit.rules) {
    rules[field.prop] = field.edit.rules;
  }
});

export type { User, UserCreate, UserUpdate };
export { config, formBase, rules };
