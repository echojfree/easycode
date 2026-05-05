import MessageList from '../components/MessageList'
import InputBar from '../components/InputBar'

export default function ChatPage({ messages, isStreaming, onSend, onClear, providerInfo }) {
  // 第一条用户消息作为标题
  const firstUserMsg = messages.find(m => m.role === 'user')
  const title = firstUserMsg
    ? firstUserMsg.content.slice(0, 40) + (firstUserMsg.content.length > 40 ? '…' : '')
    : '新对话'

  return (
    <div className="flex flex-col h-screen bg-canvas">

      {/* 顶栏 */}
      <header className="flex items-center justify-between px-5 py-3 border-b border-hairline bg-canvas flex-shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={onClear}
            className="text-muted hover:text-ink transition-colors text-sm"
            title="返回首页"
          >
            ←
          </button>
          <span className="text-sm font-medium text-ink truncate max-w-xs">{title}</span>
        </div>
        <button className="text-muted-soft hover:text-muted transition-colors text-lg" title="分享">
          ↗
        </button>
      </header>

      {/* 消息区 */}
      <main className="flex-1 overflow-y-auto px-4 py-5">
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
