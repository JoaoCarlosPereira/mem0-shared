/**
 * task_08 (feature auth Google): wizard de onboarding de primeiro login.
 */
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Provider } from "react-redux";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

const mockReplace = jest.fn();
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: mockPush }),
}));

const mockUpdate = jest.fn().mockResolvedValue(null);
let mockSession: any = { firstLogin: true };
jest.mock("next-auth/react", () => ({
  useSession: () => ({
    data: mockSession,
    status: "authenticated",
    update: mockUpdate,
  }),
}));

import OnboardingPage from "@/app/onboarding/page";
import { store } from "@/store/store";
import { clearPersonProfile, setPersonProfile } from "@/store/profileSlice";

const GROUPS = { data: { groups: [{ id: "g1", name: "Equipe Fiscal", member_count: 2 }] } };
const NO_SUGGESTIONS = { data: { detected_hostname: null, unlinked_hostnames: [] } };

function mockGets(suggestions: any = NO_SUGGESTIONS) {
  mockedAxios.get.mockImplementation((url: string) => {
    if (url.includes("/admin/groups")) return Promise.resolve(GROUPS);
    if (url.includes("/machine-suggestions")) return Promise.resolve(suggestions);
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
  fireEvent.change(screen.getByLabelText(/grupo \/ equipe/i), {
    target: { value: name },
  });
}

async function fillAndSubmit(hostname = "S0281") {
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
    mockReplace.mockReset();
    mockPush.mockReset();
    mockUpdate.mockClear();
    mockSession = { firstLogin: true };
    store.dispatch(clearPersonProfile());
    mockGets();
  });

  it("lista os grupos existentes vindos de /admin/groups", async () => {
    renderPage();
    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining("/admin/groups"),
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
      );
      expect(mockUpdate).toHaveBeenCalledWith({ firstLogin: false });
      expect(assignSpy).toHaveBeenCalledWith("/");
    });
    // @ts-expect-error test shim
    window.location = originalLocation;
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
    fireEvent.change(screen.getByLabelText(/grupo \/ equipe/i), {
      target: { value: "__novo__" },
    });
    fireEvent.change(screen.getByLabelText(/nome do novo grupo/i), {
      target: { value: "Time Novo" },
    });
    await fillAndSubmit();

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/onboarding"),
        { hostname: "S0281", group_name: "Time Novo" },
      );
    });
  });

  it("409 exibe conflito terminal sem retry de vínculo", async () => {
    mockedAxios.post.mockRejectedValue({ response: { status: 409 } });
    renderPage();
    await fillAndSubmit();

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toMatch(/outra conta/i);
    });
    expect(
      screen.queryByRole("button", { name: /vincular máquina/i }),
    ).toBeNull();
    expect(mockUpdate).not.toHaveBeenCalled();
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
