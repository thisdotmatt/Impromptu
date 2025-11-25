"use client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Download, Factory, Play, AlertCircle, CheckCircle } from "lucide-react"
import { useState } from "react"

interface CircuitToPrinterProps {
  isSimulationComplete: boolean
  circuitData?: () => string | null
  settings: { showTokenCost: boolean }
}

export function CircuitToPrinter({ isSimulationComplete, circuitData, settings }: CircuitToPrinterProps) {
  const isDesignComplete = isSimulationComplete
  const [isExecuting, setIsExecuting] = useState(false)
  const [executionStatus, setExecutionStatus] = useState<"idle" | "executing" | "success" | "error">("idle")
  const [executionMessage, setExecutionMessage] = useState<string>("")

  const downloadGcode = () => {
    const gcode = circuitData?.()
    if (!gcode) {
      setExecutionMessage("No G-code available")
      return
    }

    const blob = new Blob([gcode], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "circuit-board-placement.gcode"
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const executeGcode = async () => {
    const gcode = circuitData?.()
    if (!gcode) {
      setExecutionStatus("error")
      setExecutionMessage("No G-code available")
      return
    }

    setIsExecuting(true)
    setExecutionStatus("executing")
    setExecutionMessage("Sending G-code to printer...")

    try {
      const response = await fetch("/api/execute-gcode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gcode }),
      })

      const data = await response.json()

      if (data.status === "success") {
        setExecutionStatus("success")
        setExecutionMessage("G-code executed successfully! Check your printer.")
      } else {
        setExecutionStatus("error")
        setExecutionMessage(data.message || "Failed to execute G-code")
      }
    } catch (error) {
      setExecutionStatus("error")
      setExecutionMessage(error instanceof Error ? error.message : "Connection error")
    } finally {
      setIsExecuting(false)
    }
  }

  if (!isDesignComplete) {
    return (
      <Card className="opacity-60">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Factory className="h-16 w-16 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold text-muted-foreground mb-2">Execute G-code</h3>
          <p className="text-sm text-muted-foreground text-center">
            Complete all three stages to execute pick-and-place G-code
          </p>
          <Badge variant="secondary" className="mt-3">
            Requires Design Completion
          </Badge>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Factory className="h-5 w-5" />
            <span>Execute G-code</span>
            <Badge className="bg-green-100 text-green-800">Ready</Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-4 p-4 bg-orange-50 border border-orange-200 rounded-lg">
          <Factory className="h-12 w-12 text-orange-600" />
          <div>
            <h4 className="font-semibold text-orange-800">Pick-and-Place Execution</h4>
            <p className="text-sm text-orange-700">Execute G-code on your pick-and-place machine</p>
          </div>
        </div>

        <div className="text-center py-6 space-y-4">
          <div className="flex gap-3 justify-center">
            <Button
              onClick={executeGcode}
              disabled={isExecuting}
              size="lg"
              className="bg-green-600 hover:bg-green-700 text-white px-8 py-3"
            >
              <Play className="h-5 w-5 mr-2" />
              {isExecuting ? "Executing..." : "Run on Printer"}
            </Button>
            <Button
              onClick={downloadGcode}
              variant="outline"
              size="lg"
              className="px-8 py-3"
            >
              <Download className="h-5 w-5 mr-2" />
              Download G-code
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">
            circuit-board-placement.gcode
          </p>
        </div>

        {executionStatus !== "idle" && (
          <div
            className={`p-4 rounded-lg border flex gap-3 items-start ${
              executionStatus === "success"
                ? "bg-green-50 border-green-200"
                : executionStatus === "error"
                ? "bg-red-50 border-red-200"
                : "bg-blue-50 border-blue-200"
            }`}
          >
            {executionStatus === "success" ? (
              <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
            ) : executionStatus === "error" ? (
              <AlertCircle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
            ) : (
              <Play className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0 animate-pulse" />
            )}
            <div>
              <p
                className={`text-sm font-medium ${
                  executionStatus === "success"
                    ? "text-green-800"
                    : executionStatus === "error"
                    ? "text-red-800"
                    : "text-blue-800"
                }`}
              >
                {executionStatus === "executing" ? "Executing..." : executionStatus === "success" ? "Success" : "Error"}
              </p>
              <p
                className={`text-sm mt-1 ${
                  executionStatus === "success"
                    ? "text-green-700"
                    : executionStatus === "error"
                    ? "text-red-700"
                    : "text-blue-700"
                }`}
              >
                {executionMessage}
              </p>
            </div>
          </div>
        )}

        <div className="p-3 rounded-lg border bg-blue-50 border-blue-200">
          <p className="text-sm font-medium mb-2 text-blue-800">G-Code Preview:</p>
          <div className="text-xs whitespace-pre-wrap bg-background p-2 rounded border border-muted-foreground/10 max-h-64 overflow-y-auto font-mono">
            {circuitData?.() || "No G-code generated yet"}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
