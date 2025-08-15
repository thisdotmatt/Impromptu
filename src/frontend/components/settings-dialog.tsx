"use client"

import { useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Settings, HelpCircle } from "lucide-react"

export type SettingsType = {
  showTokenCost: boolean
}

type SettingsDialogProps = {
  settings: SettingsType
  onSettingsChange: (settings: SettingsType) => void
  onShowTutorial?: () => void
}

export function SettingsDialog({ settings, onSettingsChange, onShowTutorial }: SettingsDialogProps) {
  const [open, setOpen] = useState(false)

  const handleToggleTokenCost = (checked: boolean) => {
    onSettingsChange({
      ...settings,
      showTokenCost: checked,
    })
  }

  const handleShowTutorial = () => {
    setOpen(false)
    onShowTutorial?.()
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
          <Settings className="h-4 w-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
        </DialogHeader>
        <div className="space-y-6 py-4">
          <div className="space-y-4">
            <h4 className="text-sm font-medium">Pipeline Display</h4>
            <div className="flex items-center space-x-2">
              <Checkbox id="show-token-cost" checked={settings.showTokenCost} onCheckedChange={handleToggleTokenCost} />
              <Label htmlFor="show-token-cost" className="text-sm">
                Show token count and cost in pipeline stages
              </Label>
            </div>
            <p className="text-xs text-muted-foreground">
              Display token usage and estimated cost for each pipeline stage when available.
            </p>
          </div>

          <div className="space-y-4">
            <h4 className="text-sm font-medium">Help & Tutorial</h4>
            <Button
              variant="outline"
              size="sm"
              onClick={handleShowTutorial}
              className="w-full justify-start bg-transparent"
            >
              <HelpCircle className="h-4 w-4 mr-2" />
              Show Tutorial
            </Button>
            <p className="text-xs text-muted-foreground">
              View the getting started tutorial to learn how to use Impromptu.
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
