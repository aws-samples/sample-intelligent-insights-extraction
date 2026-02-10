import React, { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, Typography, Spin, message, Select, Layout } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, SettingOutlined } from '@ant-design/icons';
import './ChatBot.css';

const { TextArea } = Input;
const { Title, Text } = Typography;
const { Header, Content, Sider } = Layout;
const { Option } = Select;

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  images?: string[]; // 可选的图片URL数组
}

interface ModelOption {
  value: string;
  label: string;
  description: string;
}

const ChatBot: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedModel, setSelectedModel] = useState('Claude 3.5 Haiku');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const modelOptions: ModelOption[] = [
    {
      value: 'Claude 3.5 Haiku',
      label: 'Claude 3.5 Haiku',
      description: '快速响应，成本优化，适合日常对话'
    },
    {
      value: 'Claude 3.5 Sonnet v2',
      label: 'Claude 3.5 Sonnet v2',
      description: '最新版本，平衡性能与速度'
    },
    {
      value: 'Claude 3.7 Sonnet',
      label: 'Claude 3.7 Sonnet',
      description: '更强性能，适合复杂推理任务'
    },
    {
      value: 'Claude Sonnet 4',
      label: 'Claude Sonnet 4',
      description: '最新最强版本，顶级性能'
    }
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    setIsStreaming(true);

    // Create abort controller for this request
    abortControllerRef.current = new AbortController();

    try {
      // Prepare conversation history (last 10 messages to avoid token limits)
      const conversationHistory = messages.slice(-10).map(msg => ({
        role: msg.role,
        content: msg.content
      }));

      const requestBody = {
        message: userMessage.content,
        conversation_history: conversationHistory,
        model: selectedModel
      };

      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
        signal: abortControllerRef.current.signal,
        // 不设置timeout，让流式响应可以持续
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No reader available');
      }

      // Create assistant message placeholder
      const assistantMessage: Message = {
        role: 'assistant',
        content: '',
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);

      let accumulatedContent = '';

      try {
        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            break;
          }

          const chunk = new TextDecoder().decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const dataStr = line.slice(6);
                const data = JSON.parse(dataStr);

                if (data.chunk) {
                  accumulatedContent += data.chunk;
                  setMessages(prev => {
                    const newMessages = [...prev];
                    const lastMessage = newMessages[newMessages.length - 1];
                    if (lastMessage.role === 'assistant') {
                      lastMessage.content = accumulatedContent;
                    }
                    return newMessages;
                  });
                } else if (data.done) {
                  break;
                } else if (data.error) {
                  throw new Error(data.error);
                }
              } catch (parseError) {
                console.warn('Failed to parse SSE data:', line, parseError);
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }

    } catch (error: any) {
      if (error.name === 'AbortError') {
        message.info('请求已取消');
      } else {
        console.error('Error sending message:', error);
        message.error('发送消息失败，请重试');

        // Add error message
        const errorMessage: Message = {
          role: 'assistant',
          content: '抱歉，我现在无法回复。请稍后再试。',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, errorMessage]);
      }
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  return (
    <Layout className="chatbot-layout">
      <Sider
        width={300}
        collapsed={sidebarCollapsed}
        collapsible
        onCollapse={setSidebarCollapsed}
        className="chatbot-sidebar"
        theme="light"
      >
        <div className="sidebar-content">
          <div className="sidebar-header">
            <Title level={4} style={{ margin: '16px 0', color: '#1890ff' }}>
              <SettingOutlined /> 设置
            </Title>
          </div>

          {!sidebarCollapsed && (
            <>
              <div className="model-selector">
                <Text strong>选择模型</Text>
                <Select
                  value={selectedModel}
                  onChange={setSelectedModel}
                  style={{ width: '100%', marginTop: '8px' }}
                  disabled={isLoading}
                  size="large"
                  optionLabelProp="label"
                >
                  {modelOptions.map(model => (
                    <Option key={model.value} value={model.value} label={model.label}>
                      <div>
                        <div>{model.label}</div>
                        <div style={{ fontSize: '12px', color: '#666' }}>
                          {model.description}
                        </div>
                      </div>
                    </Option>
                  ))}
                </Select>
              </div>

              <div className="chat-info">
                <Text type="secondary">
                  消息数量: {messages.length}
                </Text>
                <br />
                <Text type="secondary">
                  当前模型: {modelOptions.find(m => m.value === selectedModel)?.label}
                </Text>
              </div>
            </>
          )}
        </div>
      </Sider>

      <Layout className="main-layout">
        <Header className="chatbot-header">
          <Title level={3} style={{ margin: 0, color: '#1890ff' }}>
            <RobotOutlined /> AI 智能助手
          </Title>
        </Header>

        <Content className="messages-container">
          {messages.length === 0 && (
            <div className="welcome-message">
              <RobotOutlined style={{ fontSize: '64px', color: '#1890ff', marginBottom: '24px' }} />
              <Title level={2}>欢迎使用 AI 助手</Title>
              <Text type="secondary" style={{ fontSize: '16px' }}>
                我是您的智能助手，有什么可以帮助您的吗？
              </Text>
            </div>
          )}

          {messages.map((message, index) => (
            <div key={index} className={`message ${message.role}`}>
              <div className="message-avatar">
                {message.role === 'user' ? (
                  <UserOutlined />
                ) : (
                  <RobotOutlined />
                )}
              </div>
              <Card className="message-content" size="small">
                <div className="message-text">
                  {message.content}
                </div>
                <div className="message-time">
                  {message.timestamp.toLocaleTimeString()}
                </div>
              </Card>
            </div>
          ))}

          {isLoading && messages[messages.length - 1]?.role !== 'assistant' && (
            <div className="message assistant">
              <div className="message-avatar">
                <RobotOutlined />
              </div>
              <Card className="message-content" size="small">
                <Spin size="small" /> 正在思考...
              </Card>
            </div>
          )}

          <div ref={messagesEndRef} />
        </Content>

        <div className="input-container">
          {isStreaming && (
            <div className="stop-button-container">
              <Button
                type="default"
                size="small"
                onClick={handleStopGeneration}
                style={{ marginBottom: '8px' }}
              >
                停止生成
              </Button>
            </div>
          )}

          <div style={{ display: 'flex', gap: '8px', width: '100%' }}>
            <TextArea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入你的问题... (Enter 发送，Shift+Enter 换行)"
              autoSize={{ minRows: 1, maxRows: 6 }}
              disabled={isLoading}
              style={{ resize: 'none', flex: 1 }}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSendMessage}
              disabled={isLoading || !inputValue.trim()}
              style={{
                backgroundColor: '#1890ff',
                borderColor: '#1890ff',
                height: 'auto',
                minHeight: '40px',
                alignSelf: 'stretch',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              发送
            </Button>
          </div>
        </div>
      </Layout>
    </Layout>
  );
};

export default ChatBot;