import * as React from "react"
import * as ProgressPrimitive from "@radix-ui/react-progress"
import { cn } from "@/lib/utils"

const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & {
    showValue?: boolean
    variant?: "default" | "success" | "error" | "warning"
  }
>(({ className, value, showValue = false, variant = "default", ...props }, ref) => {
  const getIndicatorColor = () => {
    switch (variant) {
      case "success":
        return "bg-green-600"
      case "error":
        return "bg-red-600"
      case "warning":
        return "bg-yellow-600"
      default:
        return "bg-primary"
    }
  }

  return (
    <div className="w-full">
      <ProgressPrimitive.Root
        ref={ref}
        className={cn(
          "relative h-4 w-full overflow-hidden rounded-full bg-secondary",
          className
        )}
        {...props}
      >
        <ProgressPrimitive.Indicator
          className={cn(
            "h-full w-full flex-1 transition-all duration-300",
            getIndicatorColor()
          )}
          style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
        />
      </ProgressPrimitive.Root>
      {showValue && (
        <div className="mt-2 flex justify-between text-sm text-muted-foreground">
          <span>Progress</span>
          <span>{Math.round(value || 0)}%</span>
        </div>
      )}
    </div>
  )
})
Progress.displayName = ProgressPrimitive.Root.displayName

export { Progress }