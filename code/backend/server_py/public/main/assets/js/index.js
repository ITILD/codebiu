// 从 Vue 的全局对象中解构出需要使用的函数
const { createApp, ref, onMounted, onBeforeUnmount } = Vue;

// 创建 Vue 应用实例
createApp({
    // setup 函数是 Composition API 的入口
    setup() {
        // --- 1. 响应式状态定义 ---
        // 使用 ref 创建响应式变量，用于存储从 API 获取的状态数据
        const status = ref(null);
        // 控制加载提示的显示
        const loading = ref(true);
        // 存储可能发生的错误信息
        const error = ref(null);
        // 用于存储定时器的ID，以便在组件销毁时清除
        let intervalId = null;

        // --- 2. 方法定义 ---
        // 异步函数，用于从服务器获取状态数据
        const fetchStatus = async () => {
            loading.value = true;
            error.value = null;
            try {
                // 使用 fetch API 调用后端的 /server_status/status_cache 接口
                const response = await fetch('./server_status/status_cache');

                // 如果网络请求失败(如404, 500等)，则抛出错误
                if (!response.ok) {
                    throw new Error(`网络请求失败，状态码: ${response.status}`);
                }

                // 解析返回的 JSON 数据并更新 status
                status.value = await response.json();

            } catch (err) {
                // 如果在 try 块中发生任何错误，则捕获它
                console.error("获取服务器状态失败:", err);
                error.value = "无法加载服务器状态，请检查网络或联系管理员。";
                status.value = null; // 出错时清空旧数据
            } finally {
                // 无论成功还是失败，最后都将加载状态设置为 false
                loading.value = false;
            }
        };

        // --- 3. 生命周期钩子 ---
        // onMounted 会在组件挂载到 DOM 后执行
        onMounted(() => {
            // 1. 立即获取一次状态数据
            fetchStatus();
            // 2. 设置一个定时器，每 60 秒自动调用 fetchStatus 方法刷新数据
            intervalId = setInterval(fetchStatus, 60000);
        });

        // onBeforeUnmount 会在组件从 DOM 中卸载前执行
        onBeforeUnmount(() => {
            // 清除定时器，以防止组件销毁后继续发起网络请求，避免内存泄漏
            clearInterval(intervalId);
        });

        // --- 4. 返回 ---
        // 从 setup 函数返回的任何 ref 或函数都可以在模板中直接使用
        return {
            status,
            loading,
            error
        };
    }
}).mount('#app'); // 将 Vue 应用实例挂载到 ID 为 'app' 的 DOM 元素上