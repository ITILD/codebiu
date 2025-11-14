const { createApp, ref, reactive, computed, onMounted, onUnmounted } = Vue;

createApp({
  setup() {
    // 数据
    const templates = ref([]);
    const loading = ref(false);
    const error = ref('');
    const success = ref('');
    const lastId = ref('');
    const hasMore = ref(true);
    const currentPage = ref(1);
    const pageSize = ref(10);
    const totalCount = ref(0);
    // 新增：列表模式（'pagination' 或 'scroll'）
    const listMode = ref('pagination');

    // 表单数据
    const formData = reactive({
      name: '',
      description: '',
      value: 0,
      is_active: true
    });

    // 编辑模式
    const editMode = ref(false);
    const currentId = ref('');
    const showModal = ref(false);
    const showDeleteModal = ref(false);
    const deleteId = ref('');

    // API基础URL
    const API_BASE_URL = '../templates';

    // 获取模板列表（分页）
    const fetchTemplates = async () => {
      try {
        loading.value = true;
        error.value = '';
        
        const response = await fetch(`${API_BASE_URL}/list?page=${currentPage.value}&pageSize=${pageSize.value}`);
        const data = await response.json();
        
        templates.value = data.items;
        totalCount.value = data.total;
      } catch (err) {
        error.value = `获取模板列表失败: ${err.message}`;
      } finally {
        loading.value = false;
      }
    };

    // 初始化滚动加载
    const initScrollMode = async () => {
      try {
        loading.value = true;
        error.value = '';
        
        // 重置数据
        templates.value = [];
        lastId.value = '';
        hasMore.value = true;
        
        // 获取第一页数据
        const response = await fetch(`${API_BASE_URL}/scroll?limit=${pageSize.value}`);
        const data = await response.json();
        
        if (data.items.length > pageSize.value) {
          templates.value = data.items.slice(0, -1);
          lastId.value = data.items[data.items.length - 2].id;
          hasMore.value = true;
        } else {
          templates.value = data.items;
          hasMore.value = data.items.length === pageSize.value;
          if (data.items.length > 0) {
            lastId.value = data.items[data.items.length - 1].id;
          }
        }
      } catch (err) {
        error.value = `加载数据失败: ${err.message}`;
      } finally {
        loading.value = false;
      }
    };

    // 滚动加载更多
    const fetchMore = async () => {
      if (loading.value || !hasMore.value || listMode.value !== 'scroll') return;
      
      try {
        loading.value = true;
        error.value = '';
        
        const params = new URLSearchParams();
        if (lastId.value) {
          params.append('last_id', lastId.value);
        }
        params.append('limit', pageSize.value);
        
        const response = await fetch(`${API_BASE_URL}/scroll?${params.toString()}`);
        const data = await response.json();
        
        if (data.items.length > pageSize.value) {
          // 去掉多余的一条（用于判断是否还有更多）
          templates.value = [...templates.value, ...data.items.slice(0, -1)];
          lastId.value = data.items[data.items.length - 2].id;
          hasMore.value = true;
        } else {
          templates.value = [...templates.value, ...data.items];
          hasMore.value = data.items.length === pageSize.value;
          if (data.items.length > 0) {
            lastId.value = data.items[data.items.length - 1].id;
          }
        }
      } catch (err) {
        error.value = `加载更多失败: ${err.message}`;
      } finally {
        loading.value = false;
      }
    };

    // 切换列表模式
    const toggleListMode = () => {
      if (listMode.value === 'pagination') {
        listMode.value = 'scroll';
        initScrollMode();
      } else {
        listMode.value = 'pagination';
        currentPage.value = 1;
        fetchTemplates();
      }
    };

    // 创建新模板
    const createTemplate = async () => {
      try {
        loading.value = true;
        error.value = '';
        
        const response = await fetch(API_BASE_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(formData)
        });
        
        if (response.ok) {
          success.value = '创建成功';
          resetForm();
          showModal.value = false;
          // 根据当前模式刷新数据
          if (listMode.value === 'pagination') {
            if (currentPage.value === 1) {
              fetchTemplates();
            } else {
              currentPage.value = 1;
              fetchTemplates();
            }
          } else {
            initScrollMode();
          }
          setTimeout(() => {
            success.value = '';
          }, 3000);
        } else {
          const data = await response.json();
          error.value = `创建失败: ${data.detail || '未知错误'}`;
        }
      } catch (err) {
        error.value = `创建失败: ${err.message}`;
      } finally {
        loading.value = false;
      }
    };

    // 更新模板
    const updateTemplate = async () => {
      try {
        loading.value = true;
        error.value = '';
        
        const response = await fetch(`${API_BASE_URL}/${currentId.value}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(formData)
        });
        
        if (response.ok) {
          success.value = '更新成功';
          resetForm();
          showModal.value = false;
          editMode.value = false;
          // 根据当前模式刷新数据
          if (listMode.value === 'pagination') {
            fetchTemplates();
          } else {
            initScrollMode();
          }
          setTimeout(() => {
            success.value = '';
          }, 3000);
        } else {
          const data = await response.json();
          error.value = `更新失败: ${data.detail || '未知错误'}`;
        }
      } catch (err) {
        error.value = `更新失败: ${err.message}`;
      } finally {
        loading.value = false;
      }
    };

    // 删除模板
    const deleteTemplate = async () => {
      try {
        loading.value = true;
        error.value = '';
        
        const response = await fetch(`${API_BASE_URL}/${deleteId.value}`, {
          method: 'DELETE'
        });
        
        if (response.ok) {
          success.value = '删除成功';
          showDeleteModal.value = false;
          // 根据当前模式刷新数据
          if (listMode.value === 'pagination') {
            fetchTemplates();
          } else {
            initScrollMode();
          }
          setTimeout(() => {
            success.value = '';
          }, 3000);
        } else {
          const data = await response.json();
          error.value = `删除失败: ${data.detail || '未知错误'}`;
        }
      } catch (err) {
        error.value = `删除失败: ${err.message}`;
      } finally {
        loading.value = false;
      }
    };

    // 查看模板详情
    const getTemplate = async (id) => {
      try {
        const response = await fetch(`${API_BASE_URL}/${id}`);
        const data = await response.json();
        return data;
      } catch (err) {
        error.value = `获取模板详情失败: ${err.message}`;
        return null;
      }
    };

    // 打开编辑模态框
    const openEditModal = async (id) => {
      currentId.value = id;
      editMode.value = true;
      
      const template = await getTemplate(id);
      if (template) {
        formData.name = template.name || '';
        formData.description = template.description || '';
        formData.value = template.value || 0;
        formData.is_active = template.is_active !== undefined ? template.is_active : true;
        showModal.value = true;
      }
    };

    // 打开创建模态框
    const openCreateModal = () => {
      resetForm();
      editMode.value = false;
      showModal.value = true;
    };

    // 打开删除确认模态框
    const openDeleteModal = (id) => {
      deleteId.value = id;
      showDeleteModal.value = true;
    };

    // 重置表单
    const resetForm = () => {
      formData.name = '';
      formData.description = '';
      formData.value = 0;
      formData.is_active = true;
      currentId.value = '';
    };

    // 分页处理
    const goToPage = (page) => {
      if (page < 1 || page > Math.ceil(totalCount.value / pageSize.value)) return;
      currentPage.value = page;
      fetchTemplates();
    };

    // 处理滚动加载
    const handleScroll = () => {
      if (loading.value || listMode.value !== 'scroll') return;
      
      const scrollPosition = window.scrollY + window.innerHeight;
      const documentHeight = document.documentElement.scrollHeight;
      
      if (scrollPosition >= documentHeight - 100 && hasMore.value) {
        fetchMore();
      }
    };

    // 生命周期
    onMounted(() => {
      if (listMode.value === 'pagination') {
        fetchTemplates();
      } else {
        initScrollMode();
      }
      window.addEventListener('scroll', handleScroll);
    });

    onUnmounted(() => {
      window.removeEventListener('scroll', handleScroll);
    });

    // 计算属性 - 总页数
    const totalPages = computed(() => {
      return Math.ceil(totalCount.value / pageSize.value);
    });

    // 计算属性 - 页码范围
    const pageRange = computed(() => {
      const start = Math.max(1, currentPage.value - 2);
      const end = Math.min(start + 4, totalPages.value);
      return Array.from({ length: end - start + 1 }, (_, i) => start + i);
    });

    return {
      templates,
      loading,
      error,
      success,
      currentPage,
      pageSize,
      totalCount,
      formData,
      editMode,
      showModal,
      showDeleteModal,
      hasMore,
      totalPages,
      pageRange,
      listMode, // 导出新模式变量
      fetchTemplates,
      fetchMore,
      createTemplate,
      updateTemplate,
      deleteTemplate,
      openEditModal,
      openCreateModal,
      openDeleteModal,
      goToPage,
      toggleListMode // 导出新模式切换函数
    };
  }
}).mount('#app');