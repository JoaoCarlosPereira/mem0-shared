import { act, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { toast } from "sonner"
import { downloadSkillArtifact } from "@/lib/admin-api"
import type { SkillResponse } from "@/lib/admin-api"
import { SkillDetail } from "../skill-detail"

vi.mock("@/lib/admin-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/admin-api")>()
  return { ...actual, downloadSkillArtifact: vi.fn() }
})

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const latestSkill: SkillResponse = {
  skill: {
    name: "code-review",
    namespace: "team-a",
    title: "Code Review",
    description: "Reviews code changes.",
    tag: "2.0.0",
  },
  _meta: {},
}

const previousSkill: SkillResponse = {
  skill: {
    ...latestSkill.skill,
    namespace: "team-b",
    tag: "1.0.0",
  },
  _meta: {},
}

const downloadMock = vi.mocked(downloadSkillArtifact)

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:skill-package"),
    revokeObjectURL: vi.fn(),
  })
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe("SkillDetail package download", () => {
  it("downloads the selected tag and namespace and reports success", async () => {
    const blob = new Blob(["package"], { type: "application/vnd.agentregistry.skill.v1.tar+gzip" })
    downloadMock.mockResolvedValue({ blob, filename: "code-review-1.0.0.tar.gz" })
    const user = userEvent.setup()
    const { unmount } = render(<SkillDetail skill={latestSkill} allTags={[latestSkill, previousSkill]} />)

    await user.click(screen.getByRole("combobox"))
    await user.click(screen.getByRole("option", { name: "1.0.0" }))
    await user.click(screen.getByRole("button", { name: "Download package" }))

    await waitFor(() => {
      expect(downloadMock).toHaveBeenCalledWith("code-review", "1.0.0", "team-b")
    })
    expect(URL.createObjectURL).toHaveBeenCalledWith(blob)
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledOnce()
    expect(toast.success).toHaveBeenCalledWith("Downloaded code-review-1.0.0.tar.gz")

    unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:skill-package")
  })

  it("shows a loading state while the package request is pending", async () => {
    let resolveDownload: ((value: { blob: Blob; filename: string }) => void) | undefined
    downloadMock.mockReturnValue(new Promise((resolve) => { resolveDownload = resolve }))
    const user = userEvent.setup()
    render(<SkillDetail skill={latestSkill} />)

    await user.click(screen.getByRole("button", { name: "Download package" }))

    expect(screen.getByRole("button", { name: "Downloading..." })).toBeDisabled()

    await act(async () => {
      resolveDownload?.({ blob: new Blob(["package"]), filename: "code-review.zip" })
    })
    await waitFor(() => expect(screen.getByRole("button", { name: "Download package" })).toBeEnabled())
  })

  it("reports download failures and restores the button", async () => {
    downloadMock.mockRejectedValue(new Error("Package is not available"))
    const user = userEvent.setup()
    render(<SkillDetail skill={latestSkill} />)

    await user.click(screen.getByRole("button", { name: "Download package" }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Package is not available"))
    expect(screen.getByRole("button", { name: "Download package" })).toBeEnabled()
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })
})
