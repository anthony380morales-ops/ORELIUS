import axios from 'axios'
import type { SystemStatus, AuditLog, SystemMetrics, Conversation, Message } from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export const chatApi = {
  sendMessage: async (userId: string, message: string, source: string = 'web') => {
    const response = await api.post('/chat', {
      user_id: userId,
      message,
      source,
    })
    return response.data
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

export const manusApi = {
  getDashboardMetrics: async () => {
    const response = await api.get('/manus/dashboard/metrics')
    return response.data
  },

  getTasks: async (status?: string, taskType?: string, limit: number = 50) => {
    const response = await api.get('/manus/tasks', {
      params: { status, task_type: taskType, limit }
    })
    return response.data
  },

  getTask: async (taskId: number) => {
    const response = await api.get(`/manus/tasks/${taskId}`)
    return response.data
  },

  createTask: async (taskType: string, customInstructions?: string, context?: any) => {
    const response = await api.post('/manus/tasks', {
      task_type: taskType,
      custom_instructions: customInstructions,
      context
    })
    return response.data
  },

  retryTask: async (taskId: number) => {
    const response = await api.post(`/manus/tasks/${taskId}/retry`)
    return response.data
  },

  getScheduledJobs: async () => {
    const response = await api.get('/manus/scheduler/jobs')
    return response.data
  },

  getHealthCheck: async () => {
    const response = await api.get('/manus/health')
    return response.data
  },
}

export default api
