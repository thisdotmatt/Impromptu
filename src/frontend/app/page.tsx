"use client"

import type React from "react"
import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Send, Zap, MessageCircle, Cpu, Factory } from "lucide-react"
import { TypewriterMessage } from "@/components/typewriter-message"
import { PipelineRunner } from "@/components/pipeline-runner"
import { ManufacturingCard } from "@/components/manufacturing-card"
import { SettingsDialog, type SettingsType } from "@/components/settings-dialog"
import { TutorialOverlay } from "@/components/tutorial-overlay"
import { ScrollIndicator } from "@/components/scroll-indicator"

type Message = {
  id: string
  content: string
  role: "user" | "assistant"
  timestamp: Date
}

type Page = "home" | "about" | "faq" | "tutorial"

export default function Home() {
  const [currentPage, setCurrentPage] = useState<Page>("home")
  const [showTutorial, setShowTutorial] = useState(true)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [selectedModel, setSelectedModel] = useState("gpt-4")
  const [isLoading, setIsLoading] = useState(false)
  const [settings, setSettings] = useState<SettingsType>({
    showTokenCost: false,
  })
  const [pipelineStages, setPipelineStages] = useState<any[]>([])

  useEffect(() => {
    // const hasSeenTutorial = localStorage.getItem("impromptu-tutorial-seen")
    // if (!hasSeenTutorial) {
    //   setShowTutorial(true)
    // }
  }, [])

  const handleCloseTutorial = () => {
    setShowTutorial(false)
    // localStorage.setItem("impromptu-tutorial-seen", "true")
  }

  const handleShowTutorial = () => {
    setShowTutorial(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault()
      if (!input.trim()) return

      const userMessage: Message = {
        id: Date.now().toString(),
        content: input,
        role: "user",
        timestamp: new Date(),
      }

      // Build the history we will send to the backend (include the new user message)
      const history = [...messages, userMessage].map((m) => ({
        role: m.role,
        content: m.content,
      }))

      setMessages((prev) => [...prev, userMessage])
      setInput("")
      setIsLoading(true)

      // Create a placeholder assistant message that we'll fill as chunks arrive
      const assistantId = (Date.now() + 1).toString()
      const placeholder: Message = {
        id: assistantId,
        content: "Thinking...", // show this instead of an empty bubble/caret
        role: "assistant",
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, placeholder])

      try {
        const controller = new AbortController()

        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: history,
            selectedModel,
          }),
          signal: controller.signal,
        })

        if (!res.ok || !res.body) {
          throw new Error(`Chat request failed with status ${res.status}`)
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder("utf-8")
        let buffer = ""

        const applyDelta = (delta: string) => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantId) return m
              const base = m.content === "Thinking..." ? "" : m.content // replace the first time
              return { ...m, content: base + delta }
            })
          )
        }

        // Parse SSE: lines separated by \n\n, extract the JSON from "data: ..."
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })

          let sepIndex: number
          while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
            const rawEvent = buffer.slice(0, sepIndex).trim()
            buffer = buffer.slice(sepIndex + 2)

            // For safety, handle multi-line SSE blocks; find the data line(s)
            const dataLines = rawEvent
              .split("\n")
              .filter((line) => line.startsWith("data:"))
              .map((line) => line.replace(/^data:\s*/, ""))

            for (const data of dataLines) {
              if (!data) continue
              let evt: any
              try {
                evt = JSON.parse(data)
              } catch {
                continue
              }

              switch (evt.type) {
                case "message_start":
                  // Optionally sync IDs; we keep local assistantId to update the correct bubble
                  break
                case "chunk":
                  applyDelta(evt.delta || "")
                  break
                case "message_end":
                  // Ensure final content is set (already accumulated)
                  setIsLoading(false)
                  break
                case "error":
                  applyDelta("\n\nSorry, I had trouble responding. Please try again.")
                  setIsLoading(false)
                  break
                case "complete":
                  // Stream finished
                  break
                default:
                  break
              }
            }
          }
        }
      } catch (err) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content:
                    m.content +
                    "\n\nSorry, I had trouble responding. Please try again.",
                }
              : m
          )
        )
        setIsLoading(false)
      }
    }

  const handlePipelineStagesUpdate = (stages: any[]) => {
    setPipelineStages(stages)
  }

  const isDesignComplete = () => {
    const designStage = pipelineStages.find((stage) => stage.id === "design")
    return designStage?.status === "success"
  }

  const renderHome = () => (
    <div className="flex flex-col h-full space-y-6">
      <div className="flex-1 flex flex-col gap-4">
        <Card className="flex-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5" />
              Circuit Design Assistant
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col h-full gap-4">
            <ScrollArea className="flex-1 h-96 pr-4">
              {messages.length === 0 ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  <p>Start a conversation about your circuit design needs...</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      {message.role === "user" ? (
                        <div className="max-w-[80%] rounded-lg px-4 py-2 bg-primary text-primary-foreground">
                          <p className="text-sm">{message.content}</p>
                          <p className="text-xs opacity-70 mt-1">{message.timestamp.toLocaleTimeString()}</p>
                        </div>
                      ) : (
                        <div className="max-w-[80%]">
                          {message.content && message.content !== "Thinking..." ? (
                            <TypewriterMessage content={message.content} timestamp={message.timestamp} speed={25} />
                          ) : (
                            <div className="bg-muted rounded-lg px-4 py-2">
                              <p className="text-sm">Thinking...</p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>

            <div className="space-y-3">
              <Select value={selectedModel} onValueChange={setSelectedModel}>
                <SelectTrigger>
                  <SelectValue placeholder="Select model" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gpt-4">GPT-4</SelectItem>
                  <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
                  <SelectItem value="claude-3">Claude 3</SelectItem>
                  <SelectItem value="llama-2">Llama 2</SelectItem>
                </SelectContent>
              </Select>

              <form onSubmit={handleSubmit} className="flex gap-2">
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about circuit design, components, analysis..."
                  disabled={isLoading}
                  className="flex-1"
                />
                <Button type="submit" disabled={isLoading || !input.trim()}>
                  <Send className="h-4 w-4" />
                </Button>
              </form>
            </div>
          </CardContent>
        </Card>
      </div>

      <div data-pipeline-section>
        <PipelineRunner
          messages={messages}
          selectedModel={selectedModel}
          settings={settings}
          onGenerateCircuit={() => {
            // Optional callback when circuit generation starts
            console.log("Circuit generation started with context:", messages)
          }}
          onStagesUpdate={handlePipelineStagesUpdate}
        />
      </div>

      <ManufacturingCard
        isSimulationComplete={isDesignComplete()}
        circuitData={null} // You can pass actual circuit data here when available
        settings={settings}
      />

      <ScrollIndicator show={messages.length > 0} />
    </div>
  )

  const renderAbout = () => (
    <Card>
      <CardHeader>
        <CardTitle>About Impromptu</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p>
          Impromptu is an end-to-end automatic circuit design chatbot that leverages advanced language models to assist
          engineers and designers in creating, analyzing, and optimizing electronic circuits.
        </p>
        <p>Our AI-powered assistant can help with:</p>
        <ul className="list-disc list-inside space-y-1 ml-4">
          <li>Circuit analysis and simulation</li>
          <li>Component selection and recommendations</li>
          <li>Design optimization suggestions</li>
          <li>Troubleshooting and debugging</li>
          <li>Best practices and design guidelines</li>
        </ul>
        <p>
          Simply select your preferred model and start asking questions about your circuit design challenges. Impromptu
          will provide detailed, technical responses to help you create better circuits faster.
        </p>
      </CardContent>
    </Card>
  )

  const renderFAQ = () => (
    <Card>
      <CardHeader>
        <CardTitle>Frequently Asked Questions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div>
          <h3 className="font-semibold mb-2">What types of circuits can Impromptu help with?</h3>
          <p className="text-sm text-muted-foreground">
            Impromptu can assist with analog, digital, mixed-signal, power electronics, RF circuits, and more. From
            simple filters to complex microprocessor systems.
          </p>
        </div>

        <div>
          <h3 className="font-semibold mb-2">Which AI models are available?</h3>
          <p className="text-sm text-muted-foreground">
            We support multiple models including GPT-4, GPT-3.5 Turbo, Claude 3, and Llama 2. Each model has different
            strengths for various types of circuit design tasks.
          </p>
        </div>

        <div>
          <h3 className="font-semibold mb-2">How accurate are the circuit recommendations?</h3>
          <p className="text-sm text-muted-foreground">
            Our AI provides well-informed suggestions based on established engineering principles, but always verify
            critical designs through simulation and testing before implementation.
          </p>
        </div>

        <div>
          <h3 className="font-semibold mb-2">Can I upload circuit schematics?</h3>
          <p className="text-sm text-muted-foreground">
            Currently, Impromptu works through text-based conversations. Describe your circuit or paste component lists,
            and our AI will provide relevant guidance and analysis.
          </p>
        </div>
      </CardContent>
    </Card>
  )

  const renderTutorial = () => (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Zap className="h-5 w-5" />
          How Impromptu Works
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-8">
        <div className="text-center">
          <h2 className="text-xl font-semibold mb-4">End-to-End Automatic Circuit Design</h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            From conversation to physical circuit board in three simple steps. Let AI handle the complexity while you
            focus on innovation.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {[
            {
              icon: MessageCircle,
              title: "Chat",
              description: "Discuss your business needs with an LLM",
              detail:
                "Start by describing your circuit requirements, specifications, and constraints through natural conversation. Our AI understands technical language and can help refine your ideas.",
            },
            {
              icon: Cpu,
              title: "Design",
              description: "Automatically generate a verified circuit design",
              detail:
                "Our AI agents create optimized circuit designs, run comprehensive simulations, and verify functionality automatically. Every design is checked for shorts, component compatibility, and performance.",
            },
            {
              icon: Factory,
              title: "Build",
              description: "Send your design to the pick-and-place machine",
              detail:
                "Seamlessly transfer your verified design to manufacturing with automated component placement data, assembly instructions, and quality verification.",
            },
          ].map((step, index) => {
            const Icon = step.icon
            return (
              <div key={index} className="text-center">
                <div className="relative mb-6">
                  <div className="w-16 h-16 mx-auto bg-primary/10 rounded-full flex items-center justify-center mb-4">
                    <Icon className="h-8 w-8 text-primary" />
                  </div>
                  <div className="absolute -top-2 -right-2 w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-xs font-semibold">
                    {index + 1}
                  </div>
                  {index < 2 && (
                    <div className="hidden md:block absolute top-8 left-full w-full h-0.5 bg-border -translate-x-4" />
                  )}
                </div>
                <h3 className="text-lg font-semibold mb-2">{step.title}</h3>
                <p className="text-sm text-muted-foreground mb-2">{step.description}</p>
                <p className="text-xs text-muted-foreground">{step.detail}</p>
              </div>
            )
          })}
        </div>

        <div className="bg-muted/50 rounded-lg p-6">
          <h3 className="font-semibold mb-2">Ready to get started?</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Navigate to the Home page to begin your first circuit design conversation, or explore the About and FAQ
            sections to learn more about Impromptu's capabilities.
          </p>
          <Button onClick={() => setCurrentPage("home")} className="w-full sm:w-auto">
            Start Designing
          </Button>
        </div>
      </CardContent>
    </Card>
  )

  return (
    <div className="min-h-screen bg-background">
      <TutorialOverlay isOpen={showTutorial} onClose={handleCloseTutorial} />

      {/* Navigation */}
      <nav className="border-b">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-2">
              <Zap className="h-6 w-6" />
              <span className="font-semibold text-lg">Impromptu</span>
            </div>
            <div className="flex items-center space-x-8">
              <div className="flex space-x-8">
                <button
                  onClick={() => setCurrentPage("home")}
                  className={`text-sm font-medium transition-colors hover:text-primary ${
                    currentPage === "home" ? "text-primary" : "text-muted-foreground"
                  }`}
                >
                  Home
                </button>
                <button
                  onClick={() => setCurrentPage("about")}
                  className={`text-sm font-medium transition-colors hover:text-primary ${
                    currentPage === "about" ? "text-primary" : "text-muted-foreground"
                  }`}
                >
                  About
                </button>
                <button
                  onClick={() => setCurrentPage("tutorial")}
                  className={`text-sm font-medium transition-colors hover:text-primary ${
                    currentPage === "tutorial" ? "text-primary" : "text-muted-foreground"
                  }`}
                >
                  Tutorial
                </button>
                <button
                  onClick={() => setCurrentPage("faq")}
                  className={`text-sm font-medium transition-colors hover:text-primary ${
                    currentPage === "faq" ? "text-primary" : "text-muted-foreground"
                  }`}
                >
                  FAQ
                </button>
              </div>
              <SettingsDialog settings={settings} onSettingsChange={setSettings} onShowTutorial={handleShowTutorial} />
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {currentPage === "home" && renderHome()}
        {currentPage === "about" && renderAbout()}
        {currentPage === "tutorial" && renderTutorial()}
        {currentPage === "faq" && renderFAQ()}
      </main>
    </div>
  )
}
