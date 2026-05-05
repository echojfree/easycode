import { useState, useRef } from 'react'
import { processFiles, buildMessageWithFiles } from '../utils/fileUtils'

/* ── SVG 图标 ─────────────────────────────────────────────── */
function ChevronDown() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
      <path d="M2.5 3.5L5 6.5L7.5 3.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function SendIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M7 2L7 12M7 2L3 6M7 2L11 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function FileDocIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 12 14" fill="none" aria-hidden="true">
      <path d="M2 1h5.5L10 3.5V12a1 1 0 01-1 1H2a1 1 0 01-1-1V2a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
      <path d="M7.5 1v2.5H10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function WarnIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path d="M6 1L11 10H1L6 1z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
      <path d="M6 5v2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      <circle cx="6" cy="8.5" r="0.5" fill="currentColor"/>
    </svg>
  )
}

function FileChip({ file, onRemove }) {
  return (
    <div className={`flex items-center gap-1.5 pl-2 pr-1.5 py-1 rounded-md text-xs font-medium border select-none ${
      file.error
        ? 'bg-surface-soft text-muted border-hairline'
        : 'bg-surface-card text-body-strong border-hairline'
    }`}>
      <span className={file.error ? 'text-warning' : 'text-muted'}>
        {file.error ? <WarnIcon /> : <FileDocIcon />}
      </span>
      <span className="max-w-[110px] truncate">{file.name}</span>
      {file.error && (
        <span className="text-muted-soft text-[10px] font-normal">· {file.error}</span>
      )}
      <button
        onClick={onRemove}
        className="ml-0.5 w-4 h-4 flex items-center justify-center rounded text-muted-soft hover:text-muted hover:bg-hairline transition-colors leading-none"
        title="移除"
      >
        ×
      </button>
    </div>
  )
}

/* ── 快捷 pills ───────────────────────────────────────────── */
const PILLS = [
  { icon: '✏️', label: '写作' },
  { icon: '📚', label: '学习' },
  { icon: '</>', label: '代码' },
  { icon: '🗂️', label: '文件操作' },
  { icon: '✦',  label: '随便聊' },
]

/* ── HomePage ─────────────────────────────────────────────── */
export default function HomePage({ onSend, providerInfo }) {
  const providerLabel = providerInfo?.provider === 'openai'
    ? (providerInfo.model || 'OpenAI')
    : 'Ollama'

  const [input, setInput] = useState('')
  const [files, setFiles] = useState([])
  const fileInputRef       = useRef(null)

  const handleFileSelect = async (e) => {
    const list = e.target.files
    e.target.value = ''
    if (!list?.length) return
    const processed = await processFiles(list)
    setFiles(prev => [...prev, ...processed])
  }

  const removeFile = (idx) => setFiles(prev => prev.filter((_, i) => i !== idx))

  const hasContent = input.trim() || files.some(f => f.content !== null)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!hasContent) return
    const msg = buildMessageWithFiles(input, files)
    if (!msg) return
    onSend(msg)
    setInput('')
    setFiles([])
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!hasContent) return
      const msg = buildMessageWithFiles(input, files)
      if (!msg) return
      onSend(msg)
      setInput('')
      setFiles([])
    }
  }

  return (
    <div className="min-h-screen bg-canvas flex flex-col items-center justify-center px-4 gap-8">

      {/* 计划徽章 */}
      <div className="flex items-center gap-2 px-4 py-1.5 bg-surface-card rounded-pill text-sm text-muted select-none">
        Free plan
        <span className="text-muted-soft">·</span>
        <span className="text-primary font-medium cursor-pointer hover:text-primary-active transition-colors">升级</span>
      </div>

      {/* 大标题 */}
      <div className="text-center">
        <h1
          className="font-serif text-5xl md:text-6xl text-ink leading-tight"
          style={{ letterSpacing: '-0.03em' }}
        >
          <span className="text-primary mr-3 select-none">✦</span>
          今天我们思考什么？
        </h1>
      </div>

      {/* 输入框 */}
      <form onSubmit={handleSubmit} className="w-full max-w-2xl">
        <div className="bg-canvas border border-hairline rounded-xl">

          {/* 文件 chips */}
          {files.length > 0 && (
            <div className="flex flex-wrap gap-1.5 px-4 pt-3 pb-1">
              {files.map((f, i) => (
                <FileChip key={i} file={f} onRemove={() => removeFile(i)} />
              ))}
            </div>
          )}

          {/* 文本区 */}
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="有什么我可以帮你的？"
            rows={2}
            className="w-full resize-none text-sm text-ink placeholder-muted-soft bg-transparent outline-none leading-relaxed px-4 pt-4 pb-2"
          />

          {/* 工具栏 */}
          <div className="flex items-center justify-between px-4 pb-3">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".txt,.md,.markdown,.py,.js,.jsx,.ts,.tsx,.json,.yaml,.yml,.toml,.css,.scss,.html,.htm,.xml,.svg,.sh,.go,.rs,.java,.kt,.cpp,.c,.h,.rb,.php,.swift,.sql,.csv,.log,.pdf,.doc,.docx,.xls,.xlsx"
              className="hidden"
              onChange={handleFileSelect}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="w-7 h-7 rounded-pill bg-surface-soft flex items-center justify-center text-muted text-base leading-none hover:bg-hairline transition-colors"
              title="添加文件（支持文本、PDF、Word、Excel，最大 5 MB）"
            >
              +
            </button>
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted flex items-center gap-1 select-none">
                {providerLabel}
                <span className="text-muted-soft"><ChevronDown /></span>
              </span>
              <button
                type="submit"
                disabled={!hasContent}
                className="w-7 h-7 rounded-pill bg-primary flex items-center justify-center text-on-primary disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary-active transition-colors"
                title="发送"
              >
                <SendIcon />
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
            className="flex items-center gap-1.5 px-4 py-2 bg-canvas border border-hairline rounded-pill text-sm text-body hover:bg-surface-soft hover:text-ink transition-colors cursor-pointer"
          >
            <span className="text-base leading-none">{icon}</span>
            {label}
          </button>
        ))}
      </div>

    </div>
  )
}
