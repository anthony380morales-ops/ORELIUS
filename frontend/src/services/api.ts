import axios from 'axios'
import type { SystemStatus, AuditLog, SystemMetrics, Conversation, Message } from '../types'

const ACCESS_KEY = 'access_token'
const REFRESH_KEY = 'refresh_token'

export const tokenStore = {
  get access() { return localStorage.getItem(ACCESS_KEY) },
  get refresh() { return localStorage.getItem(REFRESH_KEY) },
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
  get isAuthed() { return !!localStorage.getItem(ACCESS_KEY) },
}

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// Attach the access token to every request
api.interceptors.request.use((config) => {
  const token = tokenStore.access
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, try one silent refresh, then replay the request; otherwise force re-login
let refreshing: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStore.refresh
  if (!refresh) return null
  try {
    const resp = await axios.post('/api/auth/refresh', { refresh_token: refresh })
    tokenStore.set(resp.data.access_token, resp.data.refresh_token)
    return resp.data.access_token
  } catch {
    tokenStore.clear()
    return null
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config || {}
    const isAuthCall = (original.url || '').includes('/auth/')
    if (error.response?.status === 401 && !original._retried && !isAuthCall) {
      original._retried = true
      refreshing = refreshing || refreshAccessToken()
      const newToken = await refreshing
      refreshing = null
      if (newToken) {
        original.headers = original.headers || {}
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)
      }
      // refresh failed — signal the app to show the login screen
      window.dispatchEvent(new CustomEvent('orelius:logout'))
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  login: async (userId: string, password: string) => {
    const resp = await axios.post('/api/auth/login', { user_id: userId, password })
    tokenStore.set(resp.data.access_token, resp.data.refresh_token)
    return resp.data
  },
  logout: () => {
    tokenStore.clear()
    window.dispatchEvent(new CustomEvent('orelius:logout'))
  },
  me: async () => {
    const resp = await api.get('/auth/me')
    return resp.data
  },
}

export interface ChatAttachment {
  name: string
  media_type: string
  data: string // base64, no data: prefix
}

export const chatApi = {
  // user_id now comes from the JWT on the server; kept in the signature for callers
  sendMessage: async (
    _userId: string,
    message: string,
    source: string = 'web',
    attachments?: ChatAttachment[],
  ) => {
    const response = await api.post(
      '/chat',
      { message, source, attachments: attachments && attachments.length ? attachments : undefined },
      { timeout: 90000 }, // vision/file analysis can take longer
    )
    return response.data
  },

  // Persisted conversation for the authenticated user (last N days, held across
  // app closes). Returns oldest→newest.
  getHistory: async (): Promise<{ role: 'user' | 'assistant'; content: string }[]> => {
    const response = await api.get('/chat/history')
    return (response.data || []).filter(
      (m: any) => m && (m.role === 'user' || m.role === 'assistant') && m.content,
    )
  },

  getConversations: async (userId: string): Promise<Conversation[]> => {
    const response = await api.get(`/conversations/${userId}`)
    return response.data
  },

  getMessages: async (conversationId: number): Promise<Message[]> => {
    const response = await api.get(`/conversations/${conversationId}/messages`)
    return response.data
  },
}

export const systemApi = {
  getDailyReport: async () => {
    const response = await api.get('/system/daily-report')
    return response.data as {
      report_markdown: string
      system_health: string
      automation: any
      memory: any
    }
  },

  getStatus: async (): Promise<SystemStatus> => {
    const response = await api.get('/system/status')
    return response.data
  },

  getMetrics: async (): Promise<SystemMetrics> => {
    const response = await api.get('/system/metrics')
    return response.data
  },

  getLogs: async (limit: number = 50): Promise<AuditLog[]> => {
    const response = await api.get('/system/logs', { params: { limit } })
    return response.data
  },

  getOptimization: async () => {
    const response = await api.get('/system/optimization')
    return response.data
  },
}

export const automationApi = {
  getStatus: async () => {
    const response = await api.get('/automation/status')
    return response.data
  },

  getJobs: async () => {
    const response = await api.get('/automation/jobs')
    return response.data
  },

  triggerJob: async (jobId: string) => {
    const response = await api.post(`/automation/trigger/${jobId}`)
    return response.data
  },
}

export default api
