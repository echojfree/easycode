import { useState } from 'react'

export default function ToolCallBadge({ toolCall }) {
  const [expanded, setExpanded] = useState(false)
  const { tool, input, output, status } = toolCall

  return (
    <div className="inline-flex flex-col gap-1 max-w-full">
      <button
        onClick={() => status === 'done' && setExpanded(v => !v)}
        className={`
          flex items-center gap-2 px-3 py-1.5 rounded-pill text-xs
          ${status === 'running'
            ? 'bg-surface-soft text-muted cursor-default'
            : 'bg-surface-soft text-muted hover:bg-hairline transition-colors cursor-pointer'}
        `}
      >
        {/* 状态点 */}
        <span className={`
          w-1.5 h-1.5 rounded-full flex-shrink-0
          ${status === 'running' ? 'bg-primary animate-pulse' : 'bg-accent-teal'}
        `} />
        <span className="font-medium">{tool}</span>
        <span className="text-muted-soft truncate max-w-[180px]">
          {status === 'running' ? '执行中…' : (expanded ? '▲' : '▼')}
        </span>
      </button>

      {/* 展开：显示输入/输出 */}
      {expanded && status === 'done' && (
        <div className="ml-3 mt-1 p-3 bg-surface-dark rounded-lg font-mono text-xs text-on-dark-soft space-y-2">
          {input && (
            <div>
              <span className="text-muted-soft uppercase text-[10px] tracking-wider">Input</span>
              <pre className="mt-1 whitespace-pre-wrap break-all text-on-dark">{input}</pre>
            </div>
          )}
          {output && (
            <div>
              <span className="text-muted-soft uppercase text-[10px] tracking-wider">Output</span>
              <pre className="mt-1 whitespace-pre-wrap break-all">{output}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
