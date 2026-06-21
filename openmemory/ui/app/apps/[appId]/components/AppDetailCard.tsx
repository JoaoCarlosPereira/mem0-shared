import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { PauseIcon, Loader2, PlayIcon } from "lucide-react";
import { useAppsApi } from "@/hooks/useAppsApi";
import Image from "next/image";
import { useDispatch, useSelector } from "react-redux";
import { setAppDetails } from "@/store/appsSlice";
import { BiEdit } from "react-icons/bi";
import { constants } from "@/components/shared/source-app";
import { RootState } from "@/store/store";
import { appStatusLabel, formatDateTime } from "@/lib/i18n/pt-BR";

const capitalize = (str: string) => {
  return str.charAt(0).toUpperCase() + str.slice(1);
};

const AppDetailCard = ({
  appId,
  selectedApp,
}: {
  appId: string;
  selectedApp: any;
}) => {
  const { updateAppDetails } = useAppsApi();
  const [isLoading, setIsLoading] = useState(false);
  const dispatch = useDispatch();
  const apps = useSelector((state: RootState) => state.apps.apps);
  const currentApp = apps.find((app: any) => app.id === appId);
  const appConfig = currentApp
    ? constants[currentApp.name as keyof typeof constants] || constants.default
    : constants.default;
  const displayName = currentApp
    ? constants[currentApp.name as keyof typeof constants]?.name ?? currentApp.name
    : appConfig.name;

  const handlePauseAccess = async () => {
    setIsLoading(true);
    try {
      await updateAppDetails(appId, {
        is_active: !selectedApp.details.is_active,
      });
      dispatch(
        setAppDetails({ appId, isActive: !selectedApp.details.is_active })
      );
    } catch (error) {
      console.error("Failed to toggle app pause state:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const buttonText = selectedApp.details.is_active
    ? "Pausar Acesso"
    : "Retomar Acesso";

  return (
    <div>
      <div className="bg-zinc-900 border w-[320px] border-zinc-800 rounded-xl mb-6">
        <div className="flex items-center gap-2 mb-4 bg-zinc-800 rounded-t-xl p-3">
          <div className="w-5 h-5 flex items-center justify-center">
            {appConfig.iconImage ? (
              <div>
                <div className="w-6 h-6 rounded-full bg-zinc-700 flex items-center justify-center overflow-hidden">
                  <Image
                    src={appConfig.iconImage}
                    alt={appConfig.name}
                    width={40}
                    height={40}
                  />
                </div>
              </div>
            ) : (
              <div className="w-5 h-5 flex items-center justify-center bg-zinc-700 rounded-full">
                <BiEdit className="w-4 h-4 text-zinc-400" />
              </div>
            )}
          </div>
          <h2 className="text-md font-semibold">{displayName}</h2>
        </div>

        <div className="space-y-4 p-3">
          <div>
            <p className="text-xs text-zinc-400">Status de Acesso</p>
            <p
              className={`font-medium ${
                selectedApp.details.is_active
                  ? "text-emerald-500"
                  : "text-red-500"
              }`}
            >
              {capitalize(
                appStatusLabel(selectedApp.details.is_active).toLowerCase()
              )}
            </p>
          </div>

          <div>
            <p className="text-xs text-zinc-400">Total de Memórias Criadas</p>
            <p className="font-medium">
              {selectedApp.details.total_memories_created} Memórias
            </p>
          </div>

          <div>
            <p className="text-xs text-zinc-400">Total de Memórias Acessadas</p>
            <p className="font-medium">
              {selectedApp.details.total_memories_accessed} Memórias
            </p>
          </div>

          <div>
            <p className="text-xs text-zinc-400">Primeiro Acesso</p>
            <p className="font-medium">
              {selectedApp.details.first_accessed
                ? new Date(
                    selectedApp.details.first_accessed
                  ).toLocaleDateString("pt-BR", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                    hour: "numeric",
                    minute: "numeric",
                  })
                : "Nunca"}
            </p>
          </div>

          <div>
            <p className="text-xs text-zinc-400">Último Acesso</p>
            <p className="font-medium">
              {selectedApp.details.last_accessed
                ? new Date(
                    selectedApp.details.last_accessed
                  ).toLocaleDateString("pt-BR", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                    hour: "numeric",
                    minute: "numeric",
                  })
                : "Nunca"}
            </p>
          </div>

          <hr className="border-zinc-800" />

          <div className="flex gap-2 justify-end">
            <Button
              onClick={handlePauseAccess}
              className="flex bg-transparent w-[170px] bg-zinc-800 border-zinc-800 hover:bg-zinc-800 text-white"
              size="sm"
              disabled={isLoading}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : buttonText === "Pausar Acesso" ? (
                <PauseIcon className="h-4 w-4" />
              ) : (
                <PlayIcon className="h-4 w-4" />
              )}
              {buttonText}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AppDetailCard;
