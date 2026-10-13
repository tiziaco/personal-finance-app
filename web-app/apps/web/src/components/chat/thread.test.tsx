import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeAll, describe, expect, it, vi } from "vitest"

import { CHAT_COPY } from "./copy"
import { TestRuntime } from "./test-runtime"
import { Thread } from "./thread"

beforeAll(() => {
  // jsdom has no layout: the viewport's auto-scroll calls these.
  Element.prototype.scrollTo ??= () => {}
  Element.prototype.scrollIntoView ??= () => {}
})

const user = (id: string, content: string) =>
  ({ id, role: "user", content }) as const
const assistant = (id: string, content: string, status?: object) =>
  ({ id, role: "assistant", content, status }) as never

describe("Thread", () => {
  it("shows the welcome state when there are no messages", () => {
    render(
      <TestRuntime messages={[]}>
        <Thread />
      </TestRuntime>,
    )
    expect(screen.getByText(CHAT_COPY.welcomeTitle)).toBeInTheDocument()
  })

  it("renders assistant replies as Markdown and user text as plain text", () => {
    render(
      <TestRuntime
        messages={[
          user("u1", "**not bold**"),
          assistant("a1", "Here is **bold** and a [link](https://example.com)"),
        ]}
      >
        <Thread />
      </TestRuntime>,
    )
    expect(screen.getByText("**not bold**")).toBeInTheDocument()
    expect(screen.getByText("bold").tagName).toBe("STRONG")
    const link = screen.getByRole("link", { name: "link" })
    expect(link).toHaveAttribute("target", "_blank")
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"))
  })

  it("renders raw HTML in a reply as text, not markup", () => {
    render(
      <TestRuntime messages={[assistant("a1", "<img src=x onerror=alert(1)>")]}>
        <Thread />
      </TestRuntime>,
    )
    expect(document.querySelector("img")).toBeNull()
  })

  it("marks a stopped reply and a failed reply with our own copy", () => {
    render(
      <TestRuntime
        messages={[
          user("u1", "one"),
          assistant("a1", "partial", {
            type: "incomplete",
            reason: "cancelled",
          }),
          user("u2", "two"),
          assistant("a2", "", { type: "incomplete", reason: "error" }),
        ]}
      >
        <Thread />
      </TestRuntime>,
    )
    expect(screen.getByText(CHAT_COPY.stopped)).toBeInTheDocument()
    expect(screen.getByText(CHAT_COPY.failed)).toBeInTheDocument()
  })

  it("offers no edit or regenerate action", () => {
    render(
      <TestRuntime messages={[user("u1", "q"), assistant("a1", "a")]}>
        <Thread />
      </TestRuntime>,
    )
    expect(screen.queryByRole("button", { name: /edit/i })).toBeNull()
    expect(
      screen.queryByRole("button", { name: /regenerate|reload/i }),
    ).toBeNull()
  })

  it("sends with Enter and swaps Send for Stop while running", async () => {
    const onNew = vi.fn(async () => {})
    const { rerender } = render(
      <TestRuntime messages={[]} onNew={onNew}>
        <Thread />
      </TestRuntime>,
    )
    await userEvent.type(
      screen.getByRole("textbox", { name: CHAT_COPY.inputLabel }),
      "hello{Enter}",
    )
    expect(onNew).toHaveBeenCalledOnce()

    const onCancel = vi.fn(async () => {})
    rerender(
      <TestRuntime
        messages={[user("u1", "hello")]}
        isRunning
        onCancel={onCancel}
      >
        <Thread />
      </TestRuntime>,
    )
    await userEvent.click(screen.getByRole("button", { name: CHAT_COPY.stop }))
    expect(onCancel).toHaveBeenCalledOnce()
    expect(screen.queryByRole("button", { name: CHAT_COPY.send })).toBeNull()
  })

  it("caps the input at the server's message limit", () => {
    render(
      <TestRuntime messages={[]}>
        <Thread />
      </TestRuntime>,
    )
    expect(
      screen.getByRole("textbox", { name: CHAT_COPY.inputLabel }),
    ).toHaveAttribute("maxLength", "3000")
  })
})
