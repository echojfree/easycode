import { useState } from 'react'

export default function InputBar({ onSend, isStreaming }) {
  const [input, setInput] = useState('')

  const handleSubmit = (e) => {
    e?.preventDefault()
    if (!input.trim() || isStreaming) return
    onSend(input.trim())
    setInput('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="px-4 py-3">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-end gap-2 bg-white border border-hairline rounded-xl px-3 py-2 shadow-sm">
          {/* + 按钮 */}
          <button
            type="button"
            className="w-7 h-7 flex-shrink-0 rounded-pill bg-surface-soft flex items-center justify-center text-muted text-lg leading-none self-end mb-0.5"
            title="附件（暂未实现）"
          >
            +
          </button>

          {/* 输入框 */}
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isStreaming ? '请等待回复…' : 'Write a message...'}
            disabled={isStreaming}
            rows={1}
            style={{ resize: 'none' }}
            className="flex-1 text-sm text-ink placeholder-muted-soft bg-transparent outline-none leading-relaxed py-1.5 min-h-[36px] max-h-[160px] overflow-y-auto disabled:cursor-not-allowed"
            onInput={e => {
              e.target.style.height = 'auto'
              e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`
            }}
          />

          {/* 右侧：model 选择器 + 发送 */}
          <div className="flex items-center gap-2 flex-shrink-0 self-end mb-0.5">
            <span className="text-xs text-muted hidden sm:block">
              Ollama <span className="text-muted-soft">∨</span>
            </span>
            <button
              onClick={handleSubmit}
              disabled={!input.trim() || isStreaming}
              className="w-7 h-7 rounded-pill bg-primary flex items-center justify-center text-on-primary disabled:opacity-40 disabled:cursor-not-allowed"
              title="发送"
            >
              {isStreaming ? (
                <span className="w-2 h-2 rounded-sm bg-on-primary animate-pulse" />
              ) : (
                <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                  <path d="M7 2L7 12M7 2L3 6M7 2L11 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* 免责声明 */}
        <p className="text-center text-[10px] text-muted-soft mt-1.5">
          easycode 由本地 Ollama 驱动，可能出错，请核实重要信息。
        </p>
      </div>
    </div>
  )
}
