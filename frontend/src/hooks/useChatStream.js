import { useState, useCallback } from 'react'

/**
 * SSE 流式对话 hook。
 *
 * 返回：
 *   messages       — Message 数组（{id, role, content, toolCalls}）
 *   isStreaming    — 是否正在接收流
 *   sendMessage    — (text: string) => void
 *   clearMessages  — () => void（同时清空后端历史）
 */
export function useChatStream() {
  const [messages, setMessages] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)

  const sendMessage = useCallback(async (text) => {
    if (!text.trim() || isStreaming) return

    // 1. 追加用户消息和空 assistant 占位
    const userId = `u-${Date.now()}`
    const assistantId = `a-${Date.now()}`

    setMessages(prev => [
      ...prev,
      { id: userId,      role: 'user',      content: text, toolCalls: [] },
      { id: assistantId, role: 'assistant', content: '',   toolCalls: [] },
    ])
    setIsStreaming(true)

    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      // 2. 逐块读取 SSE 流
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()   // 最后一行可能不完整，留到下次

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          let event
          try { event = JSON.parse(line.slice(6)) } catch { continue }

          if (event.type === 'token') {
            setMessages(prev => prev.map(m =>
              m.id === assistantId
                ? { ...m, content: m.content + event.content }
                : m
            ))
          } else if (event.type === 'tool_start') {
            setMessages(prev => prev.map(m =>
              m.id === assistantId
                ? { ...m, toolCalls: [...m.toolCalls, {
                    tool: event.tool,
                    input: event.input,
                    output: '',
                    status: 'running',
                  }]}
                : m
            ))
          } else if (event.type === 'tool_end') {
            setMessages(prev => prev.map(m =>
              m.id === assistantId
                ? { ...m, toolCalls: m.toolCalls.map(tc =>
                    tc.tool === event.tool && tc.status === 'running'
                      ? { ...tc, output: event.output, status: 'done' }
                      : tc
                  )}
                : m
            ))
          } else if (event.type === 'error') {
            setMessages(prev => prev.map(m =>
              m.id === assistantId
                ? { ...m, content: `Error: ${event.message}` }
                : m
            ))
            setIsStreaming(false)
            return
          } else if (event.type === 'done') {
            setIsStreaming(false)
            return
          }
        }
      }
    } catch (err) {
      setMessages(prev => prev.map(m =>
        m.id === assistantId
          ? { ...m, content: `连接失败：${err.message}` }
          : m
      ))
    } finally {
      setIsStreaming(false)
    }
  }, [isStreaming])

  const clearMessages = useCallback(async () => {
    setMessages([])
    await fetch('/api/clear', { method: 'POST' }).catch(() => {})
  }, [])

  return { messages, isStreaming, sendMessage, clearMessages }
}
