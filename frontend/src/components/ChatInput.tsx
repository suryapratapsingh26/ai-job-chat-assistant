import { useState, type FormEvent } from 'react'

export function ChatInput({ onSend }: { onSend: (message: string) => void }) {
  const [value, setValue] = useState('')

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const message = value.trim()
    if (!message) return
    onSend(message)
    setValue('')
  }

  return (
    <form className="chat-composer" onSubmit={submit}>
      <label className="sr-only" htmlFor="chat-message">Message Pathfinder</label>
      <textarea
        id="chat-message"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Tell us what kind of role you’re looking for…"
        rows={1}
        maxLength={1000}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            event.currentTarget.form?.requestSubmit()
          }
        }}
      />
      <button className="send-button" type="submit" disabled={!value.trim()} aria-label="Send message">
        <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 10h13M10 4l6 6-6 6" /></svg>
      </button>
      <div className="composer-footnote">Enter to send · Shift + Enter for a new line</div>
    </form>
  )
}
