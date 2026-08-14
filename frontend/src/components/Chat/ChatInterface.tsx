import { useState, useEffect, useRef } from 'react'
import { chatApi } from '../../services/api'
import type { Message } from '../../types'

/*
 * ORELIUS Chat Console — design by Athena.
 * Premium navy + champagne-gold. Brain: Claude Haiku 4.5 (credit-optimized).
 * Companion: LUCIUS (shared memory).
 */

const QUICK_PROMPTS = [
  'Give me a validated business expansion opportunity for this quarter.',
  'Summarize what LUCIUS and I worked on recently.',
  'Draft a strategy plan to strengthen ION Systems lead validation.',
  'What banking insight should The Blueprint Collective publish next?',
]

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const getUserId = () => {
    let storedId = localStorage.getItem('userId')
    if (storedId && storedId.match(/web-user-.*web-user-/)) {
      storedId = null
      localStorage.removeItem('userId')
    }
    if (!storedId) {
      storedId = 'web-user-' + Math.random().toString(36).substring(7)
      localStorage.setItem('userId', storedId)
    }
    return storedId
  }

  const userId = getUserId()

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isLoading) return

    setMessages(prev => [...prev, { role: 'user', content: trimmed }])
    setInputValue('')
    setIsLoading(true)

    try {
      const response = await chatApi.sendMessage(userId, trimmed, 'web')
      setMessages(prev => [...prev, { role: 'assistant', content: response.response }])
    } catch (error) {
      console.error('Chat error:', error)
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: 'A momentary fault, Master. Please try that again.' },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(inputValue)
    }
  }

  return (
    <div className="flex flex-col h-full bg-athena-bg text-athena-text">
      {/* Header */}
      <header className="border-b border-athena-border px-8 py-5 bg-athena-surface/70 backdrop-blur-xl relative">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-athena-gold/60 to-transparent" />
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-athena-gold to-athena-gold-soft text-athena-bg font-black shadow-lg shadow-athena-gold/20">
              O
            </div>
            <div>
              <h2 className="text-lg font-semibold tracking-[0.18em] text-athena-text">
                O.R.E.L.I.U.S.
              </h2>
              <p className="text-xs text-athena-muted tracking-wide">
                On-the-go intelligence · voice of LUCIUS
              </p>
            </div>
          </div>
          <div className="hidden md:flex items-center gap-2">
            <Badge dot="gold">Haiku 4.5</Badge>
            <Badge dot="green">LUCIUS linked</Badge>
            <Badge dot="blue">Credit-optimized</Badge>
          </div>
        </div>
      </header>

      {/* Conversation */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-5 scrollbar-thin">
        {messages.length === 0 && !isLoading && (
          <Welcome onPick={send} />
        )}

        {messages.map((msg, idx) => (
          <Bubble key={idx} role={msg.role}>{msg.content}</Bubble>
        ))}

        {isLoading && (
          <div className="flex items-start gap-3">
            <Avatar role="assistant" />
            <div className="rounded-2xl rounded-tl-sm bg-athena-surface border border-athena-border px-4 py-3">
              <div className="flex gap-1.5">
                <span className="h-2 w-2 rounded-full bg-athena-gold/80 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="h-2 w-2 rounded-full bg-athena-gold/80 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="h-2 w-2 rounded-full bg-athena-gold/80 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Composer */}
      <div className="border-t border-athena-border bg-athena-surface/70 backdrop-blur-xl px-4 md:px-8 py-4">
        <div className="mx-auto max-w-4xl">
          <div className="flex items-end gap-3 rounded-2xl border border-athena-border bg-athena-surface-2 px-3 py-2 focus-within:border-athena-gold/60 transition-colors">
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Speak to ORELIUS…"
              className="flex-1 bg-transparent resize-none px-2 py-2 text-sm text-athena-text placeholder-athena-muted focus:outline-none"
              rows={1}
              disabled={isLoading}
            />
            <button
              onClick={() => send(inputValue)}
              disabled={isLoading || !inputValue.trim()}
              className="shrink-0 rounded-xl px-5 py-2.5 text-sm font-semibold text-athena-bg bg-gradient-to-br from-athena-gold to-athena-gold-soft shadow-lg shadow-athena-gold/20 transition-all hover:brightness-110 disabled:opacity-40 disabled:shadow-none"
            >
              Send
            </button>
          </div>
          <p className="mt-2 text-center text-[11px] text-athena-muted">
            Enter to send · Shift+Enter for a new line · responses run on Claude Haiku 4.5 with credit optimization
          </p>
        </div>
      </div>
    </div>
  )
}

function Welcome({ onPick }: { onPick: (t: string) => void }) {
  return (
    <div className="mx-auto max-w-3xl pt-6">
      <div className="text-center mb-8">
        <div className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-athena-gold to-athena-gold-soft text-athena-bg text-2xl font-black shadow-xl shadow-athena-gold/20 animate-float">
          O
        </div>
        <h3 className="text-2xl font-semibold text-athena-text">Good day, Master.</h3>
        <p className="mt-2 text-sm text-athena-muted">
          I am ORELIUS — your strategic advisor on the go, sharing memory with LUCIUS.
          Ask, and I will answer with discipline and precision.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {QUICK_PROMPTS.map((p) => (
          <button
            key={p}
            onClick={() => onPick(p)}
            className="group text-left rounded-2xl border border-athena-border bg-athena-surface hover:bg-athena-surface-2 hover:border-athena-gold/40 px-4 py-4 transition-all"
          >
            <span className="text-sm text-athena-text/90 group-hover:text-athena-text">{p}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

function Bubble({ role, children }: { role: string; children: React.ReactNode }) {
  const isUser = role === 'user'
  return (
    <div className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <Avatar role={role} />
      <div
        className={`max-w-[85%] md:max-w-2xl rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words ${
          isUser
            ? 'rounded-tr-sm bg-gradient-to-br from-navy-700 to-navy-900 text-white border border-navy-600/40'
            : 'rounded-tl-sm bg-athena-surface text-athena-text border border-athena-border'
        }`}
      >
        <div className={`mb-1 text-[10px] font-semibold uppercase tracking-wider ${isUser ? 'text-white/60' : 'text-athena-gold/80'}`}>
          {isUser ? 'You' : 'ORELIUS'}
        </div>
        {children}
      </div>
    </div>
  )
}

function Avatar({ role }: { role: string }) {
  if (role === 'user') {
    return (
      <div className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-navy-700 text-xs font-bold text-white">
        You
      </div>
    )
  }
  return (
    <div className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-athena-gold to-athena-gold-soft text-xs font-black text-athena-bg">
      O
    </div>
  )
}

function Badge({ children, dot }: { children: React.ReactNode; dot: 'gold' | 'green' | 'blue' }) {
  const color = dot === 'gold' ? 'bg-athena-gold' : dot === 'green' ? 'bg-emerald-400' : 'bg-sky-400'
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-athena-border bg-athena-surface-2 px-3 py-1 text-[11px] font-medium text-athena-muted">
      <span className={`h-1.5 w-1.5 rounded-full ${color} animate-pulse`} />
      {children}
    </span>
  )
}
