import { useState, useEffect, useRef } from 'react'
import { chatApi, systemApi } from '../../services/api'
import type { ChatAttachment } from '../../services/api'
import Sparkles from './Sparkles'

/*
 * ORELIUS Chat Console — the entire app.
 * Single, fully-responsive chat window. Black & white dark theme.
 * Adapts to phone, tablet, and desktop. No navigation, no tabs — just chat.
 * Features: photo + file attachments, and a daily "wake-up" status report.
 */

type Msg = { role: 'user' | 'assistant'; content: string; files?: string[] }

const MAX_ATTACH_BYTES = 8 * 1024 * 1024 // 8MB per file

// ---- tiny, safe markdown (escape first, then bold + bullets + line breaks) ----
function escapeHtml(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function renderMarkdown(text: string) {
  const html = escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^\s*[-•]\s+(.*)$/gm, '<span class="oreo-li">$1</span>')
    .replace(/\n/g, '<br/>')
  return { __html: html }
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = String(reader.result || '')
      resolve(result.includes(',') ? result.split(',')[1] : result)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

export default function ChatConsole() {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [pending, setPending] = useState<{ name: string; media_type: string; data: string }[]>([])
  const [loading, setLoading] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const photoRef = useRef<HTMLInputElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const taRef = useRef<HTMLTextAreaElement>(null)

  const userId = 'web-user'

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // On open: (1) reload the held conversation (persists across app closes for the
  // 7-day retention window), then (2) append the daily "wake-up" report once/day.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      // 1) Load the persisted conversation so it isn't wiped on reopen.
      try {
        const history = await chatApi.getHistory()
        if (!cancelled && history.length) {
          setMessages(history.map((m) => ({ role: m.role, content: m.content })))
        }
      } catch {
        /* offline / waking — start empty */
      }

      // 2) Daily wake report — once per day, appended after the held conversation.
      const today = new Date().toISOString().slice(0, 10)
      if (localStorage.getItem('orelius:reportDate') === today) return
      try {
        const r = await systemApi.getDailyReport()
        if (cancelled || !r?.report_markdown) return
        setMessages((prev) => [...prev, { role: 'assistant', content: r.report_markdown }])
        localStorage.setItem('orelius:reportDate', today)
      } catch {
        /* offline / waking — silent */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const autoGrow = () => {
    const el = taRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }

  const addFiles = async (files: FileList | null) => {
    if (!files) return
    for (const f of Array.from(files)) {
      if (f.size > MAX_ATTACH_BYTES) {
        alert(`${f.name} is too large (max 8MB).`)
        continue
      }
      try {
        const data = await fileToBase64(f)
        setPending((p) => [...p, { name: f.name, media_type: f.type || 'application/octet-stream', data }])
      } catch {
        /* skip unreadable file */
      }
    }
  }

  const send = async () => {
    const text = input.trim()
    if ((!text && pending.length === 0) || loading) return

    const attachments: ChatAttachment[] = pending.map((p) => ({
      name: p.name,
      media_type: p.media_type,
      data: p.data,
    }))
    const fileNames = pending.map((p) => p.name)

    setMessages((prev) => [...prev, { role: 'user', content: text, files: fileNames }])
    setInput('')
    setPending([])
    setLoading(true)
    if (taRef.current) taRef.current.style.height = 'auto'

    try {
      const res = await chatApi.sendMessage(userId, text || 'Please review the attached file(s).', 'web', attachments)
      setMessages((prev) => [...prev, { role: 'assistant', content: res.response }])
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'A momentary fault, Master. Please try that again.' },
      ])
    } finally {
      setLoading(false)
    }
  }

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="oreo-root">
      <Sparkles />
      {/* Header — centered wordmark only */}
      <header className="oreo-header">
        <h1 className="oreo-wordmark">O.R.E.L.I.U.S.</h1>
      </header>

      {/* Conversation */}
      <main className="oreo-conv">
        <div className="oreo-conv-inner">
          {messages.length === 0 && !loading && (
            <div className="oreo-welcome">
              <div className="oreo-logo oreo-logo-lg">O</div>
              <h2>Good day, Master.</h2>
              <p>I am ORELIUS. Speak, and I will answer with discipline and precision.</p>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`oreo-row ${m.role}`}>
              <div className={`oreo-bubble ${m.role}`}>
                <div className="oreo-role">{m.role === 'user' ? 'You' : 'ORELIUS'}</div>
                {m.content && (
                  <div className="oreo-text" dangerouslySetInnerHTML={renderMarkdown(m.content)} />
                )}
                {m.files && m.files.length > 0 && (
                  <div className="oreo-files">
                    {m.files.map((f, k) => (
                      <span key={k} className="oreo-chip">📎 {f}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="oreo-row assistant">
              <div className="oreo-bubble assistant">
                <div className="oreo-role">ORELIUS</div>
                <div className="oreo-dots"><span /><span /><span /></div>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </main>

      {/* Composer */}
      <footer className="oreo-composer">
        <div className="oreo-composer-inner">
          {pending.length > 0 && (
            <div className="oreo-pending">
              {pending.map((p, i) => (
                <span key={i} className="oreo-chip">
                  {p.media_type.startsWith('image/') ? '🖼️' : '📄'} {p.name}
                  <button onClick={() => setPending((x) => x.filter((_, j) => j !== i))} aria-label="Remove">×</button>
                </span>
              ))}
            </div>
          )}
          <div className="oreo-inputbar">
            <button className="oreo-attach" onClick={() => photoRef.current?.click()} title="Attach photo" aria-label="Attach photo">
              {/* image icon */}
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.6"/><path d="M21 15l-5-5L5 21"/></svg>
            </button>
            <button className="oreo-attach" onClick={() => fileRef.current?.click()} title="Attach file" aria-label="Attach file">
              {/* paperclip icon */}
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M21 8l-9.5 9.5a4 4 0 01-5.7-5.7L14 4a2.7 2.7 0 013.8 3.8L9.4 16.2a1.4 1.4 0 01-2-2L15 6.6"/></svg>
            </button>
            <textarea
              ref={taRef}
              value={input}
              onChange={(e) => { setInput(e.target.value); autoGrow() }}
              onKeyDown={onKey}
              placeholder="Message ORELIUS…"
              rows={1}
              disabled={loading}
            />
            <button className="oreo-send" onClick={send} disabled={loading || (!input.trim() && pending.length === 0)} aria-label="Send">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M3 11l18-8-8 18-2-7-8-3z"/></svg>
            </button>
          </div>
          <p className="oreo-hint">Enter to send · Shift+Enter for a new line</p>
        </div>
      </footer>

      <input ref={photoRef} type="file" accept="image/*" multiple hidden onChange={(e) => { addFiles(e.target.files); e.target.value = '' }} />
      <input ref={fileRef} type="file" multiple hidden onChange={(e) => { addFiles(e.target.files); e.target.value = '' }} />
    </div>
  )
}
