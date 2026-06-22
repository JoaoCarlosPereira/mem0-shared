import axios from "axios";

const UI_CLIENT = "openmemory-ui";

/** Tagged axios instance for new code. */
export const apiClient = axios.create({
  headers: { "x-client-name": UI_CLIENT },
});

// Existing hooks import bare `axios` — tag those requests too.
axios.interceptors.request.use((config) => {
  config.headers = config.headers ?? {};
  if (!config.headers["x-client-name"]) {
    config.headers["x-client-name"] = UI_CLIENT;
  }
  return config;
});
