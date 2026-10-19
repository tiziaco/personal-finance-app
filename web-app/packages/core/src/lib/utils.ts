import { clsx, type ClassValue } from "clsx"
import { extendTailwindMerge } from "tailwind-merge"

// The Finsight type scale (globals.css's @theme): without it tailwind-merge reads
// text-caption as a colour, so it neither replaces text-sm nor survives a text colour.
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: [
        "display",
        "h1",
        "h2",
        "h3",
        "body",
        "label",
        "caption",
        "hero",
        "amount",
      ],
    },
  },
})

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
