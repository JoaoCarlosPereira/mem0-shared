export type Category = "personal" | "work" | "health" | "finance" | "travel" | "education" | "preferences" | "relationships"
export type Client = "chrome" | "chatgpt" | "cursor" | "windsurf" | "terminal" | "api"

export interface Memory {
  id: string
  memory: string
  metadata: any
  client: Client
  categories: Category[]
  created_at: number
  app_name: string
  state: "active" | "paused" | "archived" | "deleted"
  // Grupo (equipe) do autor da memória (task_09). Ausente/null => sem grupo resolvível.
  group?: string | null
  created_by_hostname?: string | null
  created_by_client?: string | null
  created_by_display_name?: string | null
  created_by_avatar_url?: string | null
}