import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
export const Dialog = DialogPrimitive.Root;
export const DialogTitle = DialogPrimitive.Title;
export const DialogDescription = DialogPrimitive.Description;
export function DialogContent({
  children,
  className,
  drawer = false,
}: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
  drawer?: boolean;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-[1000] bg-black/65 backdrop-blur-sm" />
      <DialogPrimitive.Content
        className={cn(
          "fixed z-[1001] border border-border bg-background p-7 shadow-2xl focus:outline-none",
          drawer
            ? "inset-y-0 right-0 w-full max-w-xl overflow-y-auto"
            : "left-1/2 top-1/2 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl",
          className,
        )}
      >
        {children}
        <DialogPrimitive.Close
          className="absolute right-4 top-4 rounded-md p-1 text-muted-foreground hover:text-foreground"
          aria-label="Close"
        >
          <X size={18} />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
