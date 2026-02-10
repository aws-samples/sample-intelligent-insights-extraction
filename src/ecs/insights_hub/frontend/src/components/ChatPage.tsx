import React from 'react';
import ChatBot from './ChatBot';

const ChatPage: React.FC = () => {
  return (
    <div style={{
      height: 'calc(100vh - 64px)', // Subtract header height
      width: '100%',
      position: 'relative',
      overflow: 'hidden'
    }}>
      <ChatBot />
    </div>
  );
};

export default ChatPage;