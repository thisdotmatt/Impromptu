"use client"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { MessageCircle, Cpu, Factory, X, Zap } from "lucide-react"

interface TutorialOverlayProps {
  isOpen: boolean
  onClose: () => void
}

export function TutorialOverlay({ isOpen, onClose }: TutorialOverlayProps) {
  if (!isOpen) return null

  const handleClose = () => {
    onClose()
    // Only set localStorage if this was the first-time tutorial
    if (!localStorage.getItem("impromptu-tutorial-seen")) {
      localStorage.setItem("impromptu-tutorial-seen", "true")
    }
  }

  const steps = [
    {
      icon: MessageCircle,
      title: "Chat",
      description: "Discuss your business needs with an LLM",
      detail:
        "Start by describing your circuit requirements, specifications, and constraints through natural conversation.",
    },
    {
      icon: Cpu,
      title: "Design",
      description: "Automatically generate a verified circuit design",
      detail:
        "Our AI agents create optimized circuit designs, run simulations, and verify functionality automatically.",
    },
    {
      icon: Factory,
      title: "Build",
      description: "Send your design to the pick-and-place machine to be built on a physical board",
      detail: "Seamlessly transfer your verified design to manufacturing with automated component placement.",
    },
  ]

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-4xl max-h-[90vh] overflow-y-auto">
        <CardContent className="p-8">
          <div className="flex justify-between items-start mb-8">
            <div className="flex items-center gap-3">
              <Zap className="h-8 w-8 text-primary" />
              <h1 className="text-4xl font-bold">Impromptu</h1>
            </div>
            <Button variant="ghost" size="icon" onClick={handleClose}>
              <X className="h-5 w-5" />
            </Button>
          </div>

          <div className="text-center mb-12">
            <h2 className="text-2xl font-semibold mb-4">End-to-End Automatic Circuit Design</h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              From conversation to physical circuit board in three simple steps. Let AI handle the complexity while you
              focus on innovation.
            </p>
          </div>

          <div className="relative mb-8">
            <div className="hidden md:block absolute top-10 left-0 w-full h-0.5 bg-border z-0" />

            <div className="grid md:grid-cols-3 gap-8">
              {steps.map((step, index) => {
                const Icon = step.icon
                return (
                  <div key={index} className="text-center relative">
                    <div className="relative inline-block mb-6">
                      <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center">
                        <Icon className="h-10 w-10 text-primary" />
                      </div>
                      <div className="absolute -top-1 -right-1 w-7 h-7 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm font-semibold">
                        {index + 1}
                      </div>
                    </div>
                    <h3 className="text-xl font-semibold mb-2">{step.title}</h3>
                    <p className="text-sm text-muted-foreground mb-3">{step.description}</p>
                    <p className="text-xs text-muted-foreground">{step.detail}</p>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="text-center">
            <Button onClick={handleClose} size="lg" className="px-8">
              Get Started
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
