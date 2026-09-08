import { useState, useEffect } from 'react'
import Login from './components/Login'
import { tokenStore } from './services/api'
import ChatConsole from './components/Chat/ChatConsole'

/*
 * ORELIUS is a chatbot. The entire app is one responsive chat window — no
 * navigation, no tabs, no dashboards. Everything ORELIUS knows lives in its
 * memory; it reports status on request and greets with a daily briefing.
 */
function App() {
  const [authed, setAuthed] = useState(tokenStore.isAuthed)

  useEffect(() => {
    const onLogout = () => setAuthed(false)
    window.addEventListener('orelius:logout', onLogout)
    return () => window.removeEventListener('orelius:logout', onLogout)
  }, [])

  if (!authed) {
    return <Login onSuccess={() => setAuthed(true)} />
  }

  return <ChatConsole />
}

export default App
