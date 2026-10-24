import type { Job, JobPage } from '../types/job'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`The server returned ${response.status}. Please try again.`)
  }
  return response.json() as Promise<T>
}

export const jobService = {
  list: (offset = 0, limit = 24) =>
    getJson<JobPage>(`/api/jobs?offset=${offset}&limit=${limit}`),
}

export interface ResumeProfile {
  name: string | null
  email: string | null
  phone: string | null
  designation: string | null
  skills: string[]
  experience: string | null
  education: string[]
  projects: string[]
}

export interface MatchScoringDetails {
  skills: number | null
  title: number | null
  experience: number | null
  description: number | null
}

export interface JobRecommendation {
  job: Job
  match_score: number
  matched_skills: string[]
  match_reasons: string[]
  scoring_details: MatchScoringDetails
}

export interface JobMatchResponse {
  total_matches: number
  recommendations: JobRecommendation[]
}

export interface ChatFilters {
  skills: string[]
  location: string | null
  remote: boolean | null
  role: string | null
  experience_level: 'intern' | 'entry' | 'junior' | 'mid' | 'senior' | 'lead' | null
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatResponse {
  assistant_message: string
  intent: 'search_jobs' | 'refine_jobs' | 'explain_job' | 'show_jobs' | 'apply_job' | 'list_applications' | 'general' | 'error'
  jobs: Job[]
  recommendations: JobRecommendation[]
  applications: JobApplication[]
  active_filters: ChatFilters
  personalized: boolean
  error: string | null
}

export interface JobApplication {
  job_id: string
  applied_at: string
  status: 'applied'
  job: Job | null
}

export const chatService = {
  async send(
    message: string,
    profile: ResumeProfile | null,
    history: ChatTurn[],
    activeFilters: ChatFilters,
    currentJobIds: string[],
    selectedJobId?: string,
  ): Promise<ChatResponse> {
    let response: Response
    try {
      response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          profile,
          history: history.slice(-20),
          active_filters: activeFilters,
          current_job_ids: currentJobIds.slice(0, 1800),
          selected_job_id: selectedJobId,
        }),
      })
    } catch {
      throw new Error('Could not reach the conversational search service. Check that the API is running and try again.')
    }
    const payload = await response.json().catch(() => null) as
      | (ChatResponse & { detail?: unknown })
      | null
    if (!response.ok) {
      const messageText = typeof payload?.detail === 'string'
        ? payload.detail
        : typeof payload?.error === 'string'
          ? payload.error
          : `Conversational search failed (${response.status}). Please try again.`
      throw new Error(messageText)
    }
    if (!payload || typeof payload.assistant_message !== 'string') {
      throw new Error('The assistant returned an incomplete response. Please try again.')
    }
    return payload
  },
}

export const matchingService = {
  async recommend(profile: ResumeProfile, limit = 24): Promise<JobMatchResponse> {
    let response: Response
    try {
      response = await fetch(`${API_BASE_URL}/api/jobs/match?limit=${limit}`, {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile }),
      })
    } catch {
      throw new Error('Could not reach the job matching service. Check that the API is running and try again.')
    }
    const payload = await response.json().catch(() => null) as
      | (JobMatchResponse & { detail?: unknown })
      | null
    if (!response.ok) {
      const message = typeof payload?.detail === 'string'
        ? payload.detail
        : `Job matching failed (${response.status}). Check the profile and try again.`
      throw new Error(message)
    }
    if (!payload || !Array.isArray(payload.recommendations)) {
      throw new Error('The server returned an incomplete recommendation list. Please try again.')
    }
    return payload
  },
}

export const resumeService = {
  async parse(file: File): Promise<ResumeProfile> {
    const form = new FormData()
    form.append('file', file)
    let response: Response
    try {
      response = await fetch(`${API_BASE_URL}/api/resume/parse`, {
        method: 'POST',
        headers: { Accept: 'application/json' },
        body: form,
      })
    } catch {
      throw new Error('Could not reach the resume service. Check that the API is running and try again.')
    }
    const payload = await response.json().catch(() => null) as
      | { profile?: ResumeProfile; detail?: unknown }
      | null
    if (!response.ok) {
      const message = typeof payload?.detail === 'string'
        ? payload.detail
        : `Resume processing failed (${response.status}). Check the file and try again.`
      throw new Error(message)
    }
    if (!payload?.profile) {
      throw new Error('The server returned an incomplete profile. Please try uploading the resume again.')
    }
    return payload.profile
  },
}
