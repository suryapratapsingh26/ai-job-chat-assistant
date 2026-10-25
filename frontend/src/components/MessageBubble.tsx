export interface ChatMessage {
  id: string
  role: 'assistant' | 'user'
  text: string
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  return (
    <article className={`message-row${isUser ? ' user-message' : ''}`}>
      {!isUser && <span className="assistant-avatar" aria-hidden="true">✳</span>}
      <div className="message-content">
        <div className="message-author">{isUser ? 'You' : 'JobFinder'}</div>
        <div className={`message-bubble ${isUser ? 'bubble-user' : 'bubble-assistant'}`}>
          {message.text}
        </div>
      </div>
    </article>
  )
}
