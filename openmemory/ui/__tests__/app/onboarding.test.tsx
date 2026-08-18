/**
 * task_08 (feature auth Google): wizard de onboarding de primeiro login.
 */
import React from "react";
import { fireEvent, render, screen, waitFor, act } from "@testing-library/react";
import { Provider } from "react-redux";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

const mockReplace = jest.fn();
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: mockPush }),
  usePathname: () => "/onboarding",
}));

const mockUpdate = jest.fn().mockResolvedValue(null);
const mockSignOut = jest.fn();
let mockSession: any = { firstLogin: true };
let mockStatus = "authenticated";

jest.mock("next-auth/react", () => ({
  useSession: () => ({
    data: mockSession,
    status: mockStatus,
    update: mockUpdate,
  }),
  signOut: (...args: any[]) => mockSignOut(...args),
}));

import OnboardingPage from "@/app/onboarding/page";
import { store } from "@/store/store";
import { clearPersonProfile, setPersonProfile, setApiSessionStatus } from "@/store/profileSlice";

const GROUPS = { data: { groups: [{ id: "g1", name: "Equipe Fiscal", member_count: 2 }] } };
const NO_SUGGESTIONS = { data: { detected_hostname: null, unlinked_hostnames: [] } };

function mockGets(suggestions: any = NO_SUGGESTIONS, groups: any = GROUPS) {
  mockedAxios.get.mockImplementation((url: string) => {
    if (url.includes("/admin/groups")) {
      if (groups instanceof Error) return Promise.reject(groups);
      return Promise.resolve(groups);
    }
    if (url.includes("/machine-suggestions")) {
      if (suggestions instanceof Error) return Promise.reject(suggestions);
      return Promise.resolve(suggestions);
    }
    if (url.includes("/api/v1/auth/me")) {
      return Promise.resolve({
        data: {
          user: { email: "test@example.com" },
          machine: { hostname: "S0281" },
        },
      });
    }
    return Promise.reject(new Error(`GET inesperado: ${url}`));
  });
}

function renderPage() {
  return render(
    <Provider store={store}>
      <OnboardingPage />
    </Provider>,
  );
}

async function selectGroup(name = "Equipe Fiscal") {
  await waitFor(() => {
    expect(screen.getByRole("option", { name })).toBeInTheDocument();
  });
  fireEvent.change(screen.getByLabelText(/grupo \/ equipe/i), {
    target: { value: name },
  });
}

async function fillAndSubmit(hostname = "S0281") {
  await waitFor(() => {
    expect(screen.getByRole("option", { name: "Equipe Fiscal" })).toBeInTheDocument();
  });
  fireEvent.change(screen.getByLabelText(/nome da máquina/i), {
    target: { value: hostname },
  });
  await selectGroup();
  fireEvent.click(
    screen.getByRole("button", { name: /vincular máquina e continuar/i }),
  );
}

