import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AuthLockup } from "./auth-lockup"

describe("AuthLockup", () => {
  it("shows the Finsight mark and wordmark above the form, named once", () => {
    const { container } = render(
      <AuthLockup>
        <form aria-label="Sign in" />
      </AuthLockup>,
    )
    // The wordmark names it; the mark beside it is decorative, so a screen
    // reader does not hear "Finsight Finsight".
    expect(container.querySelector("svg")).toHaveAttribute(
      "aria-hidden",
      "true",
    )
    expect(screen.queryByRole("img", { name: "Finsight" })).toBeNull()
    const wordmark = screen.getByText("Finsight")
    const form = screen.getByRole("form", { name: "Sign in" })
    expect(
      wordmark.compareDocumentPosition(form) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })
})
