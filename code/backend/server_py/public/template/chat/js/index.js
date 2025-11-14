 const { createApp, ref } = Vue;

    createApp({
      setup() {
        const name = ref('');
        const newMessage = ref('');
        const status = ref('未连接');
        const messages = ref([]);
        let ws = null;

        const addMessage = (sender, message) => {
          messages.value.push({ sender, message });
        };

        const connect = () => {
          if (!name.value.trim()) {
            alert("请输入昵称！");
            return;
          }

          const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
          const host = window.location.host;
          const wsUrl = `${protocol}//${host}/template/template_ex/ws?name=${encodeURIComponent(name.value)}`;
          console.log(wsUrl);
          ws = new WebSocket(wsUrl);

          ws.onopen = () => {
            status.value = "已连接";
            addMessage("系统", "✅ 已连接到聊天室");
          };

          ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            addMessage(data.sender, data.message);
          };

          ws.onclose = () => {
            status.value = "已断开";
            addMessage("系统", "❌ 连接已关闭");
          };

          ws.onerror = () => {
            addMessage("系统", "⚠️ WebSocket 发生错误");
          };
        };

        const disconnect = () => {
          if (ws) {
            ws.close();
            ws = null;
          }
        };

        const sendMessage = () => {
          if (!ws || ws.readyState !== WebSocket.OPEN) {
            alert("请先连接！");
            return;
          }
          if (newMessage.value.trim()) {
            ws.send(newMessage.value);
            newMessage.value = '';
          }
        };

        return {
          name,
          newMessage,
          status,
          messages,
          connect,
          disconnect,
          sendMessage
        };
      }
    }).mount('#app');