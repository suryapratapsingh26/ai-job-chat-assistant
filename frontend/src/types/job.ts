export interface Job {
  job_id: string
  title: string
  company: string
  location: string
  experience: string
  skills: string[]
  description: string
  source_link: string
}

export interface JobPage {
  total: number
  offset: number
  limit: number
  jobs: Job[]
}
