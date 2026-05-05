import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import ToolCallBadge from './ToolCallBadge'

function UserMessage({ content }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[72%] bg-surface-card text-ink text-sm leading-relaxed px-4 py-2.5 rounded-2xl rounded-br-sm">
        {content}
      </div>
    </div>
  )
}

function AssistantMessage({ content, toolCalls, isStreaming }) {
  return (
    <div className="flex flex-col gap-2">
      {/* spike + 名称 */}
      <div className="flex items-center gap-1.5">
        <span className="text-primary text-sm leading-none">✳</span>
        <span className="text-xs font-semibold text-muted tracking-wide uppercase">easycode</span>
      </div>

      {/* 工具调用 badges */}
      {toolCalls?.map((tc, i) => (
        <ToolCallBadge key={i} toolCall={tc} />
      ))}

      {/* 回复正文（markdown 渲染） */}
      {(content || isStreaming) && (
        <div className="text-sm text-body leading-relaxed prose prose-sm max-w-none
                        prose-headings:font-sans prose-headings:text-ink
                        prose-strong:text-body-strong prose-strong:font-semibold
                        prose-code:text-ink prose-code:bg-surface-soft prose-code:rounded prose-code:px-1 prose-code:py-0.5 prose-code:font-mono prose-code:text-xs
                        prose-pre:bg-surface-dark prose-pre:text-on-dark prose-pre:rounded-lg prose-pre:p-4 prose-pre:font-mono prose-pre:text-xs
                        prose-a:text-primary prose-a:no-underline hover:prose-a:underline">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
          {/* 流式光标（仅在无内容时显示占位光标） */}
          {isStreaming && !content && (
            <span className="inline-block w-0.5 h-4 bg-primary animate-pulse ml-0.5 align-middle" />
          )}
        </div>
      )}

      {/* 操作按钮（完成后显示） */}
      {!isStreaming && content && (
        <div className="flex gap-3 mt-1">
          {[
            { icon: '⊡', title: '复制' },
            { icon: '👍', title: '好评' },
            { icon: '👎', title: '差评' },
            { icon: '↺',  title: '重新生成' },
          ].map(({ icon, title }) => (
            <button
              key={title}
              title={title}
              className="text-muted-soft hover:text-muted text-base transition-colors"
            >
              {icon}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

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
