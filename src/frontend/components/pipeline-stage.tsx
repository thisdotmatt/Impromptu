"use client"

import type React from "react"

import { useState } from "react"
import { ChevronDown, ChevronRight, CheckCircle, XCircle, Loader2, Circle } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export type StageStatus = "pending" | "running" | "success" | "error"

export type SubStage = {
  id: string
  name: string
  status: StageStatus
  result?: string
}

export type PipelineStage = {
  id: string
  name: string
  status: StageStatus
  result?: string | React.ReactNode
  subStages?: SubStage[]
}

interface PipelineStageProps {
  stage: PipelineStage
  isExpanded?: boolean
  onToggle?: () => void
}

const getStatusIcon = (status: StageStatus) => {
  switch (status) {
    case "pending":
      return <Circle className="h-4 w-4 text-muted-foreground" />
    case "running":
      return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
    case "success":
      return <CheckCircle className="h-4 w-4 text-green-500" />
    case "error":
      return <XCircle className="h-4 w-4 text-red-500" />
  }
}

const getStatusColor = (status: StageStatus) => {
  switch (status) {
    case "pending":
      return "text-muted-foreground"
    case "running":
      return "text-blue-600"
    case "success":
      return "text-green-600"
    case "error":
      return "text-red-600"
  }
}

export function PipelineStage({ stage, isExpanded = false, onToggle }: PipelineStageProps) {
  const [localExpanded, setLocalExpanded] = useState(isExpanded)
  const expanded = onToggle ? isExpanded : localExpanded
  const toggleExpanded = onToggle || (() => setLocalExpanded(!localExpanded))

  const hasContent = stage.result || stage.subStages?.length
  const canExpand = hasContent && (stage.status === "success" || stage.status === "error" || stage.subStages?.length)

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 group">
        {canExpand ? (
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={toggleExpanded}>
            {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          </Button>
        ) : (
          <div className="w-6" />
        )}

        {getStatusIcon(stage.status)}

        <span className={`font-medium ${getStatusColor(stage.status)}`}>{stage.name}</span>
      </div>

      {expanded && hasContent && (
        <div className="ml-9 space-y-3">
          {/* Sub-stages */}
          {stage.subStages && stage.subStages.length > 0 && (
            <div className="space-y-2">
              {stage.subStages.map((subStage) => (
                <div key={subStage.id} className="flex items-center gap-3">
                  <div className="w-6" />
                  {getStatusIcon(subStage.status)}
                  <span className={`text-sm ${getStatusColor(subStage.status)}`}>{subStage.name}</span>
                </div>
              ))}
            </div>
          )}

          {/* Stage result */}
          {stage.result && (
            <Card className="bg-muted/50">
              <CardContent className="p-3">
                {typeof stage.result === "string" ? (
                  <pre className="text-xs whitespace-pre-wrap font-mono">{stage.result}</pre>
                ) : (
                  stage.result
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
