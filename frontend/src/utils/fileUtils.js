/* ── 文件处理工具（HomePage + InputBar 共享） ─────────────── */

export const MAX_SIZE = 5 * 1024 * 1024  // 5 MB

/* 允许的扩展名 */
const ALLOWED_EXTS = new Set([
  // 文本 / 代码
  'txt','md','markdown','py','pyw','js','jsx','ts','tsx',
  'json','yaml','yml','toml','ini','cfg','conf','env',
  'css','scss','sass','less','html','htm','xml','svg',
  'sh','bash','zsh','fish','bat','cmd','ps1',
  'go','rs','java','kt','cpp','cc','cxx','c','h','hpp',
  'rb','php','swift','dart','lua','r','m','scala','ex','exs',
  'sql','graphql','gql','proto','csv','log',
  'gitignore','prettierrc','eslintrc','babelrc','editorconfig','dockerfile',
  // Office / PDF
  'pdf','doc','docx','xls','xlsx',
])

export function getExt(filename) {
  return filename.split('.').pop()?.toLowerCase() ?? ''
}

export function isSupportedFile(file) {
  return ALLOWED_EXTS.has(getExt(file.name))
}

/* ── 上传单个文件到服务器 ─────────────────────────────────── */

async function uploadToServer(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch('/api/upload', { method: 'POST', body: formData })
  if (!res.ok) throw new Error(`上传失败 (${res.status})`)
  return res.json()  // { filename, path, size }
}

/* ── 处理文件选择事件 ─────────────────────────────────────── */
/* 返回 [{ name, path, error }]                               */
/* path 为服务器返回的相对路径，error 时 path 为 null          */

export async function processFiles(fileList) {
  return Promise.all(Array.from(fileList).map(async (file) => {
    if (file.size > MAX_SIZE) {
      return { name: file.name, path: null, error: '超过 5 MB' }
    }
    if (!isSupportedFile(file)) {
      return { name: file.name, path: null, error: '不支持的格式' }
    }
    try {
      const { path } = await uploadToServer(file)
      return { name: file.name, path, error: null }
    } catch (err) {
      console.error('上传失败:', err)
      return { name: file.name, path: null, error: '上传失败' }
    }
  }))
}

/* ── 把文件列表拼接到消息文本 ─────────────────────────────── */

export function buildMessageWithFiles(text, files) {
  const parts = []
  if (text.trim()) parts.push(text.trim())
  for (const { name, path } of files) {
    if (path) {
      parts.push(`[附件：${name}，路径：${path}]`)
    }
  }
  return parts.join('\n')
}
