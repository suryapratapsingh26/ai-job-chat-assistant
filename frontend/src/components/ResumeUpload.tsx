import { useRef, useState, type ChangeEvent, type DragEvent } from 'react'

const ACCEPTED_TYPES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])

function supported(file: File) {
  const extensionIsValid = /\.(pdf|docx)$/i.test(file.name)
  const mimeIsValid = !file.type || file.type === 'application/octet-stream' || ACCEPTED_TYPES.has(file.type)
  return extensionIsValid && mimeIsValid
}

export function ResumeUpload() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [filename, setFilename] = useState('')
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  function selectFile(file?: File) {
    if (!file) return
    setError('')
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
  }

  function onChange(event: ChangeEvent<HTMLInputElement>) {
    selectFile(event.target.files?.[0])
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setDragging(false)
    selectFile(event.dataTransfer.files[0])
  }

  return (
    <section className="resume-card" aria-labelledby="resume-heading">
      <div className="resume-intro">
        <div className="section-eyebrow">YOUR PROFILE</div>
        <h2 id="resume-heading">Start with your resume</h2>
        <p className="resume-copy">Add a PDF or DOCX to set up your job search.</p>
      </div>
      <label
        className={`resume-dropzone${dragging ? ' is-dragging' : ''}`}
        htmlFor="resume-file"
        onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <span className="upload-icon" aria-hidden="true">↑</span>
        <span className="dropzone-label">{filename || 'Choose a file or drop it here'}</span>
        <span className="dropzone-hint">PDF or DOCX · max 10 MB</span>
        <input
          ref={inputRef}
          id="resume-file"
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={onChange}
          aria-describedby={error ? 'resume-error resume-note' : 'resume-note'}
        />
      </label>
      {error && <p className="field-error" id="resume-error" role="alert">{error}</p>}
      <p className="privacy-note" id="resume-note" aria-live="polite">
        {filename ? 'Selected in this browser only. Resume upload is not connected yet.' : 'Your file stays on this device. Upload is not connected yet.'}
      </p>
    </section>
  )
}
