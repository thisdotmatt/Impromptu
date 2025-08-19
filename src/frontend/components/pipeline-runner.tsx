"use client"

import type React from "react"
import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { RotateCcw, Zap, CheckCircle, Clock, AlertCircle, Play, DollarSign } from "lucide-react"

type StageStatus = "pending" | "running" | "success" | "error" | "completed"

type SubStage = {
  id: string
  name: string
  status: StageStatus
}

type TokenCost = {
  inputTokens: number
  outputTokens: number
  totalTokens: number
  estimatedCost: number
}

type PipelineStageType = {
  id: string
  name: string
  status: StageStatus
  result?: Record<string, any>
  subStages?: SubStage[]
  tokenCost?: TokenCost
  startTime?: Date
  endTime?: Date
  duration?: number // in milliseconds
}

interface PipelineRunnerProps {
  messages: { id: string; content: string; role: "user" | "assistant"; timestamp: Date }[]
  selectedModel: string
  settings: { showTokenCost: boolean }
  onGenerateCircuit?: () => void
  onStagesUpdate?: (stages: PipelineStageType[]) => void
}

export function PipelineRunner({
  messages,
  selectedModel,
  settings,
  onGenerateCircuit,
  onStagesUpdate,
}: PipelineRunnerProps) {
  const [stages, setStages] = useState<PipelineStageType[]>([
    { id: "spec_generation", name: "Specification Generation", status: "pending" },
    {
      id: "netlist_generation",
      name: "Circuit Netlist Pipeline",
      status: "pending",
      subStages: [
        { id: "generate", name: "Generate netlist", status: "pending" },
        { id: "simulate", name: "Run simulation", status: "pending" },
        { id: "verify", name: "Verify results", status: "pending" },
      ],
    },
    {
      id: "circuit_to_printer",
      name: "Circuit-to-Printer",
      status: "pending",
      subStages: [
        { id: "circuit_to_printer", name: "Circuit-to-Printer", status: "pending" },
      ],
    },
  ])

  const [isRunning, setIsRunning] = useState(false)
  const [selectedStageId, setSelectedStageId] = useState<string>("spec_generation")
  const [pipelineStartTime, setPipelineStartTime] = useState<Date | null>(null)

  // NEW: capture start times synchronously to beat React's batching
  const stageStartRef = useRef<Record<string, number>>({})

  useEffect(() => {
    onStagesUpdate?.(stages)
  }, [stages, onStagesUpdate])

  const updateStage = (stageId: string, updates: Partial<PipelineStageType>) => {
    setStages((prev) => prev.map((stage) => (stage.id === stageId ? { ...stage, ...updates } : stage)))
  }

  const updateSubStage = (stageId: string, subStageId: string, status: PipelineStageType["status"]) => {
    setStages((prev) =>
      prev.map((stage) =>
        stage.id === stageId
          ? {
              ...stage,
              subStages: stage.subStages?.map((sub) => (sub.id === subStageId ? { ...sub, status } : sub)),
            }
          : stage,
      ),
    )
  }

  const getConversationContext = () => {
    const userMessages = messages.filter((msg) => msg.role === "user")
    if (userMessages.length === 0) return "No specific requirements provided"
    return userMessages.map((msg) => msg.content).join("; ")
  }

  const getVisibleStages = () => stages

  const getProgressPercentage = () => {
    const completedStages = stages.filter((stage) => stage.status === "success").length
    return (completedStages / stages.length) * 100
  }

  const getStageIcon = (status: StageStatus) => {
    switch (status) {
      case "success":
        return <CheckCircle className="h-4 w-4 text-green-600" />
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-600" />
      case "running":
        return <Play className="h-4 w-4 text-blue-600 animate-pulse" />
      case "error":
        return <AlertCircle className="h-4 w-4 text-red-600" />
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />
    }
  }

  const getStatusBadge = (status: StageStatus) => {
    switch (status) {
      case "success":
        return (
          <Badge variant="default" className="bg-green-100 text-green-800">
            Complete
          </Badge>
        )
      case "completed":
        return (
          <Badge variant="default" className="bg-green-100 text-green-800">
            Complete
          </Badge>
        )
      case "running":
        return (
          <Badge variant="default" className="bg-blue-100 text-blue-800">
            Running
          </Badge>
        )
      case "error":
        return <Badge variant="destructive">Error</Badge>
      default:
        return <Badge variant="secondary">Pending</Badge>
    }
  }

  const getTotalCost = () =>
    stages.filter((stage) => stage.tokenCost).reduce((total, stage) => total + (stage.tokenCost?.estimatedCost || 0), 0)

  const getTotalTokens = () =>
    stages.filter((stage) => stage.tokenCost).reduce((total, stage) => total + (stage.tokenCost?.totalTokens || 0), 0)

  const getTotalDuration = () => {
    if (!pipelineStartTime) return 0
    const completedStages = stages.filter((stage) => stage.endTime)
    if (completedStages.length === 0) return 0
    const lastCompletedTime = Math.max(...completedStages.map((stage) => stage.endTime!.getTime()))
    return lastCompletedTime - pipelineStartTime.getTime()
  }

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`
    const seconds = Math.floor(ms / 1000)
    if (seconds < 60) return `${seconds}s`
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return `${minutes}m ${remainingSeconds}s`
  }

  const handleStreamUpdate = (update: {
    stage: string
    status: "running" | "success" | "error" | "completed"
    result?: Record<string, any>
    subStage?: string
    tokenCost?: TokenCost
    startTimeMs?: number
    endTimeMs?: number
    durationMs?: number
  }) => {
    const { stage, status, result, subStage, tokenCost, startTimeMs, endTimeMs, durationMs } = update

    if (!subStage) {
      setSelectedStageId(stage)

      // Compute times synchronously to avoid batching issues
      const nowMs = Date.now()
      if (status === "running") {
        stageStartRef.current[stage] = startTimeMs ?? nowMs
      }

      setStages((prevStages) =>
        prevStages.map((currentStage) => {
          if (currentStage.id !== stage) return currentStage

          const timeUpdates: Partial<PipelineStageType> = { status, result, tokenCost }

          // Prefer server timings if present
          if (typeof startTimeMs === "number") timeUpdates.startTime = new Date(startTimeMs)
          if (typeof endTimeMs === "number") timeUpdates.endTime = new Date(endTimeMs)
          if (typeof durationMs === "number") timeUpdates.duration = Math.max(0, durationMs)

          // If server didn't send timing, compute here with our ref to avoid batching races
          if (!startTimeMs && status === "running") {
            timeUpdates.startTime = new Date(stageStartRef.current[stage] || nowMs)
          } else if (!durationMs && (status === "success" || status === "error")) {
            const startMs =
              stageStartRef.current[stage] ??
              currentStage.startTime?.getTime() ??
              pipelineStartTime?.getTime() ??
              nowMs
            const end = new Date(endTimeMs ?? nowMs)
            timeUpdates.startTime = new Date(startMs)
            timeUpdates.endTime = end
            timeUpdates.duration = Math.max(0, end.getTime() - startMs)
          }

          return { ...currentStage, ...timeUpdates }
        }),
      )
    } else {
      updateSubStage(stage, subStage, status)
    }
  }

  const runPipeline = async () => {
    setIsRunning(true)
    setPipelineStartTime(new Date())
    onGenerateCircuit?.()

    // Reset local start cache
    stageStartRef.current = {}

    setStages((prev) =>
      prev.map((stage) => ({
        ...stage,
        status: "pending" as const,
        result: undefined,
        tokenCost: undefined,
        startTime: undefined,
        endTime: undefined,
        duration: undefined,
        subStages: stage.subStages?.map((sub) => ({ ...sub, status: "pending" as const })),
      })),
    )

    const conversationContext = getConversationContext()

    try {
      const response = await fetch("/api/generate-circuit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userInput: messages[0].content,
          conversationContext: messages,
          selectedModel,
          requirements: conversationContext,
        }),
      })

      if (!response.ok) throw new Error("Failed to start circuit generation")

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error("No response stream available")

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        const lines = chunk.split("\n")
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue

          try {
            // Parse the SSE payload (and defensively unwrap if double-wrapped)
            let evt: any = JSON.parse(line.slice(6))
            if (typeof evt?.payload === "string" && evt.payload.startsWith("data: ")) {
              evt = JSON.parse(evt.payload.slice(6))
            }

            const type = evt?.type as string | undefined

            if (type === "workflow_started") {
              const stage = evt.workflow as string
              handleStreamUpdate({ stage, status: "running" })
              continue
            }

            if (type === "workflow_succeeded") {
              const stage = evt.workflow as string
              const ctx = evt.context ?? {}
              const durationMs =
                typeof ctx.duration_ns === "number" ? Math.max(0, Math.floor(ctx.duration_ns / 1_000_000)) : undefined
              const tokenCost = {
                inputTokens: Number(ctx.input_tokens ?? 0),
                outputTokens: Number(ctx.output_tokens ?? 0),
                totalTokens: Number(ctx.total_tokens ?? 0),
                estimatedCost: Number(ctx.cost ?? 0),
              }
              let resultObj: Record<string, any> | undefined
              const raw = evt.result
              if (raw != null) {
                if (typeof raw === "object") {
                  resultObj = raw as Record<string, any>
                } else if (typeof raw === "string") {
                  try {
                    const parsed = JSON.parse(raw)
                    resultObj = typeof parsed === "object" && parsed !== null ? parsed : { displayed_result: raw }
                  } catch {
                    resultObj = { displayed_result: raw }
                  }
                }
              }

              handleStreamUpdate({ stage, status: "success", result: resultObj, tokenCost, durationMs })
              continue
            }

            if (type === "workflow_failed") {
              const stage = evt.workflow as string
              const ctx = evt.context ?? {}
              const durationMs =
                typeof ctx.duration_ns === "number" ? Math.max(0, Math.floor(ctx.duration_ns / 1_000_000)) : undefined
              const tokenCost = {
                inputTokens: Number(ctx.input_tokens ?? 0),
                outputTokens: Number(ctx.output_tokens ?? 0),
                totalTokens: Number(ctx.total_tokens ?? 0),
                estimatedCost: Number(ctx.cost ?? 0),
              }
              let resultObj: Record<string, any> | undefined
              const raw = evt.error ?? evt.result
              if (raw != null) {
                if (typeof raw === "object") {
                  resultObj = raw as Record<string, any>
                } else if (typeof raw === "string") {
                  try {
                    const parsed = JSON.parse(raw)
                    resultObj = typeof parsed === "object" && parsed !== null ? parsed : { displayed_result: raw }
                  } catch {
                    resultObj = { displayed_result: raw }
                  }
                }
              }
              handleStreamUpdate({ stage, status: "error", result: resultObj, tokenCost, durationMs })
              continue
            }

            if (type === "substage_started") {
              const stage = evt.workflow as string
              const subStage = evt.substage as string
              handleStreamUpdate({ stage, subStage, status: "running" })
              continue
            }

            if (type === "substage_completed") {
              const stage = evt.workflow as string
              const subStage = evt.substage as string
              handleStreamUpdate({ stage, subStage, status: "success" })
              continue
            }

            // Optional: ignore run_* for UI
            // run_started, run_succeeded, run_failed → no-op

          } catch (e) {
            console.error("Failed to parse stream update:", e)
          }
        }
      }
    } catch (error: any) {
      console.error("Pipeline execution failed:", error)
      setStages((prev) =>
        prev.map((stage) => (stage.status === "running" ? { ...stage, status: "error" as const } : stage)),
      )
    } finally {
      setIsRunning(false)
    }
  }

  const resetPipeline = () => {
    stageStartRef.current = {}
    setStages((prev) =>
      prev.map((stage) => ({
        ...stage,
        status: "pending" as const,
        result: undefined,
        tokenCost: undefined,
        startTime: undefined,
        endTime: undefined,
        duration: undefined,
        subStages: stage.subStages?.map((sub) => ({ ...sub, status: "pending" as const })),
      })),
    )
    setSelectedStageId("spec_generation")
    setPipelineStartTime(null)
  }

  const hasConversation = messages.length > 0
  const selectedStage = stages.find((stage) => stage.id === selectedStageId)
  const formatResultValues = (res: Record<string, any>) => {
    const vals = Object.values(res ?? {})
    if (vals.length === 0) return ""
    return vals
      .map((v) => {
        if (v == null) return ""
        if (typeof v === "string") return v
        if (typeof v === "number" || typeof v === "boolean") return String(v)
        try {
          return JSON.stringify(v, null, 2)
        } catch {
          return String(v)
        }
      })
      .filter(Boolean)
      .join("\n\n")
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Circuit Design Pipeline</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={resetPipeline} disabled={isRunning}>
              <RotateCcw className="h-4 w-4 mr-1" />
              Reset
            </Button>
            <Button onClick={runPipeline} disabled={isRunning || !hasConversation} size="sm">
              <Zap className="h-4 w-4 mr-1" />
              Generate Circuit
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {hasConversation && (
          <div className="p-3 bg-muted/50 rounded-lg">
            <p className="text-sm font-medium mb-1">Conversation Context:</p>
            <p className="text-xs text-muted-foreground">
              {messages.length} message{messages.length !== 1 ? "s" : ""} • Model: {selectedModel}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              "{getConversationContext().slice(0, 100)}
              {getConversationContext().length > 100 ? "..." : ""}"
            </p>
          </div>
        )}

        {!hasConversation && (
          <div className="p-3 bg-muted/30 rounded-lg text-center">
            <p className="text-sm text-muted-foreground">
              Start a conversation above to provide context for circuit generation
            </p>
          </div>
        )}

        {settings.showTokenCost && (
          <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-blue-600" />
                <span className="text-sm font-medium text-blue-800">Total Usage</span>
              </div>
              <div className="flex items-center gap-4 text-sm text-blue-700">
                <span>{getTotalTokens().toLocaleString()} tokens</span>
                <div className="flex items-center gap-1">
                  <DollarSign className="h-3 w-3" />
                  <span>{getTotalCost().toFixed(4)}</span>
                </div>
                {getTotalDuration() > 0 && (
                  <div className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    <span>{formatDuration(getTotalDuration())}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Progress</span>
            <span>{Math.round(getProgressPercentage())}%</span>
          </div>
          <Progress value={getProgressPercentage()} className="h-2 transition-all duration-500 ease-out" />
        </div>

        <div className="flex justify-between items-center">
          {getVisibleStages().map((stage) => {
            return (
              <button
                key={stage.id}
                onClick={() => setSelectedStageId(stage.id)}
                className={`flex flex-col items-center space-y-2 p-2 rounded-lg transition-all duration-300 ease-in-out transform hover:scale-105 ${
                  selectedStageId === stage.id ? "bg-muted shadow-sm" : "hover:bg-muted/50"
                }`}
              >
                <div className="flex items-center justify-center w-8 h-8 rounded-full border-2 border-muted-foreground/20 bg-background transition-all duration-300 ease-in-out">
                  {getStageIcon(stage.status)}
                </div>
                <div className="text-center">
                  <p className="text-xs font-medium">{stage.name}</p>
                  <div className="transition-all duration-200 ease-in-out">{getStatusBadge(stage.status)}</div>
                  <div className="flex flex-col items-center gap-1 mt-1">
                    {settings.showTokenCost && stage.tokenCost && stage.status === "success" && (
                      <div className="flex items-center gap-1 text-xs text-muted-foreground animate-in fade-in duration-300">
                        <DollarSign className="h-3 w-3" />
                        <span>{stage.tokenCost.estimatedCost.toFixed(4)}</span>
                      </div>
                    )}
                    {typeof stage.duration === "number" && (
                      <div className="flex items-center gap-1 text-xs text-muted-foreground animate-in fade-in duration-300">
                        <Clock className="h-3 w-3" />
                        <span>{formatDuration(stage.duration)}</span>
                      </div>
                    )}
                  </div>
                </div>
              </button>
            )
          })}
        </div>

        {selectedStage && (
          <Card className="border-muted transition-all duration-300 ease-in-out animate-in slide-in-from-bottom-2">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                {getStageIcon(selectedStage.status)}
                {selectedStage.name}
                {getStatusBadge(selectedStage.status)}
                {typeof selectedStage.duration === "number" && (
                  <span className="text-sm font-normal text-muted-foreground ml-2">
                    ({formatDuration(selectedStage.duration)})
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {settings.showTokenCost && selectedStage.tokenCost && selectedStage.status === "success" && (
                <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
                  <p className="text-sm font-medium text-green-800 mb-2">Token Usage</p>
                  <div className="grid grid-cols-2 gap-4 text-xs text-green-700">
                    <div>
                      <span className="font-medium">Input tokens:</span>{" "}
                      {selectedStage.tokenCost.inputTokens.toLocaleString()}
                    </div>
                    <div>
                      <span className="font-medium">Output tokens:</span>{" "}
                      {selectedStage.tokenCost.outputTokens.toLocaleString()}
                    </div>
                    <div>
                      <span className="font-medium">Total tokens:</span>{" "}
                      {selectedStage.tokenCost.totalTokens.toLocaleString()}
                    </div>
                    <div>
                      <span className="font-medium">Estimated cost:</span> $
                      {selectedStage.tokenCost.estimatedCost.toFixed(4)}
                    </div>
                  </div>
                </div>
              )}

              {selectedStage.subStages && (
                <div className="mb-4">
                  <p className="text-sm font-medium mb-2">Sub-stages:</p>
                  <div className="space-y-1">
                    {selectedStage.subStages.map((sub) => (
                      <div key={sub.id} className="flex items-center gap-2 text-sm">
                        {getStageIcon(sub.status)}
                        <span className={sub.status === "error" ? "text-red-600" : ""}>{sub.name}</span>
                        {sub.status === "error" && <span className="text-xs text-red-500 ml-auto">Failed</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedStage.result ? (
                <div className="bg-muted/30 rounded p-3">
                  <p className="text-sm font-medium mb-2">Results:</p>
                  <div className="text-sm text-muted-foreground whitespace-pre-wrap">
                    {formatResultValues(selectedStage.result)}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {selectedStage.status === "pending"
                    ? "Waiting to start..."
                    : selectedStage.status === "running"
                    ? "Processing..."
                    : "No results available"}
                </p>
              )}
            </CardContent>
          </Card>
        )}
      </CardContent>
    </Card>
  )
}
