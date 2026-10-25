import { useEffect, useState } from 'react'
import { matchingService } from '../services/api'
import type { ChatResponse, JobMatchResponse, JobRecommendation, ResumeProfile } from '../services/api'
import type { Job } from '../types/job'
import { LoadingIndicator } from './LoadingIndicator'

function JobCard({ job, recommendation, position, applicationStatus, onApplyJob }: {
  job: Job
  recommendation?: JobRecommendation
  position: number
  applicationStatus?: { status: string; applied_at: string }
  onApplyJob: (jobId: string) => void
}) {
  const summary = job.description.length > 220 ? `${job.description.slice(0, 220).trimEnd()}…` : job.description
  return (
    <article className="job-card">
      <div className="job-card-topline">
        <div className="company-monogram" aria-hidden="true">{job.company.slice(0, 1).toUpperCase()}</div>
        <span className="job-position" aria-label={`Job ${position}`}>Job {position}</span>
        {recommendation && <span className="match-score">{recommendation.match_score}% match</span>}
        <a className="source-link" href={job.source_link} target="_blank" rel="noreferrer" aria-label={`View ${job.title} at source`}>↗</a>
      </div>
      <h3>{job.title}</h3>
      <p className="job-company">{job.company}</p>
      <div className="job-meta">
        <span>⌖ {job.location}</span>
        {job.experience && <span>◷ {job.experience}</span>}
      </div>
      {summary && <p className="job-description">{summary}</p>}
      {applicationStatus && <p className="job-application-status">Application {applicationStatus.status} · {new Date(applicationStatus.applied_at).toLocaleDateString()}</p>}
      <button type="button" className="track-application-button" onClick={() => onApplyJob(job.job_id)}>Track application</button>
      {job.skills.length > 0 && (
        <ul className="skill-list" aria-label="Skills">
          {job.skills.slice(0, 4).map((skill) => <li key={skill}>{skill}</li>)}
          {job.skills.length > 4 && <li>+{job.skills.length - 4}</li>}
        </ul>
      )}
      {recommendation && recommendation.matched_skills.length > 0 && (
        <ul className="matched-skills" aria-label="Matched skills">
          {recommendation.matched_skills.slice(0, 5).map((skill) => <li key={skill}>{skill}</li>)}
        </ul>
      )}
      {recommendation && recommendation.match_reasons.length > 0 && (
        <ul className="match-reasons" aria-label="Why this job matches">
          {recommendation.match_reasons.map((reason) => <li key={reason}>{reason}</li>)}
        </ul>
      )}
      <a className="job-apply-link" href={job.source_link} target="_blank" rel="noreferrer">View listing <span aria-hidden="true">→</span></a>
    </article>
  )
}

