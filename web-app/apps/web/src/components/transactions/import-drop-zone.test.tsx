import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { ImportDropZone } from "./import-drop-zone"

describe("ImportDropZone", () => {
  it("does not take a second file while an upload is pending", async () => {
    const onFile = vi.fn()
    render(<ImportDropZone onFile={onFile} pending />)
    const input = screen.getByLabelText("CSV file")
    expect(input).toBeDisabled()
    await userEvent
      .setup({ applyAccept: false })
      .upload(input, new File(["x"], "a.csv"))
    expect(onFile).not.toHaveBeenCalled()
  })
})
