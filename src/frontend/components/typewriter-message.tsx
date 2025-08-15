"use client"

import { useTypewriter } from "@/hooks/use-typewriter"

interface TypewriterMessageProps {
  content: string
  timestamp: Date
  speed?: number
}

export function TypewriterMessage({ content, timestamp, speed = 40 }: TypewriterMessageProps) {
  const { displayText, isComplete } = useTypewriter(content, speed)

  return (
    <div className="bg-muted rounded-lg px-4 py-2">
      <p className="text-sm">
        {displayText}
        {!isComplete && <span className="animate-pulse">|</span>}
      </p>
      {isComplete && <p className="text-xs opacity-70 mt-1">{timestamp.toLocaleTimeString()}</p>}
    </div>
  )
}