describe("OnboardingPage", () => {
  beforeEach(() => {
    mockedAxios.get.mockReset();
    mockedAxios.post.mockReset();
    mockedAxios.isAxiosError = ((err: any) => err?.isAxiosError || !!err?.response) as any;
    mockedAxios.isCancel = ((err: any) => err?.__CANCEL__) as any;
    mockReplace.mockReset();
    mockPush.mockReset();
    mockSignOut.mockReset();
    mockUpdate.mockClear();
    mockSession = { firstLogin: true };
    mockStatus = "authenticated";
    store.dispatch(clearPersonProfile());
    store.dispatch(setApiSessionStatus("valid"));
    mockGets();
  });

  it("aguarda apiSessionStatus === valid antes de carregar grupos e sugestões (UI-1)", async () => {
    store.dispatch(setApiSessionStatus("idle"));
    renderPage();

    expect(screen.getByText(/preparando ambiente de primeiro acesso/i)).toBeInTheDocument();
    expect(mockedAxios.get).not.toHaveBeenCalled();

    act(() => {
      store.dispatch(setApiSessionStatus("valid"));
    });

    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith(expect.stringContaining("/admin/groups"), expect.anything());
    });
  });

  it("lista os grupos existentes vindos de /admin/groups", async () => {
    renderPage();
    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining("/admin/groups"),
        expect.anything(),
      );
      expect(screen.getByRole("option", { name: "Equipe Fiscal" })).toBeInTheDocument();
    });
  });

  it("submissão com legado redireciona ao painel de instalação", async () => {
    mockedAxios.post.mockResolvedValue({
      data: {
        linked: true,
        hostname: "S0281",
        group: "Equipe Fiscal",
        memories_count: 42,
        legacy_user_linked: true,
      },
    });
    const assignSpy = jest.fn();
    const originalLocation = window.location;
    // jsdom: location.assign é read-only — substituímos o objeto inteiro.
    // @ts-expect-error test shim
    delete window.location;
    // @ts-expect-error test shim
    window.location = { ...originalLocation, assign: assignSpy };
    renderPage();
    await fillAndSubmit();

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/onboarding"),
        { hostname: "S0281", group_name: "Equipe Fiscal" },
        expect.anything(),
      );
      expect(mockUpdate).toHaveBeenCalledWith({ firstLogin: false });
      expect(assignSpy).toHaveBeenCalledWith("/");
    });
    // @ts-expect-error test shim
    window.location = originalLocation;
  });

  it("recuperação com fallback em BE-5 quando update da sessão falha persistentemente", async () => {
    mockedAxios.post.mockResolvedValue({
      data: {
        linked: true,
        hostname: "S0281",
        group: "Equipe Fiscal",
        memories_count: 42,
        legacy_user_linked: true,
      },
    });
    mockUpdate.mockRejectedValue(new Error("Update failed"));

    renderPage();
    await fillAndSubmit();

    await waitFor(() => {
      expect(screen.getByText(/vinculada com sucesso no servidor/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /continuar para o painel/i })).toBeInTheDocument();
    });
  });

  it("confirmação de hostname divergente (BE-4) antes do submit", async () => {
    mockGets({
      data: {
        detected_hostname: "S0281",
        unlinked_hostnames: ["S0281"],
      },
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/nome da máquina/i)).toHaveValue("S0281");
    });

    // Usuário altera o hostname para S0299
    fireEvent.change(screen.getByLabelText(/nome da máquina/i), {
      target: { value: "S0299" },
    });
    await selectGroup();

    fireEvent.click(screen.getByRole("button", { name: /vincular máquina e continuar/i }));

    // Deve exibir caixa de confirmação de divergência
    await waitFor(() => {
      expect(screen.getByTestId("mismatch-confirm-box")).toBeInTheDocument();
      expect(screen.getByText(/Detectamos S0281 na sua rede, mas você informou S0299/i)).toBeInTheDocument();
    });

    expect(mockedAxios.post).not.toHaveBeenCalled();

    // Clicando em continuar prossegue
    mockedAxios.post.mockResolvedValue({
      data: { linked: true, hostname: "S0299", group: "Equipe Fiscal", memories_count: 0, legacy_user_linked: false },
    });

    fireEvent.click(screen.getByRole("button", { name: /^Continuar$/ }));

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/onboarding"),
        { hostname: "S0299", group_name: "Equipe Fiscal" },
        expect.anything(),
      );
    });
  });

  it("grupo novo dispara o POST com o nome digitado", async () => {
    mockedAxios.post.mockResolvedValue({
      data: {
        linked: true,
        hostname: "S0281",
        group: "Time Novo",
        memories_count: 0,
        legacy_user_linked: false,
      },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("option", { name: "Equipe Fiscal" })).toBeInTheDocument();
    });
    fireEvent.change(screen.getByLabelText(/grupo \/ equipe/i), {
      target: { value: "__novo__" },
    });
    fireEvent.change(screen.getByLabelText(/nome do novo grupo/i), {
      target: { value: "Time Novo" },
    });
    fireEvent.change(screen.getByLabelText(/nome da máquina/i), {
      target: { value: "S0281" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /vincular máquina e continuar/i }),
    );

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/onboarding"),
        { hostname: "S0281", group_name: "Time Novo" },
        expect.anything(),
      );
    });
  });

  it("409 exibe tela de conflito sem loop com opções de voltar ou logout (UI-3)", async () => {
    mockedAxios.post.mockRejectedValue({
      isAxiosError: true,
      response: { status: 409 },
    });
    renderPage();
    await fillAndSubmit();

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toMatch(/outra conta/i);
    });
    expect(screen.queryByRole("button", { name: /ir para o painel/i })).toBeNull();

    // Opções disponíveis
    expect(screen.getByRole("button", { name: /voltar e informar outra máquina/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sair e entrar com outra conta/i })).toBeInTheDocument();

    // Clicando em sair
    fireEvent.click(screen.getByRole("button", { name: /sair e entrar com outra conta/i }));
    expect(mockSignOut).toHaveBeenCalledWith({ callbackUrl: "/login" });
  });

  it("classificação de erro 401 para relogin (UI-5)", async () => {
    mockedAxios.post.mockRejectedValue({
      isAxiosError: true,
      response: { status: 401 },
    });
    renderPage();
    await fillAndSubmit();

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toMatch(/sessão expirou/i);
      expect(screen.getByRole("button", { name: /fazer login novamente/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /fazer login novamente/i }));
    expect(mockSignOut).toHaveBeenCalledWith({ callbackUrl: "/login?error=SessionExpired" });
  });

  it("classificação de erro 500 com botão de tentar novamente (UI-5)", async () => {
    mockedAxios.post.mockRejectedValue({
      isAxiosError: true,
      response: { status: 500, data: { detail: "Erro interno" } },
    });
    renderPage();
    await fillAndSubmit();

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toMatch(/Erro interno/i);
      expect(screen.getByRole("button", { name: /tentar novamente/i })).toBeInTheDocument();
    });
  });

  it("feedback explícito de erro no carregamento de grupos com botão de tentar novamente (UI-4)", async () => {
    const groupError = new Error("Network Error");
    (groupError as any).isAxiosError = true;
    mockGets(NO_SUGGESTIONS, groupError);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Lista de equipes indisponível/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /tentar novamente/i })).toBeInTheDocument();
    });
  });

  it("feedback explícito de grupos vazios (UI-4)", async () => {
    mockGets(NO_SUGGESTIONS, { data: { groups: [] } });

    renderPage();

    await waitFor(() => {
      expect(screen.getByRole("option", { name: /Nenhuma equipe cadastrada/i })).toBeInTheDocument();
    });
  });

  it("sem grupo selecionado o botão de envio fica desabilitado", async () => {
    renderPage();
    fireEvent.change(screen.getByLabelText(/nome da máquina/i), {
      target: { value: "S0281" },
    });
    expect(
      screen.getByRole("button", { name: /vincular máquina e continuar/i }),
    ).toBeDisabled();
  });

  it("grupo sugerido pelo legado é pré-selecionado", async () => {
    mockGets({
      data: {
        detected_hostname: "S0293",
        unlinked_hostnames: [],
        suggested_group: "Equipe Fiscal",
      },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/grupo \/ equipe/i)).toHaveValue("Equipe Fiscal");
    });
  });

  it("hostname inválido bloqueia envio e exibe erro", async () => {
    renderPage();
    fireEvent.change(screen.getByLabelText(/nome da máquina/i), {
      target: { value: "S0281 - Ana Paula" },
    });
    fireEvent.blur(screen.getByLabelText(/nome da máquina/i));

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toMatch(/S \+ 4 dígitos/i);
    });
    expect(
      screen.getByRole("button", { name: /vincular máquina e continuar/i }),
    ).toBeDisabled();
    expect(mockedAxios.post).not.toHaveBeenCalled();
  });

  it("máquina detectada pela rede pré-preenche o campo com aviso", async () => {
    mockGets({
      data: { detected_hostname: "S0293", unlinked_hostnames: ["S0293", "S0300"] },
    });
    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/nome da máquina/i)).toHaveValue("S0293");
      expect(screen.getByTestId("detected-hint").textContent).toMatch(/S0293/);
    });
    // Autocomplete com as máquinas legadas sem dono.
    const datalist = document.getElementById("known-machines");
    expect(datalist?.querySelectorAll("option")).toHaveLength(2);
  });

  it("sem detecção o campo fica vazio e editável", async () => {
    renderPage();
    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining("/machine-suggestions"),
        expect.anything(),
      );
    });
    expect(screen.getByLabelText(/nome da máquina/i)).toHaveValue("");
  });

  it("usuário já vinculado (sem first_login) é redirecionado ao painel", async () => {
    mockSession = { firstLogin: false };
    store.dispatch(
      setPersonProfile({
        email: "a@b.c",
        displayName: "A",
        avatarUrl: null,
        machineHostname: "S0281",
        group: "Default",
      }),
    );
    renderPage();
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/");
    });
  });
});
