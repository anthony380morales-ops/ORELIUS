import { useState, useEffect, useRef } from 'react'
import { chatApi } from '../../services/api'
import type { Message } from '../../types'

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Generate or retrieve user ID (only once)
  const getUserId = () => {
    let storedId = localStorage.getItem('userId')

    // Fix corrupted user IDs (if it contains multiple "web-user-" prefixes)
    if (storedId && storedId.match(/web-user-.*web-user-/)) {
      console.warn('Corrupted user ID detected, generating new one')
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
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading) return

    const userMessage: Message = {
      role: 'user',
      content: inputValue,
    }

    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)

    try {
      const response = await chatApi.sendMessage(userId, inputValue, 'web')

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.response,
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('Chat error:', error)
      const errorMessage: Message = {
        role: 'assistant',
        content: 'An error occurred while processing your request. Please try again.',
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex flex-col h-full bg-navy-950">
      {/* Header */}
      <div className="border-b border-navy-800 px-6 py-4 bg-navy-900/50 backdrop-blur-sm relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-blue-900/20 via-transparent to-transparent pointer-events-none" />
        <div className="relative z-10 flex items-center gap-3">
          <span className="text-3xl animate-pulse">🤖</span>
          <div>
            <h2 className="text-xl font-semibold text-white">Chat with O.R.E.I.L.U.S.</h2>
            <p className="text-sm text-navy-300 mt-1">Your strategic business advisor</p>
          </div>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 scrollbar-thin">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="max-w-2xl">
              <div className="text-6xl mb-4 animate-float">🤖</div>
              <h3 className="text-2xl font-semibold text-white mb-3">
                Good day, Master.
              </h3>
              <p className="text-navy-300 mb-6">
                I am O.R.E.I.L.U.S., your strategic business advisor and systems architect.
              </p>
              <div className="bg-navy-900/50 backdrop-blur-sm rounded-lg p-6 text-left border border-navy-800 relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-blue-900/20 via-transparent to-transparent pointer-events-none" />
                <div className="relative z-10">
                  <div className="text-sm font-semibold text-blue-400 mb-3 flex items-center gap-2">
                    <span>⚡</span>
                    <span>I can assist you with:</span>
                  </div>
                  <ul className="space-y-2 text-sm text-navy-200">
                    <li className="flex items-start gap-2">
                      <span className="text-blue-400">•</span>
                      <span>Strategic business planning and expansion opportunities</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-400">•</span>
                      <span>Market intelligence and trend analysis</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-400">•</span>
                      <span>Systems optimization (LUCIUS, GREECE, ION Systems)</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-400">•</span>
                      <span>Cybersecurity strategy and threat assessment</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-blue-400">•</span>
                      <span>Blueprint Collective banking intelligence insights</span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-3xl rounded-lg px-4 py-3 relative overflow-hidden ${
                msg.role === 'user'
                  ? 'bg-gradient-to-r from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-500/30'
                  : 'bg-navy-900/50 backdrop-blur-sm text-navy-100 border border-navy-800'
              }`}
            >
              {msg.role === 'assistant' && (
                <div className="absolute inset-0 bg-gradient-to-br from-blue-900/10 via-transparent to-transparent pointer-events-none" />
              )}
              <div className="relative z-10">
                <div className="text-xs font-semibold mb-1 opacity-70">
                  {msg.role === 'user' ? 'You' : 'O.R.E.I.L.U.S.'}
                </div>
                <div className="message-content whitespace-pre-wrap">{msg.content}</div>
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-navy-900/50 backdrop-blur-sm rounded-lg px-4 py-3 max-w-3xl border border-navy-800 relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-900/10 via-transparent to-transparent pointer-events-none" />
              <div className="relative z-10">
                <div className="text-xs font-semibold mb-1 opacity-70 text-navy-300">O.R.E.I.L.U.S.</div>
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-navy-800 bg-navy-900/50 backdrop-blur-sm px-6 py-4 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-blue-900/10 via-transparent to-transparent pointer-events-none" />
        <div className="relative z-10">
          <div className="flex gap-3">
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Send a message to O.R.E.I.L.U.S..."
              className="flex-1 bg-navy-950 text-navy-100 rounded-lg px-4 py-3 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 border border-navy-800 placeholder-navy-400"
              rows={2}
              disabled={isLoading}
            />
            <button
              onClick={sendMessage}
              disabled={isLoading || !inputValue.trim()}
              className="px-6 py-3 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 disabled:from-navy-800 disabled:to-navy-800 disabled:cursor-not-allowed rounded-lg font-semibold transition-all shadow-lg shadow-blue-500/30 disabled:shadow-none"
            >
              Send
            </button>
          </div>
          <p className="text-xs text-navy-400 mt-2">
            Press Enter to send, Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  )
}
