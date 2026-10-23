import { useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { resumeService, type ResumeProfile } from '../services/api'

const ACCEPTED_TYPES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])

function supported(file: File) {
  const extensionIsValid = /\.(pdf|docx)$/i.test(file.name)
  const mimeIsValid = !file.type || file.type === 'application/octet-stream' || ACCEPTED_TYPES.has(file.type)
  return extensionIsValid && mimeIsValid
}

export function ResumeUpload({ onProfileParsed }: { onProfileParsed: (profile: ResumeProfile | null) => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [filename, setFilename] = useState('')
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [profile, setProfile] = useState<ResumeProfile | null>(null)

  async function selectFile(file?: File) {
    if (!file) return
    setError('')
    setProfile(null)
    onProfileParsed(null)
    if (!supported(file)) {
      setFilename('')
      setError('Choose a PDF or DOCX file to continue.')
      if (inputRef.current) inputRef.current.value = ''
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setFilename('')
      setError('This file is larger than 10 MB. Choose a smaller resume.')
      if (inputRef.current) inputRef.current.value = ''
      return
    }
    setFilename(file.name)
    setUploading(true)
    try {
      const parsedProfile = await resumeService.parse(file)
      setProfile(parsedProfile)
      onProfileParsed(parsedProfile)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not process this resume. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  function onChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.currentTarget.value = ''
    void selectFile(file)
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setDragging(false)
    if (!uploading) void selectFile(event.dataTransfer.files[0])
  }

  return (
    <section className="resume-card" aria-labelledby="resume-heading">
      <div className="resume-intro">
        <div className="section-eyebrow">YOUR PROFILE</div>
        <h2 id="resume-heading">Start with your resume</h2>
        <p className="resume-copy">Add a PDF or DOCX to set up your job search.</p>
      </div>
      <label
        className={`resume-dropzone${dragging ? ' is-dragging' : ''}${uploading ? ' is-uploading' : ''}`}
        htmlFor="resume-file"
        aria-disabled={uploading}
        onDragOver={(event) => { event.preventDefault(); if (!uploading) setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <span className="upload-icon" aria-hidden="true">↑</span>
        <span className="dropzone-label">{uploading ? 'Uploading and processing…' : filename || 'Choose a file or drop it here'}</span>
        <span className="dropzone-hint">PDF or DOCX · max 10 MB</span>
        <input
          ref={inputRef}
          id="resume-file"
          type="file"
          disabled={uploading}
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={onChange}
          aria-describedby={error ? 'resume-error resume-note' : 'resume-note'}
        />
      </label>
      {error && <p className="field-error" id="resume-error" role="alert">{error}</p>}
      <p className="privacy-note" id="resume-note" aria-live="polite">
        {uploading ? 'Extracting text and preparing your profile. Your file is not stored.' : error ? 'No profile was created. Your file is not stored.' : profile ? 'Resume processed successfully. Your file is not stored.' : 'Your resume is processed in memory and is not stored.'}
      </p>
      {profile && <ParsedProfile profile={profile} />}
    </section>
  )
}

function ParsedProfile({ profile }: { profile: ResumeProfile }) {
  const hasDetails = Boolean(
    profile.name || profile.email || profile.phone || profile.designation || profile.skills.length ||
    profile.experience || profile.education.length || profile.projects.length,
  )

  return (
    <div className="resume-profile" aria-labelledby="parsed-profile-heading">
      <div className="profile-heading">
        <div>
          <div className="section-eyebrow">RESUME DETAILS</div>
          <h3 id="parsed-profile-heading">{profile.name || 'Parsed profile'}</h3>
          {profile.designation && <p className="profile-designation">{profile.designation}</p>}
        </div>
        <span className="profile-success" aria-label="Resume parsed successfully">✓</span>
      </div>
      {!hasDetails && <p className="profile-empty">Text was extracted, but no profile details could be identified.</p>}
      {(profile.email || profile.phone) && (
        <div className="profile-contact">
          {profile.email && <a href={`mailto:${profile.email}`}>{profile.email}</a>}
          {profile.phone && <a href={`tel:${profile.phone.replace(/[^+\d]/g, '')}`}>{profile.phone}</a>}
        </div>
      )}
      {profile.skills.length > 0 && (
        <section className="profile-section">
          <h4>Skills</h4>
          <ul className="profile-skills">{profile.skills.map((skill) => <li key={skill}>{skill}</li>)}</ul>
        </section>
      )}
      {profile.experience && <ProfileText title="Experience" text={profile.experience} />}
      {profile.education.length > 0 && <ProfileList title="Education" items={profile.education} />}
      {profile.projects.length > 0 && <ProfileList title="Projects" items={profile.projects} />}
    </div>
  )
}

function ProfileText({ title, text }: { title: string; text: string }) {
  return <section className="profile-section"><h4>{title}</h4><p className="profile-body">{text}</p></section>
}

function ProfileList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="profile-section">
      <h4>{title}</h4>
      <ul className="profile-items">{items.map((item, index) => <li key={`${title}-${index}`}>{item}</li>)}</ul>
    </section>
  )
}
