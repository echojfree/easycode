import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import ToolCallBadge from './ToolCallBadge'

/* ── SVG 图标 ─────────────────────────────────────────── */
function CopyIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <rect x="4.5" y="4.5" width="7.5" height="7.5" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
      <path d="M9.5 4.5V3a1 1 0 00-1-1H3a1 1 0 00-1 1v5.5a1 1 0 001 1H4.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  )
}

function ThumbUpIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M4.5 12.5V7L6.5 2h.3a1 1 0 011 1v3.5H11a.5.5 0 01.5.5l-.8 4.5a.5.5 0 01-.5.5H4.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
      <path d="M4.5 7H3a.5.5 0 00-.5.5v4.5a.5.5 0 00.5.5h1.5" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
    </svg>
  )
}

function ThumbDownIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M9.5 1.5V7L7.5 12h-.3a1 1 0 01-1-1V7.5H3a.5.5 0 01-.5-.5l.8-4.5a.5.5 0 01.5-.5H9.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
      <path d="M9.5 7H11a.5.5 0 01.5.5v-4.5a.5.5 0 00-.5-.5H9.5" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
    </svg>
  )
}

function RefreshIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M2 7a5 5 0 015-5c1.6 0 3 .7 3.95 1.8L12.5 2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M12.5 2v3.5H9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M12 7a5 5 0 01-5 5c-1.6 0-3-.7-3.95-1.8L1.5 12" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

/* ── 用户消息 ─────────────────────────────────────────── */
function UserMessage({ content }) {
  return (
    <div className="flex justify-end message-appear">
      <div className="max-w-[72%] bg-surface-card text-ink text-sm leading-relaxed px-4 py-3 rounded-2xl rounded-br-sm">
        {content}
      </div>
    </div>
  )
}

/* ── 助手消息 ─────────────────────────────────────────── */
function AssistantMessage({ content, toolCalls, isStreaming }) {
  return (
    <div className="flex flex-col gap-2.5 message-appear">

      {/* 品牌标记 + 名称 */}
      <div className="flex items-center gap-1.5">
        <span className="text-primary text-base leading-none select-none">✦</span>
        <span className="text-sm font-medium text-muted">easycode</span>
      </div>

      {/* 工具调用 badges */}
      {toolCalls?.map((tc, i) => (
        <ToolCallBadge key={i} toolCall={tc} />
      ))}

      {/* 回复正文（Markdown 渲染） */}
      {(content || isStreaming) && (
        <div className="markdown-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
          {/* 流式光标：仅在内容为空时显示 */}
          {isStreaming && !content && (
            <span className="inline-block w-0.5 h-4 bg-primary animate-pulse ml-0.5 align-middle" />
          )}
        </div>
      )}

      {/* 操作按钮（回复完成后显示） */}
      {!isStreaming && content && (
        <div className="flex items-center gap-1 mt-0.5">
          {[
            { Icon: CopyIcon, title: '复制' },
            { Icon: ThumbUpIcon, title: '好评' },
            { Icon: ThumbDownIcon, title: '差评' },
            { Icon: RefreshIcon, title: '重新生成' },
          ].map(({ Icon, title }) => (
            <button
              key={title}
              title={title}
              className="p-1.5 rounded-md text-muted-soft hover:text-muted hover:bg-surface-soft transition-colors"
            >
              <Icon />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── 导出 ─────────────────────────────────────────────── */
export default function MessageItem({ message, isLastAssistant, isStreaming }) {
  if (message.role === 'user') {
    return <UserMessage content={message.content} />
  }
  return (
    <AssistantMessage
      content={message.content}
      toolCalls={message.toolCalls}
      isStreaming={isLastAssistant && isStreaming}
    />
  )
}
