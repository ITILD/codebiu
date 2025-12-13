// src/types/authorization/user.ts
interface UserBase {
  username: string;
  password: string;
  email?: string;
  phone?: string;
  nickname?: string;
  avatar?: string;
  is_active?: boolean;
}

interface User extends UserBase {
  id: string;
  created_at: string; // ISO格式日期字符串
  updated_at: string; // ISO格式日期字符串
}

interface UserCreate extends UserBase {
  username: string; // 必填字段
  password: string; // 必填字段
}

interface UserUpdate extends UserBase { }

// 通用配置对象
const config = {
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

export type { User, UserCreate, UserUpdate };
export { config, formBase, rules };
