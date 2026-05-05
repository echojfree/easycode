import { useState } from 'react'

const PILLS = [
  { icon: '✏️', label: '写作' },
  { icon: '📚', label: '学习' },
  { icon: '</>', label: '代码' },
  { icon: '🗂️', label: '文件操作' },
  { icon: '✦',  label: '随便聊' },
]

export default function HomePage({ onSend, providerInfo }) {
  const providerLabel = providerInfo?.provider === 'openai'
    ? (providerInfo.model || 'OpenAI')
    : 'Ollama'
  const [input, setInput] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!input.trim()) return
    onSend(input)
    setInput('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!input.trim()) return
      onSend(input)
      setInput('')
    }
  }

  return (
    <div className="min-h-screen bg-canvas flex flex-col items-center justify-center px-4 gap-8">

      {/* 计划徽章 */}
      <div className="flex items-center gap-2 px-4 py-1.5 bg-surface-card rounded-pill text-sm text-muted">
        Free plan
        <span className="text-muted-soft">·</span>
        <span className="text-primary font-medium cursor-pointer hover:underline">Upgrade</span>
      </div>

      {/* 大标题 */}
      <h1 className="font-serif text-4xl md:text-5xl text-ink text-center leading-tight tracking-tight flex items-center gap-3">
        <span className="text-primary text-3xl md:text-4xl">✳</span>
        今天我们思考什么？
      </h1>

      {/* 输入框 */}
      <form onSubmit={handleSubmit} className="w-full max-w-xl">
        <div className="bg-white border border-hairline rounded-xl p-4 shadow-sm">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="How can I help you today?"
            rows={2}
            className="w-full resize-none text-sm text-ink placeholder-muted-soft bg-transparent outline-none leading-relaxed"
          />
          <div className="flex items-center justify-between mt-3">
            <button
              type="button"
              className="w-7 h-7 rounded-pill bg-surface-soft flex items-center justify-center text-muted text-lg leading-none"
              title="附件（暂未实现）"
            >
              +
            </button>
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted flex items-center gap-1">
                {providerLabel} <span className="text-muted-soft">∨</span>
              </span>
              <button
                type="submit"
                disabled={!input.trim()}
                className="w-7 h-7 rounded-pill bg-primary flex items-center justify-center text-on-primary disabled:opacity-40 disabled:cursor-not-allowed"
                title="发送"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M7 2L7 12M7 2L3 6M7 2L11 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </form>

      {/* 快捷 pills */}
      <div className="flex flex-wrap gap-2 justify-center">
        {PILLS.map(({ icon, label }) => (
          <button
            key={label}
            onClick={() => onSend(label)}
            className="flex items-center gap-1.5 px-4 py-2 bg-canvas border border-hairline rounded-pill text-sm text-body hover:bg-surface-soft transition-colors"
          >
            <span>{icon}</span>
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}
