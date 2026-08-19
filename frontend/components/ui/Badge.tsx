import { cn } from "@/lib/utils";

const styles: Record<string, string> = {
  info: "bg-stone-100 text-stone-600",
  suggestion: "bg-amber-50 text-amber-800",
  warning: "bg-red-50 text-red-700",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span
      className={cn(
        "inline-block rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
        styles[severity] || styles.info
      )}
    >
      {severity}
    </span>
  );
}
