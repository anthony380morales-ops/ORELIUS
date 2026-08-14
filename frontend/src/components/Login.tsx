import { useState } from 'react'
import { authApi } from '../services/api'

export default function Login({ onSuccess }: { onSuccess: () => void }) {
  const [userId, setUserId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!userId.trim() || !password) return
    setError('')
    setLoading(true)
    try {
      await authApi.login(userId.trim(), password)
      onSuccess()
    } catch (err: any) {
      const status = err?.response?.status
      setError(
        status === 401 ? 'Incorrect password.' :
        status === 403 ? 'This user ID is not authorized.' :
        'Unable to sign in. Check your connection and try again.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen grid place-items-center bg-rich-navy text-white px-6">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-xl p-7 shadow-2xl"
      >
        <div className="mb-6 text-center">
          <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-amber-300 to-yellow-500 text-rich-navy text-xl font-black">
            O
          </div>
          <h1 className="text-xl font-semibold tracking-[0.18em]">O.R.E.L.I.U.S.</h1>
          <p className="mt-1 text-xs text-white/50">Master access only</p>
        </div>

        <label className="block text-xs font-medium text-white/60 mb-1">User ID</label>
        <input
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          autoComplete="username"
          className="w-full mb-4 rounded-xl bg-black/30 border border-white/10 px-3 py-2.5 text-sm focus:outline-none focus:border-amber-300/60"
          placeholder="Your authorized ID"
        />

        <label className="block text-xs font-medium text-white/60 mb-1">Master password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          className="w-full mb-4 rounded-xl bg-black/30 border border-white/10 px-3 py-2.5 text-sm focus:outline-none focus:border-amber-300/60"
          placeholder="••••••••"
        />

        {error && <p className="mb-4 text-sm text-red-300">{error}</p>}

        <button
          type="submit"
          disabled={loading || !userId.trim() || !password}
          className="w-full rounded-xl py-2.5 text-sm font-semibold text-rich-navy bg-gradient-to-br from-amber-300 to-yellow-500 disabled:opacity-40 transition"
        >
          {loading ? 'Signing in…' : 'Enter'}
        </button>
      </form>
    </div>
  )
}
