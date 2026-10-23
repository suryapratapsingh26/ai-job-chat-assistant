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
