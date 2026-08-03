import { fireEvent, render, screen, waitFor } from "@testing-library/react";

jest.mock("@/lib/api-client", () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

jest.mock("@/hooks/useApiSessionReady", () => ({
  useApiSessionReady: () => true,
}));

import { apiClient } from "@/lib/api-client";
import StorePage from "@/app/store/page";
import type { RegistryResource } from "@/lib/registry-client";

const mockedApiClient = apiClient as jest.Mocked<typeof apiClient>;

const skill: RegistryResource = {
  registryKind: "skills",
  apiVersion: "agentregistry.dev/v1alpha1",
  kind: "Skill",
  metadata: {
    namespace: "default",
    name: "team/demo-skill",
    tag: "latest",
    labels: { team: "platform" },
  },
  spec: {
    title: "Demo Skill",
    description: "Automatiza tarefas repetitivas",
    source: {
      repository: {
        url: "https://github.com/acme/demo-skill",
      },
    },
  },
};

describe("StorePage", () => {
  beforeEach(() => {
    mockedApiClient.get.mockReset();
    mockedApiClient.post.mockReset();
    mockedApiClient.get.mockImplementation((url) => {
      if (String(url) === "/registry-api/v0/skills") {
        return Promise.resolve({ data: { items: [skill] } });
      }
      if (String(url).includes("/registry-api/v0/skills/team%2Fdemo-skill/latest")) {
        return Promise.resolve({ data: skill });
      }
      return Promise.resolve({ data: { items: [] } });
    });
    mockedApiClient.post.mockResolvedValue({
      data: {
        results: [{ kind: "Skill", name: "team/new-skill", tag: "latest", status: "created" }],
      },
    });
  });

  it("renderiza listagem autenticada e carrega detalhe", async () => {
    render(<StorePage />);

    expect(await screen.findByText("Demo Skill")).toBeInTheDocument();
    expect(screen.getByText("Automatiza tarefas repetitivas")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Buscar na Store"), {
      target: { value: "platform" },
    });
    expect(screen.getByText("Demo Skill")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Demo Skill").closest("button") as HTMLButtonElement);

    await waitFor(() => {
      expect(mockedApiClient.get).toHaveBeenCalledWith(
        "/registry-api/v0/skills/team%2Fdemo-skill/latest",
        { params: { namespace: "default" } },
      );
    });
    expect(await screen.findByText(/Repositório: https:\/\/github.com\/acme\/demo-skill/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Gerar receita de instalação/i }),
    ).toBeEnabled();

    mockedApiClient.post.mockResolvedValueOnce({
      data: {
        version: "1",
        resource_kind: "skill",
        name: "team/demo-skill",
        tag: "latest",
        target: "cursor",
        steps: [{ id: "copy-resource", type: "copy", to: ".cursor/skills/team/demo-skill" }],
      },
    });
    fireEvent.click(screen.getByRole("button", { name: /Gerar receita de instalação/i }));
    await waitFor(() => {
      expect(mockedApiClient.post).toHaveBeenCalledWith(
        "/api-proxy/api/v1/store/install-recipes",
        {
          kind: "skill",
          name: "team/demo-skill",
          tag: "latest",
          target: "cursor",
        },
      );
    });
    expect(await screen.findByText(/Receita cursor/i)).toBeInTheDocument();
  });

  it("publica manifesto via proxy de registry", async () => {
    render(<StorePage />);
    await screen.findByText("Demo Skill");

    fireEvent.change(screen.getByLabelText("Nome do recurso"), {
      target: { value: "team/new-skill" },
    });
    fireEvent.change(screen.getByLabelText("Título"), {
      target: { value: "New Skill" },
    });
    fireEvent.change(screen.getByLabelText("Repositório de origem"), {
      target: { value: "https://github.com/acme/new-skill" },
    });

    fireEvent.click(screen.getByRole("button", { name: /Publicar via \/v0\/apply/i }));

    await waitFor(() => {
      expect(mockedApiClient.post).toHaveBeenCalledWith(
        "/registry-api/v0/apply",
        expect.stringContaining('name: "team/new-skill"'),
        { headers: { "content-type": "application/yaml" } },
      );
    });
    expect(await screen.findByText(/Skill team\/new-skill@latest: created/)).toBeInTheDocument();
  });
});
