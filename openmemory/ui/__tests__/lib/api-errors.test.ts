import { parseApiError } from "@/lib/api-errors";
import axios from "axios";

describe("parseApiError", () => {
  it("traduz 403 de deletion guard", () => {
    const err = new axios.AxiosError(
      "Forbidden",
      "403",
      undefined,
      undefined,
      {
        status: 403,
        data: {
          detail: "Memory deletion blocked (operation=delete). Set MEM0_ALLOW_MEMORY_DELETE=1",
        },
        statusText: "Forbidden",
        headers: {},
        config: {} as never,
      },
    );
    expect(parseApiError(err)).toContain("fail-closed");
  });
});
