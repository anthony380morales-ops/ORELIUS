// Type definitions for O.R.E.I.L.U.S. frontend

export interface Message {
  id?: number
  role: 'user' | 'assistant' | 'system'
  content: string
  token_count?: number
  created_at?: string
}

export interface Conversation {
  id: number
  title: string
  source: 'web' | 'telegram' | 'api'
  created_at: string
  updated_at: string
}

export interface SystemStatus {
  status: string
  components: {
    claude_api: string
    security_layer: string
    memory_manager: string
  }
  database: {
    conversations: number
    messages: number
    audit_logs: number
  }
  resources: {
    cpu_percent: number
    memory_percent: number
    memory_available_gb: number
    disk_percent: number
    disk_free_gb: number
  }
  timestamp: string
}

export interface AuditLog {
  id: number
  event_type: string
  severity: 'info' | 'warning' | 'error' | 'critical'
  user_id: string | null
  description: string
  metadata: any
  created_at: string
}

export interface SystemMetrics {
  messages: {
    total: number
    total_tokens: number
    last_24h: number
  }
  security: {
    total_audit_logs: number
    security_alerts: number
  }
  timestamp: string
}
