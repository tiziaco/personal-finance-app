export interface HealthResponse {
  status: 'healthy' | 'degraded'
  version: string
  environment: 'development' | 'staging' | 'production' | 'test'
  components: {
    api: 'healthy'
    database: {
      status: 'healthy' | 'unhealthy'
      connection_pool: {
        size: number
        checked_in: number
        checked_out: number
        overflow: number
        total: number
      }
    }
    agents: {
      chatbot: {
        ready: boolean
        graph_compiled: boolean
      }
    }
  }
  timestamp: string
}
