"use client";

import * as React from "react";
import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip";
import { cn } from "cn";

/**
 * Hover/focus tooltip. `content` is shown in the popup; `children` is the trigger element.
 */
function Tooltip({
  content,
  children,
  className,
  side = "top",
}: {
  content: React.ReactNode;
  children: React.ReactElement;
  className?: string;
  side?: "top" | "bottom" | "left" | "right";
}) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger delay={150} render={children} />
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Positioner
          side={side}
          sideOffset={6}
          className={"z-50"}
        >
          <TooltipPrimitive.Popup
            data-slot="tooltip-content"
            className={cn(
              "max-w-xs border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md whitespace-pre-wrap wrap-break-word origin-(--transform-origin) transition-[opacity,scale] duration-100 data-starting-style:scale-95 data-starting-style:opacity-0 data-ending-style:scale-95 data-ending-style:opacity-0",
              className,
            )}
          >
            {content}
          </TooltipPrimitive.Popup>
        </TooltipPrimitive.Positioner>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

export { Tooltip };
