"use client"

import {
  MarkdownTextPrimitive,
  memoizeMarkdownComponents,
  useIsMarkdownCodeBlock,
} from "@assistant-ui/react-markdown"
import { cn } from "@app/core/lib/utils"
import { memo, type ComponentProps } from "react"
import remarkGfm from "remark-gfm"

function InlineOrBlockCode({ className, ...props }: ComponentProps<"code">) {
  const isBlock = useIsMarkdownCodeBlock()
  return (
    <code
      className={cn(
        !isBlock && "rounded bg-muted px-1 py-0.5 font-mono text-[0.9em]",
        className,
      )}
      {...props}
    />
  )
}

// Element → Tailwind classes, in place of @tailwindcss/typography.
// No rehype-raw: raw HTML in a reply renders as text, never as markup.
const components = memoizeMarkdownComponents({
  h1: ({ className, ...p }) => (
    <h1
      className={cn("mt-4 mb-2 text-lg font-semibold first:mt-0", className)}
      {...p}
    />
  ),
  h2: ({ className, ...p }) => (
    <h2
      className={cn("mt-4 mb-2 text-base font-semibold first:mt-0", className)}
      {...p}
    />
  ),
  h3: ({ className, ...p }) => (
    <h3
      className={cn("mt-3 mb-1 font-semibold first:mt-0", className)}
      {...p}
    />
  ),
  p: ({ className, ...p }) => (
    <p
      className={cn("my-2 leading-relaxed first:mt-0 last:mb-0", className)}
      {...p}
    />
  ),
  ul: ({ className, ...p }) => (
    <ul className={cn("my-2 ml-5 list-disc", className)} {...p} />
  ),
  ol: ({ className, ...p }) => (
    <ol className={cn("my-2 ml-5 list-decimal", className)} {...p} />
  ),
  li: ({ className, ...p }) => <li className={cn("my-1", className)} {...p} />,
  a: ({ className, ...p }) => (
    <a
      className={cn("text-primary underline underline-offset-2", className)}
      target="_blank"
      rel="noopener noreferrer"
      {...p}
    />
  ),
  // Never an <img>: the browser would fetch it unasked, so a prompt-injected
  // reply could carry data out in the URL. The image is a link to click.
  img: ({ src, alt, className }) => {
    const href = typeof src === "string" ? src : undefined
    const label = alt || href
    if (!href) return label ? <span className={className}>{label}</span> : null
    return (
      <a
        href={href}
        className={cn("text-primary underline underline-offset-2", className)}
        target="_blank"
        rel="noopener noreferrer"
      >
        {label}
      </a>
    )
  },
  blockquote: ({ className, ...p }) => (
    <blockquote
      className={cn("my-2 border-l-2 pl-3 text-muted-foreground", className)}
      {...p}
    />
  ),
  hr: ({ className, ...p }) => (
    <hr className={cn("my-4 border-border", className)} {...p} />
  ),
  table: ({ className, ...p }) => (
    <div className="my-3 overflow-x-auto">
      <table
        className={cn("w-full border-collapse text-sm", className)}
        {...p}
      />
    </div>
  ),
  th: ({ className, ...p }) => (
    <th
      className={cn("border px-2 py-1 text-left font-medium", className)}
      {...p}
    />
  ),
  td: ({ className, ...p }) => (
    <td className={cn("border px-2 py-1", className)} {...p} />
  ),
  pre: ({ className, ...p }) => (
    <pre
      className={cn(
        "my-3 overflow-x-auto rounded-lg bg-muted p-3 text-sm",
        className,
      )}
      {...p}
    />
  ),
  code: InlineOrBlockCode,
})

function MarkdownTextImpl() {
  return (
    <MarkdownTextPrimitive
      remarkPlugins={[remarkGfm]}
      components={components}
      className="text-sm"
    />
  )
}

export const MarkdownText = memo(MarkdownTextImpl)
