import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { useAppAuth } from "@app/auth"
import { WelcomeHeader } from "./welcome-header"
import { formatMonth } from "./month"

vi.mock("@app/auth", () => ({ useAppAuth: vi.fn() }))

const signedIn = (name: string | null) =>
  vi.mocked(useAppAuth).mockReturnValue({
    user: { name, email: null, imageUrl: null },
    isLoaded: true,
  } as unknown as ReturnType<typeof useAppAuth>)

describe("WelcomeHeader", () => {
  it("greets by first name and names the reference month", () => {
    signedIn("Ada Lovelace")
    render(<WelcomeHeader referenceMonth="2026-09" />)
    expect(
      screen.getByRole("heading", { name: "Welcome back, Ada" }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(`Your overview for ${formatMonth("2026-09")}`),
    ).toBeInTheDocument()
  })

  it("falls back without a name or a month", () => {
    signedIn(null)
    render(<WelcomeHeader referenceMonth={null} />)
    expect(
      screen.getByRole("heading", { name: "Welcome back" }),
    ).toBeInTheDocument()
    expect(screen.getByText("Your overview")).toBeInTheDocument()
  })
})
