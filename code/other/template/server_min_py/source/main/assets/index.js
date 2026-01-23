// 从 Vue 的全局对象中解构出需要使用的函数 
const { createApp, ref, onMounted, onBeforeUnmount, computed } = Vue; 

// 创建 Vue 应用实例 
createApp({ 
    // setup 函数是 Composition API 的入口 
    setup() { 
        // --- 1. 响应式状态定义 --- 
        // 使用 ref 创建响应式变量，用于存储从 API 获取的用户数据 
        const users = ref([]); 
        // 控制加载提示的显示 
        const loading = ref(false); 
        // 存储可能发生的错误信息 
        const error = ref(null); 
        // 存储表单数据
        const formData = ref({
          name: '',
          email: ''
        });
        // 当前正在编辑的用户ID
        const editingUserId = ref(null);
        // API基础路径
        const apiBaseUrl = '/users';
        // const apiBaseUrl = 'http://localhost:3100/users/';

        // --- 2. 计算属性 ---
        const formTitle = computed(() => {
          return editingUserId.value ? '编辑用户' : '添加用户';
        });
        
        const submitButtonText = computed(() => {
          return editingUserId.value ? '更新用户' : '添加用户';
        });

        // --- 3. 方法定义 --- 
        // 异步函数，用于从服务器获取用户列表数据 
        const loadUsers = async () => { 
            loading.value = true; 
            error.value = null; 
            try { 
                // 使用 fetch API 调用后端的 /users 接口 
                const response = await fetch(apiBaseUrl); 

                // 如果网络请求失败(如404, 500等)，则抛出错误 
                if (!response.ok) { 
                    throw new Error('网络请求失败'); 
                } 

                // 解析返回的 JSON 数据并更新 users 
                users.value = await response.json(); 

            } catch (err) { 
                // 如果在 try 块中发生任何错误，则捕获它 
                console.error("获取用户列表失败:", err); 
                error.value = "无法加载用户列表，请检查网络或联系管理员。"; 
                users.value = []; // 出错时清空旧数据 
            } finally { 
                // 无论成功还是失败，最后都将加载状态设置为 false 
                loading.value = false; 
            }
        }; 

        // 创建用户
        const createUser = async (userData) => {
          const response = await fetch(apiBaseUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '创建用户失败');
          }

          const newUser = await response.json();
          console.log('用户创建成功:', newUser);
        };

        // 更新用户
        const updateUser = async (userId, userData) => {
          const response = await fetch(`${apiBaseUrl}/${userId}`, {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '更新用户失败');
          }

          const updatedUser = await response.json();
          console.log('用户更新成功:', updatedUser);
        };

        // 删除用户
        const deleteUser = async (userId) => {
          // 简化的确认，不使用 alert
          if (!confirm('确定要删除这个用户吗？此操作不可撤销。')) {
            return;
          }

          try {
            const response = await fetch(`${apiBaseUrl}/${userId}`, {
              method: 'DELETE'
            });

            if (!response.ok) {
              throw new Error('删除用户失败');
            }

            console.log('用户删除成功');
            loadUsers(); // 刷新列表
          } catch (err) {
            console.error('删除用户失败:', err);
            error.value = err.message;
          }
        };

        // 处理表单提交
        const handleSubmit = async () => {
          const userData = {
            name: formData.value.name.trim(),
            email: formData.value.email.trim()
          };

          try {
            if (editingUserId.value) {
              // 更新用户
              await updateUser(editingUserId.value, userData);
            } else {
              // 创建用户
              await createUser(userData);
            }

            // 重置表单并刷新用户列表
            resetForm();
            loadUsers();
          } catch (err) {
            console.error('操作失败:', err);
            error.value = err.message;
          }
        };

        // 编辑用户
        const editUser = (user) => {
          // 填充表单
          editingUserId.value = user.id;
          formData.value.name = user.name;
          formData.value.email = user.email;

          // 滚动到表单位置
          document.querySelector('.form-section').scrollIntoView({ behavior: 'smooth' });
        };

        // 处理取消编辑
        const handleCancel = () => {
          resetForm();
        };

        // 重置表单
        const resetForm = () => {
          formData.value = { name: '', email: '' };
          editingUserId.value = null;
        };

        // 格式化日期
        const formatDate = (dateString) => {
          const date = new Date(dateString);
          return date.toLocaleString('zh-CN');
        };

        // --- 4. 生命周期钩子 --- 
        // onMounted 会在组件挂载到 DOM 后执行 
        onMounted(() => { 
            // 立即获取一次用户列表数据 
            loadUsers(); 
        }); 

        // --- 5. 返回 --- 
        // 从 setup 函数返回的任何 ref 或函数都可以在模板中直接使用 
        return { 
            users,
            loading,
            error,
            formData,
            editingUserId,
            formTitle,
            submitButtonText,
            loadUsers,
            createUser,
            updateUser,
            deleteUser,
            handleSubmit,
            editUser,
            handleCancel,
            resetForm,
            formatDate
        }; 
    } 
}).mount('#app'); // 将 Vue 应用实例挂载到 ID 为 'app' 的 DOM 元素上
