"use client";

import { useState, useRef, useEffect } from "react";
import { Card, Input, Button, List, Avatar, Space } from "antd";
import { SendOutlined, UserOutlined, RobotOutlined } from "@ant-design/icons";

export default function AIChat() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "您好！我是AI助手，有什么可以帮助您的吗？",
      sender: "ai",
      timestamp: new Date().toLocaleTimeString(),
    }
  ]);
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = () => {
    if (inputValue.trim() === "") return;

    // 添加用户消息
    const userMessage = {
      id: messages.length + 1,
      text: inputValue,
      sender: "user",
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages([...messages, userMessage]);
    setInputValue("");

    // 模拟AI回复
    setTimeout(() => {
      const aiResponse = {
        id: messages.length + 2,
        text: "感谢您的消息！这是一个模拟回复。在实际应用中，这里会是AI模型的回复。",
        sender: "ai",
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages(prev => [...prev, aiResponse]);
    }, 1000);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      <Card title="AI 聊天助手" className="flex-1 flex flex-col">
        <div className="flex-1 overflow-y-auto mb-4">
          <List
            dataSource={messages}
            renderItem={(message) => (
              <List.Item className="flex border-none">
                <div
                  className={`flex ${
                    message.sender === "user" ? "justify-end" : "justify-start"
                  } w-full`}
                >
                  <div
                    className={`flex items-start space-x-2 max-w-[80%] ${
                      message.sender === "user" ? "flex-row-reverse space-x-reverse" : ""
                    }`}
                  >
                    <Avatar
                      icon={
                        message.sender === "user" ? <UserOutlined /> : <RobotOutlined />
                      }
                      className={
                        message.sender === "user" 
                          ? "bg-blue-500" 
                          : "bg-green-500"
                      }
                    />
                    <div
                      className={`rounded-lg p-3 ${
                        message.sender === "user"
                          ? "bg-blue-500 text-white"
                          : "bg-gray-100"
                      }`}
                    >
                      <p>{message.text}</p>
                      <p
                        className={`text-xs mt-1 ${
                          message.sender === "user" ? "text-blue-100" : "text-gray-500"
                        }`}
                      >
                        {message.timestamp}
                      </p>
                    </div>
                  </div>
                </div>
              </List.Item>
            )}
          />
          <div ref={messagesEndRef} />
        </div>
        <div className="flex space-x-2">
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onPressEnter={handleKeyPress}
            placeholder="输入您的消息..."
            className="flex-1"
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            disabled={inputValue.trim() === ""}
          >
            发送
          </Button>
        </div>
      </Card>
    </div>
  );
}