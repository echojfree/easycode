import { useState } from 'react'
import { useChatStream } from './hooks/useChatStream'
import HomePage from './pages/HomePage'
import ChatPage from './pages/ChatPage'

export default function App() {
  const [view, setView] = useState('home')
  const { messages, isStreaming, sendMessage, clearMessages } = useChatStream()

  const handleSend = (text) => {
    if (!text.trim()) return
    if (view === 'home') setView('chat')
    sendMessage(text)
  }

  const handleClear = () => {
    clearMessages()
    setView('home')
  }

  if (view === 'home') {
    return <HomePage onSend={handleSend} />
  }

  return (
    <ChatPage
      messages={messages}
      isStreaming={isStreaming}
      onSend={handleSend}
      onClear={handleClear}
    />
  )
}
