import { useEffect, useRef } from 'react'
import { MessageBubble, type ChatMessage } from './MessageBubble'

export function MessageList({ messages }: { messages: ChatMessage[] }) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [messages])

  return (
    <div className="message-list" aria-live="polite" aria-relevant="additions text">
      {messages.map((message) => <MessageBubble key={message.id} message={message} />)}
      <div ref={endRef} />
    </div>
  )
}
