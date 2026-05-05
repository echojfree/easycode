import { useEffect, useRef } from 'react'
import MessageItem from './MessageItem'

export default function MessageList({ messages, isStreaming }) {
  const bottomRef = useRef(null)

  // 新消息/流式更新时自动滚到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  if (messages.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-muted text-sm">
        开始对话吧
      </div>
    )
  }

  const lastAssistantIdx = messages.map(m => m.role).lastIndexOf('assistant')

  return (
    <div className="space-y-5">
      {messages.map((msg, idx) => (
        <MessageItem
          key={msg.id}
          message={msg}
          isLastAssistant={idx === lastAssistantIdx}
          isStreaming={isStreaming}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
