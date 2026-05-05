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

/* ── FileChip 组件 ────────────────────────────────────────── */
function FileChip({ file, onRemove, disabled }) {
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
      {!disabled && (
        <button
          onClick={onRemove}
          className="ml-0.5 w-4 h-4 flex items-center justify-center rounded text-muted-soft hover:text-muted hover:bg-hairline transition-colors leading-none"
          title="移除"
          aria-label={`移除 ${file.name}`}
        >
          ×
        </button>
      )}
    </div>
  )
}

/* ── InputBar 主组件 ──────────────────────────────────────── */
export default function InputBar({ onSend, isStreaming, providerInfo }) {
  const providerLabel = providerInfo?.provider === 'openai'
    ? (providerInfo.model || 'OpenAI')
    : 'Ollama'

  const [input, setInput]   = useState('')
  const [files, setFiles]   = useState([])
  const fileInputRef         = useRef(null)

  const handleFileSelect = async (e) => {
    const list = e.target.files
    e.target.value = ''
    if (!list?.length) return
    const processed = await processFiles(list)
    setFiles(prev => [...prev, ...processed])
  }

  const removeFile = (idx) => setFiles(prev => prev.filter((_, i) => i !== idx))

  const hasContent = input.trim() || files.some(f => f.content !== null)
  const canSend    = hasContent && !isStreaming

  const handleSubmit = (e) => {
    e?.preventDefault()
    if (!canSend) return
    const msg = buildMessageWithFiles(input, files)
    if (!msg) return
    onSend(msg)
    setInput('')
    setFiles([])
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

        <div className="bg-canvas border border-hairline rounded-xl">

          {/* 文件 chips（有文件时显示） */}
          {files.length > 0 && (
            <div className="flex flex-wrap gap-1.5 px-3 pt-3 pb-1">
              {files.map((f, i) => (
                <FileChip
                  key={i}
                  file={f}
                  onRemove={() => removeFile(i)}
                  disabled={isStreaming}
                />
              ))}
            </div>
          )}

          {/* 主输入行 */}
          <div className="flex items-end gap-2 px-3 py-2">

            {/* 隐藏文件 input */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".txt,.md,.markdown,.py,.js,.jsx,.ts,.tsx,.json,.yaml,.yml,.toml,.css,.scss,.html,.htm,.xml,.svg,.sh,.go,.rs,.java,.kt,.cpp,.c,.h,.rb,.php,.swift,.sql,.csv,.log,.pdf,.doc,.docx,.xls,.xlsx"
              className="hidden"
              onChange={handleFileSelect}
            />

            {/* 附件按钮 */}
            <button
              type="button"
              onClick={() => !isStreaming && fileInputRef.current?.click()}
              disabled={isStreaming}
              className="w-7 h-7 flex-shrink-0 rounded-pill bg-surface-soft flex items-center justify-center text-muted text-base leading-none self-end mb-0.5 hover:bg-hairline disabled:opacity-50 transition-colors"
              title="添加文件（支持文本、PDF、Word、Excel，最大 5 MB）"
            >
              +
            </button>

            {/* 文本输入 */}
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isStreaming ? '请等待回复…' : '继续对话…'}
              disabled={isStreaming}
              rows={1}
              style={{ resize: 'none' }}
              className="flex-1 text-sm text-ink placeholder-muted-soft bg-transparent outline-none leading-relaxed py-1.5 min-h-[36px] max-h-[160px] overflow-y-auto disabled:cursor-not-allowed"
              onInput={e => {
                e.target.style.height = 'auto'
                e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`
              }}
            />

            {/* 模型标签 + 发送 */}
            <div className="flex items-center gap-2 flex-shrink-0 self-end mb-0.5">
              <span className="text-xs text-muted hidden sm:flex items-center gap-0.5 select-none">
                {providerLabel}
                <span className="text-muted-soft ml-0.5"><ChevronDown /></span>
              </span>
              <button
                onClick={handleSubmit}
                disabled={!canSend}
                className="w-7 h-7 rounded-pill bg-primary flex items-center justify-center text-on-primary disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary-active transition-colors"
                title="发送"
              >
                {isStreaming
                  ? <span className="w-2 h-2 rounded-sm bg-on-primary animate-pulse" />
                  : <SendIcon />}
              </button>
            </div>
          </div>
        </div>

        <p className="text-center text-[10px] text-muted-soft mt-1.5 select-none">
          easycode 由本地 AI 驱动，可能出错，请核实重要信息。
        </p>
      </div>
    </div>
  )
}