export function JobResults({ profile, chatResponse, onVisibleJobs, onApplyJob }: {
  profile: ResumeProfile | null
  chatResponse: ChatResponse | null
  onVisibleJobs: (jobIds: string[]) => void
  onApplyJob: (jobId: string) => void
}) {
  const [recommendations, setRecommendations] = useState<JobMatchResponse | null>(null)
  const [matching, setMatching] = useState(false)
  const [matchError, setMatchError] = useState('')
  const [showMatches, setShowMatches] = useState(false)
  const [showChatResults, setShowChatResults] = useState(false)
  const [resultsResponse, setResultsResponse] = useState<ChatResponse | null>(null)

  useEffect(() => {
    if (chatResponse && chatResponse.intent !== 'apply_job') setResultsResponse(chatResponse)
  }, [chatResponse])

  const hasChatResults = Boolean(resultsResponse && ['search_jobs', 'refine_jobs', 'explain_job', 'show_jobs', 'list_applications'].includes(resultsResponse.intent))
  const showingChatResults = showChatResults && hasChatResults

  useEffect(() => {
    setRecommendations(null)
    setMatchError('')
    setShowMatches(false)
    setShowChatResults(false)
    if (profile) void findMatches()
    else onVisibleJobs([])
  }, [profile])

  useEffect(() => {
    if (hasChatResults) {
      setShowChatResults(true)
      setShowMatches(false)
    }
  }, [resultsResponse, hasChatResults])

  useEffect(() => {
    if (showingChatResults && resultsResponse) {
      onVisibleJobs(resultsResponse.jobs.map((job) => job.job_id))
    } else if (showMatches) {
      onVisibleJobs(matching || !recommendations
        ? []
        : recommendations.recommendations.map((item) => item.job.job_id))
    } else {
      onVisibleJobs([])
    }
  }, [showingChatResults, resultsResponse, showMatches, matching, recommendations, onVisibleJobs])

  async function findMatches() {
    if (!profile) return
    setMatching(true)
    setMatchError('')
    setShowMatches(true)
    setShowChatResults(false)
    try {
      const result = await matchingService.recommend(profile)
      setRecommendations(result)
    } catch (reason) {
      setMatchError(reason instanceof Error ? reason.message : 'Could not find matching jobs.')
    } finally {
      setMatching(false)
    }
  }

  return (
    <aside className="results-panel" aria-labelledby="jobs-heading">
      <div className="results-heading">
        <div>
          <div className="section-eyebrow">
            {showingChatResults
              ? resultsResponse?.intent === 'list_applications'
                ? 'APPLICATION TRACKING'
                : resultsResponse?.personalized ? 'RESUME MATCHES' : 'GENERAL SEARCH'
              : profile ? 'PERSONALIZED FROM YOUR PROFILE' : 'YOUR PROFILE'}
          </div>
          <h2 id="jobs-heading">{showingChatResults
            ? resultsResponse?.intent === 'list_applications' ? 'Applied jobs' : 'Chat results'
            : 'Recommended jobs'}</h2>
        </div>
        {showingChatResults && <span className="results-count">{resultsResponse?.intent === 'list_applications' ? resultsResponse.applications.length : resultsResponse?.jobs.length ?? 0} {resultsResponse?.intent === 'list_applications' ? 'applications' : 'jobs'}</span>}
        {showMatches && !matching && recommendations && <span className="results-count">{recommendations.total_matches.toLocaleString()} matches</span>}
        {showingChatResults && <button type="button" className="text-button" onClick={() => { setShowMatches(Boolean(profile)); setShowChatResults(false) }}>Recommendations</button>}
      </div>
      <p className="results-intro">
        {showingChatResults
          ? resultsResponse?.intent === 'list_applications' ? 'Your saved applications and their current statuses.'
            : resultsResponse?.personalized ? 'Ranked resume matches refined by your conversation.' : 'General listings filtered from the existing job dataset. No resume match score is applied.'
          : 'Upload a resume to see job recommendations based on your profile.'}
      </p>
      {showingChatResults && resultsResponse && resultsResponse.intent !== 'list_applications' && <ActiveFilters filters={resultsResponse.active_filters} />}
      <div className="results-scroll" aria-label="Job listings">
        {showMatches && matching && <LoadingIndicator label="Finding jobs that fit your profile"><div className="match-loading-space" /></LoadingIndicator>}
        {showMatches && !matching && matchError && (
          <div className="results-message error-state" role="alert">
            <span className="state-icon">!</span>
            <h3>Recommendations aren’t available</h3>
            <p>{matchError}</p>
            <button type="button" className="text-button" onClick={() => void findMatches()}>Try again <span aria-hidden="true">↻</span></button>
          </div>
        )}
        {showMatches && !matching && !matchError && recommendations?.recommendations.length === 0 && (
          <div className="results-message">
            <span className="state-icon">⌕</span>
            <h3>No matching jobs found</h3>
            <p>Try a resume with more role or skill details to find relevant listings.</p>
          </div>
        )}
        {showMatches && !matching && !matchError && recommendations && recommendations.recommendations.length > 0 && (
          <div className="job-grid">
            {recommendations.recommendations.map((recommendation, index) => (
              <JobCard key={recommendation.job.job_id} job={recommendation.job} recommendation={recommendation} position={index + 1} onApplyJob={onApplyJob} />
            ))}
          </div>
        )}
        {showingChatResults && resultsResponse?.jobs.length === 0 && (
          <div className="results-message">
            <span className="state-icon">⌕</span>
            <h3>{resultsResponse.intent === 'list_applications' ? 'No applications yet' : 'No jobs found'}</h3>
            <p>{resultsResponse.assistant_message}</p>
          </div>
        )}
        {showingChatResults && resultsResponse && resultsResponse.recommendations.length > 0 && (
          <div className="job-grid">
            {resultsResponse.recommendations.map((recommendation, index) => (
              <JobCard key={recommendation.job.job_id} job={recommendation.job} recommendation={recommendation} position={index + 1} applicationStatus={resultsResponse.applications.find((item) => item.job_id === recommendation.job.job_id)} onApplyJob={onApplyJob} />
            ))}
          </div>
        )}
        {showingChatResults && resultsResponse && !resultsResponse.personalized && resultsResponse.jobs.length > 0 && (
          <div className="job-grid">
            {resultsResponse.jobs.map((job, index) => <JobCard key={job.job_id} job={job} position={index + 1} applicationStatus={resultsResponse.applications.find((item) => item.job_id === job.job_id)} onApplyJob={onApplyJob} />)}
          </div>
        )}
      </div>
    </aside>
  )
}

function ActiveFilters({ filters }: { filters: ChatResponse['active_filters'] }) {
  const values = [
    ...filters.skills,
    filters.location,
    filters.remote === true ? 'Remote' : filters.remote === false ? 'Onsite' : null,
    filters.role,
    filters.experience_level ? `${filters.experience_level} level` : null,
  ].filter((value): value is string => Boolean(value))
  if (!values.length) return null
  return <ul className="result-filter-list" aria-label="Active search filters">{values.map((value) => <li key={value}>{value}</li>)}</ul>
}
