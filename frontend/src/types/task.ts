export interface Clip {
  title: string
  description: string
  start_time: number
  end_time: number
  clip_file: string
}

export interface TaskItem {
  id: number
  task_id?: string | null
  filename: string
  status: string
  progress: number
  progress_msg: string
  result: Clip[] | null
  upload_file?: string | null
  log_file?: string | null
  created_at: string
  updated_at: string
}
