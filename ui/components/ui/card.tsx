import * as React from "react";
import { cn } from "@/lib/utils";

function Card({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("bg-card text-card-foreground flex flex-col gap-6 rounded-[var(--radius)] border py-6 shadow-sm", className)}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("grid auto-rows-min items-start gap-1.5 px-6", className)} {...props} />;
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("text-[11px] font-medium text-muted-foreground uppercase tracking-wider leading-none", className)} {...props} />;
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("px-6", className)} {...props} />;
}

export { Card, CardHeader, CardTitle, CardContent };
