"use client"

import { ChevronDown } from "lucide-react"
import { useEffect, useState } from "react"

interface ScrollIndicatorProps {
  show: boolean
}

export function ScrollIndicator({ show }: ScrollIndicatorProps) {
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    if (show) {
      // adds a small delay to make the arrow feel more natural
      const timer = setTimeout(() => setIsVisible(true), 1000)
      return () => clearTimeout(timer)
    } else {
      setIsVisible(false)
    }
  }, [show])

  const handleClick = () => {
    // finds the circuit pipeline section and scrolls to it
    const pipelineElement = document.querySelector("[data-pipeline-section]")
    if (pipelineElement) {
      pipelineElement.scrollIntoView({ behavior: "smooth" })
    }
  }

  if (!isVisible) return null

  return (
    <div className="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-50">
      <button
        onClick={handleClick}
        className="group bg-black text-white px-4 py-3 rounded-full shadow-lg hover:bg-gray-800 transition-all duration-300 flex items-center gap-2 animate-bounce"
      >
        <span className="text-sm font-medium">See your circuit pipeline</span>
        <ChevronDown className="h-4 w-4 group-hover:translate-y-0.5 transition-transform" />
      </button>
    </div>
  )
}
