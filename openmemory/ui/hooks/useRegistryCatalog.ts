"use client";

import { useCallback, useState } from "react";

import {
  fetchInstallRecipe,
  getRegistryResource,
  listAllRegistryResources,
  publishRegistryManifest,
  registryErrorMessage,
  type InstallRecipe,
  type InstallTarget,
  type RegistryApplyResponse,
  type RegistryResource,
  type RegistryResourceKind,
} from "@/lib/registry-client";

export interface UseRegistryCatalogState {
  resources: RegistryResource[];
  selectedResource: RegistryResource | null;
  applyResponse: RegistryApplyResponse | null;
  installRecipe: InstallRecipe | null;
  loading: boolean;
  detailLoading: boolean;
  publishing: boolean;
  installing: boolean;
  error: string | null;
  publishError: string | null;
  installError: string | null;
}

export function useRegistryCatalog() {
  const [state, setState] = useState<UseRegistryCatalogState>({
    resources: [],
    selectedResource: null,
    applyResponse: null,
    installRecipe: null,
    loading: false,
    detailLoading: false,
    publishing: false,
    installing: false,
    error: null,
    publishError: null,
    installError: null,
  });

  const loadCatalog = useCallback(async () => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const resources = await listAllRegistryResources();
      setState((current) => ({
        ...current,
        resources,
        loading: false,
        error: null,
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        loading: false,
        error: registryErrorMessage(error, "Falha ao carregar catálogo da Store."),
      }));
    }
  }, []);

  const loadDetail = useCallback(
    async (
      kind: RegistryResourceKind,
      name: string,
      tag?: string,
      namespace?: string,
    ) => {
      setState((current) => ({ ...current, detailLoading: true, error: null }));
      try {
        const selectedResource = await getRegistryResource(kind, name, tag, namespace);
        setState((current) => ({
          ...current,
          selectedResource,
          detailLoading: false,
          error: null,
        }));
        return selectedResource;
      } catch (error) {
        setState((current) => ({
          ...current,
          detailLoading: false,
          error: registryErrorMessage(error, "Falha ao carregar detalhe do recurso."),
        }));
        return null;
      }
    },
    [],
  );

  const publishManifest = useCallback(async (manifest: string) => {
    setState((current) => ({
      ...current,
      publishing: true,
      publishError: null,
      applyResponse: null,
    }));
    try {
      const applyResponse = await publishRegistryManifest(manifest);
      setState((current) => ({
        ...current,
        publishing: false,
        publishError: null,
        applyResponse,
      }));
      await loadCatalog();
      return applyResponse;
    } catch (error) {
      setState((current) => ({
        ...current,
        publishing: false,
        publishError: registryErrorMessage(error, "Falha ao publicar recurso."),
      }));
      return null;
    }
  }, [loadCatalog]);

  const requestInstallRecipe = useCallback(
    async (
      kind: RegistryResourceKind,
      name: string,
      tag: string,
      target: InstallTarget,
    ) => {
      setState((current) => ({
        ...current,
        installing: true,
        installError: null,
        installRecipe: null,
      }));
      try {
        const installRecipe = await fetchInstallRecipe({
          kind,
          name,
          tag,
          target,
        });
        setState((current) => ({
          ...current,
          installing: false,
          installError: null,
          installRecipe,
        }));
        return installRecipe;
      } catch (error) {
        setState((current) => ({
          ...current,
          installing: false,
          installError: registryErrorMessage(
            error,
            "Falha ao gerar receita de instalação.",
          ),
        }));
        return null;
      }
    },
    [],
  );

  return {
    ...state,
    loadCatalog,
    loadDetail,
    publishManifest,
    requestInstallRecipe,
  };
}
