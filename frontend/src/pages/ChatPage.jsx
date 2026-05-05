import MessageList from '../components/MessageList'
import InputBar from '../components/InputBar'

function BackIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <path d="M11 14L6 9L11 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function ShareIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
      <path d="M2.5 12.5L12.5 2.5M12.5 2.5H7.5M12.5 2.5V7.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

export default function ChatPage({ messages, isStreaming, onSend, onClear, providerInfo }) {
  // 第一条用户消息作为标题
  const firstUserMsg = messages.find(m => m.role === 'user')
  const title = firstUserMsg
    ? firstUserMsg.content.slice(0, 42) + (firstUserMsg.content.length > 42 ? '…' : '')
    : '新对话'

  return (
    <div className="flex flex-col h-screen bg-canvas">

      {/* 顶栏 */}
      <header className="flex items-center justify-between px-4 h-14 border-b border-hairline bg-canvas flex-shrink-0">
        <div className="flex items-center gap-1.5 min-w-0">
          <button
            onClick={onClear}
            className="w-8 h-8 flex-shrink-0 flex items-center justify-center rounded-md text-muted hover:text-ink hover:bg-surface-soft transition-colors"
            title="返回首页"
          >
            <BackIcon />
          </button>
          <span className="text-sm font-medium text-ink truncate">{title}</span>
        </div>
        <button
          className="w-8 h-8 flex-shrink-0 flex items-center justify-center rounded-md text-muted-soft hover:text-muted hover:bg-surface-soft transition-colors"
          title="分享"
        >
          <ShareIcon />
        </button>
      </header>

      {/* 消息区 */}
      <main className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-2xl mx-auto">
          <MessageList messages={messages} isStreaming={isStreaming} />
        </div>
      </main>

      {/* 底部输入区 */}
      <footer className="flex-shrink-0 border-t border-hairline bg-canvas">
        <InputBar onSend={onSend} isStreaming={isStreaming} providerInfo={providerInfo} />
      </footer>
    </div>
  )
}
