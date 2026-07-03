/**
 * task_07 (feature auth Google): interceptor anexa Bearer preservando
 * o header x-client-name existente.
 */
import axios from "axios";

import { setApiAccessToken } from "@/lib/api-client";

function runRequestInterceptor(config: any) {
  const handlers = (axios.interceptors.request as any).handlers.filter(Boolean);
  return handlers.reduce(
    (cfg: any, handler: any) => handler.fulfilled(cfg),
    config,
  );
}

describe("api-client Bearer interceptor", () => {
  afterEach(() => setApiAccessToken(null));

  it("sem token: só x-client-name, sem Authorization", () => {
    setApiAccessToken(null);
    const cfg = runRequestInterceptor({ headers: {} });
    expect(cfg.headers["x-client-name"]).toBe("openmemory-ui");
    expect(cfg.headers["Authorization"]).toBeUndefined();
  });

  it("com token: anexa Bearer e preserva x-client-name", () => {
    setApiAccessToken("jwt-da-api");
    const cfg = runRequestInterceptor({ headers: {} });
    expect(cfg.headers).toEqual(
      expect.objectContaining({
        "x-client-name": "openmemory-ui",
        Authorization: "Bearer jwt-da-api",
      }),
    );
  });

  it("não sobrescreve Authorization explícito da chamada", () => {
    setApiAccessToken("jwt-da-api");
    const cfg = runRequestInterceptor({
      headers: { Authorization: "Bearer explicito" },
    });
    expect(cfg.headers["Authorization"]).toBe("Bearer explicito");
  });
});
