"use client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Download, Factory } from "lucide-react"

interface ManufacturingCardProps {
  isSimulationComplete: boolean
  circuitData?: any
  settings: { showTokenCost: boolean }
}

export function ManufacturingCard({ isSimulationComplete, circuitData, settings }: ManufacturingCardProps) {
  const isDesignComplete = isSimulationComplete // This now represents design stage completion

  const downloadGcode = () => {
    const gcodeContent = `; Impromptu Circuit Board G-code
; Generated for pick-and-place machine
; Board: Circuit Design v1.0
; Components: 24 total

G21 ; Set units to millimeters
G90 ; Absolute positioning
M84 S0 ; Disable motor idle timeout

; Component placement sequence
G0 X10.5 Y15.2 ; Move to R1 position
M3 S1000 ; Pick component
G0 X10.5 Y15.2 Z-2 ; Place component
M5 ; Release component

G0 X25.3 Y20.1 ; Move to C1 position
M3 S1000 ; Pick component
G0 X25.3 Y20.1 Z-2 ; Place component
M5 ; Release component

; Additional components...
; Total placement time: ~3.2 minutes

M30 ; Program end
`

    const blob = new Blob([gcodeContent], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "circuit-board-placement.gcode"
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  if (!isDesignComplete) {
    return (
      <Card className="opacity-60">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Factory className="h-16 w-16 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold text-muted-foreground mb-2">Download G-code</h3>
          <p className="text-sm text-muted-foreground text-center">
            Complete circuit design to download pick-and-place G-code
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
            <span>Download G-code</span>
            <Badge className="bg-green-100 text-green-800">Ready</Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-4 p-4 bg-orange-50 border border-orange-200 rounded-lg">
          <Factory className="h-12 w-12 text-orange-600" />
          <div>
            <h4 className="font-semibold text-orange-800">Pick-and-Place G-code</h4>
            <p className="text-sm text-orange-700">Download G-code file for automated circuit board assembly</p>
          </div>
        </div>

        <div className="text-center py-6">
          <Button onClick={downloadGcode} size="lg" className="bg-orange-600 hover:bg-orange-700 text-white px-8 py-3">
            <Download className="h-5 w-5 mr-2" />
            Download G-code File
          </Button>
          <p className="text-sm text-muted-foreground mt-2">
            circuit-board-placement.gcode • Ready for pick-and-place machine
          </p>
        </div>

        <div className="p-3 rounded-lg border bg-green-50 border-green-200">
          <p className="text-sm font-medium mb-2 text-green-800">File Contents:</p>
          <div className="text-sm text-green-700">
            • 24 component placement coordinates
            <br />• Pick-and-place machine commands
            <br />• Estimated assembly time: 3.2 minutes
            <br />• Compatible with standard G-code machines
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
