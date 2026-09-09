import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-white/[0.07] bg-[#0c0c10]/95 p-4 shadow-[0_20px_45px_-15px_rgba(0,0,0,0.9),inset_0_1px_0_0_rgba(255,255,255,0.07)] backdrop-blur-2xl transition-all duration-200 hover:border-white/[0.13] sm:p-5",
        className,
      )}
      {...props}
    />
  );
}
