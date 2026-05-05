import { useState, useEffect } from 'react'
import { useChatStream } from './hooks/useChatStream'
import HomePage from './pages/HomePage'
import ChatPage from './pages/ChatPage'

export default function App() {
  const [view, setView] = useState('home')
  const { messages, isStreaming, sendMessage, clearMessages } = useChatStream()
  const [providerInfo, setProviderInfo] = useState({ provider: 'ollama', model: '' })

  useEffect(() => {
    fetch('/api/health')
      .then(r => r.json())
      .then(d => setProviderInfo({ provider: d.provider || 'ollama', model: d.model || '' }))
      .catch(() => {})
  }, [])

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
    return <HomePage onSend={handleSend} providerInfo={providerInfo} />
  }

  return (
    <ChatPage
      messages={messages}
      isStreaming={isStreaming}
      onSend={handleSend}
      onClear={handleClear}
      providerInfo={providerInfo}
    />
  )
}
