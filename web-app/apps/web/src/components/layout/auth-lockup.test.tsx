import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AuthLockup } from "./auth-lockup"

describe("AuthLockup", () => {
  it("shows the Finsight mark and wordmark above the form", () => {
    render(
      <AuthLockup>
        <form aria-label="Sign in" />
      </AuthLockup>,
    )
    const mark = screen.getByRole("img", { name: "Finsight" })
    const wordmark = screen.getByText("Finsight")
    const form = screen.getByRole("form", { name: "Sign in" })
    expect(mark).toBeInTheDocument()
    expect(
      wordmark.compareDocumentPosition(form) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })
})
