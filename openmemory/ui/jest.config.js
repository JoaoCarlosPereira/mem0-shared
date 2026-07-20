// Timezone determinístico para os testes (date-fns formata em horário local).
process.env.TZ = "UTC";

const nextJest = require("next/jest");

const createJestConfig = nextJest({
  // Carrega next.config.js e .env no ambiente de teste
  dir: "./",
});

/** @type {import('jest').Config} */
const customJestConfig = {
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
  testEnvironment: "jest-environment-jsdom",
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
  },
  testPathIgnorePatterns: ["<rootDir>/node_modules/", "<rootDir>/.next/"],
  collectCoverageFrom: [
    "hooks/usePolling.ts",
    "store/adminSlice.ts",
    "store/queuesSlice.ts",
    "hooks/useAdminApi.ts",
    "hooks/useQueuesApi.ts",
    "hooks/useMetricsApi.ts",
    "store/metricsSlice.ts",
    "hooks/useSpecsApi.ts",
    "store/specsSlice.ts",
    "lib/specsBoard.ts",
    "components/admin/**/*.{ts,tsx}",
    "components/metrics/**/*.{ts,tsx}",
    "app/admin/**/*.{ts,tsx}",
  ],
};

module.exports = createJestConfig(customJestConfig);
