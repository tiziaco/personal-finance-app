export type ProjectStatus = "active" | "completed" | "archived"

export interface Project {
  id: string
  name: string
  code: string
  clientId: string
  status: ProjectStatus
  createdAt: string
  updatedAt: string
}
