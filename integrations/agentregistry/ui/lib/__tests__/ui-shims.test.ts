import { afterEach, describe, expect, it, vi } from "vitest"
import { client } from "@/lib/api/client.gen"
import { downloadSkillArtifact } from "../ui-shims"

describe("downloadSkillArtifact", () => {
  afterEach(() => {
    client.setConfig({ baseUrl: "", fetch: globalThis.fetch, headers: undefined })
    vi.restoreAllMocks()
  })

  it("downloads the selected skill artifact using the configured API base URL", async () => {
    const blob = new Blob(["package"], { type: "application/vnd.agentregistry.skill.v1.tar+gzip" })
    const requestFetch = vi.fn().mockResolvedValue(
      new Response(blob, {
        status: 200,
        headers: { "Content-Disposition": "attachment; filename*=UTF-8''review%20skill.tar.gz" },
      }),
    )
    client.setConfig({ baseUrl: "https://registry.example.test", fetch: requestFetch })

    await expect(downloadSkillArtifact("code review", "v1/beta", "team-a")).resolves.toEqual({
      blob: expect.any(Blob),
      filename: "review skill.tar.gz",
    })
    expect(requestFetch).toHaveBeenCalledWith(
      "https://registry.example.test/v0/skills/code%20review/v1%2Fbeta/artifact?namespace=team-a",
      expect.objectContaining({ method: "GET" }),
    )
  })

  it("uses a safe generated filename when Content-Disposition is missing", async () => {
    const requestFetch = vi.fn().mockResolvedValue(new Response(new Blob(["package"]), { status: 200 }))
    client.setConfig({ fetch: requestFetch })

    await expect(downloadSkillArtifact("code-review", "1.3.0")).resolves.toMatchObject({
      filename: "code-review-1.3.0.tar.gz",
    })
  })

  it("rejects unsuccessful responses", async () => {
    const requestFetch = vi.fn().mockResolvedValue(new Response("not found", { status: 404 }))
    client.setConfig({ fetch: requestFetch })

    await expect(downloadSkillArtifact("missing", "latest")).rejects.toThrow(
      "Failed to download skill package (404)",
    )
  })
})
