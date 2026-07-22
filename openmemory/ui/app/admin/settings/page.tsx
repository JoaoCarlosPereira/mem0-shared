"use client";

import { useState, useEffect } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { SaveIcon, RotateCcw, Settings } from "lucide-react"
import { FormView } from "@/components/form-view"
import { JsonEditor } from "@/components/json-editor"
import { useConfig } from "@/hooks/useConfig"
import { useSelector } from "react-redux"
import { RootState } from "@/store/store"
import { useToast } from "@/components/ui/use-toast"
import { PageHeader } from "@/components/shared/PageHeader"
import { APP_NAME } from "@/lib/branding"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"

export default function SettingsPage() {
  const { toast } = useToast()
  const configState = useSelector((state: RootState) => state.config)
  const [settings, setSettings] = useState({
    openmemory: configState.openmemory || {
      custom_instructions: null,
      multilingual: true,
    },
    mem0: configState.mem0
  })
  const [viewMode, setViewMode] = useState<"form" | "json">("form")
  const { fetchConfig, saveConfig, resetConfig, isLoading, error } = useConfig()

  useEffect(() => {
    const loadConfig = async () => {
      try {
        await fetchConfig()
      } catch (error) {
        toast({
          title: "Erro",
          description: "Falha ao carregar configuração",
          variant: "destructive",
        })
      }
    }
    
    loadConfig()
  }, [])

  useEffect(() => {
    setSettings(prev => ({
      ...prev,
      openmemory: configState.openmemory || { custom_instructions: null, multilingual: true },
      mem0: configState.mem0
    }))
  }, [configState.openmemory, configState.mem0])

  const handleSave = async () => {
    try {
      await saveConfig({
        openmemory: settings.openmemory,
        mem0: settings.mem0,
      })
      await fetchConfig()
      toast({
        title: "Configurações salvas",
        description: "Sua configuração foi atualizada com sucesso.",
      })
    } catch (error: any) {
      const detail =
        error?.response?.data?.detail ||
        error?.message ||
        "Falha ao salvar configuração"
      toast({
        title: "Erro",
        description: typeof detail === "string" ? detail : "Falha ao salvar configuração",
        variant: "destructive",
      })
    }
  }

  const handleReset = async () => {
    try {
      await resetConfig()
      toast({
        title: "Configurações redefinidas",
        description: "A configuração foi restaurada para os valores padrão.",
      })
      await fetchConfig()
    } catch (error) {
      toast({
        title: "Erro",
        description: "Falha ao redefinir configuração",
        variant: "destructive",
      })
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="animate-fade-slide-down">
          <PageHeader
            size="large"
            icon={Settings}
            title="Configurações"
            description={`Gerencie sua configuração do ${APP_NAME} e do Mem0`}
          />
        </div>
        <div className="flex flex-wrap gap-2">
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" className="border-zinc-800 text-zinc-200 hover:bg-zinc-700 hover:text-zinc-50 animate-fade-slide-down" disabled={isLoading}>
                  <RotateCcw className="mr-2 h-4 w-4" />
                  Restaurar padrões
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Redefinir configuração?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Isso irá redefinir todas as configurações para os padrões do sistema.
                    Qualquer configuração personalizada será perdida. As chaves de API
                    serão definidas para usar variáveis de ambiente.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancelar</AlertDialogCancel>
                  <AlertDialogAction onClick={handleReset} className="bg-red-600 hover:bg-red-700">
                    Redefinir
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            
            <Button onClick={handleSave} className="bg-primary hover:bg-primary/90 animate-fade-slide-down" disabled={isLoading}>
              <SaveIcon className="mr-2 h-4 w-4" />
              {isLoading ? "Salvando..." : "Salvar configuração"}
            </Button>
        </div>
      </div>

      <Tabs value={viewMode} onValueChange={(value) => setViewMode(value as "form" | "json")} className="w-full animate-fade-slide-down delay-1">
          <TabsList className="grid w-full grid-cols-2 mb-8">
            <TabsTrigger value="form">Formulário</TabsTrigger>
            <TabsTrigger value="json">Editor JSON</TabsTrigger>
          </TabsList>

          <TabsContent value="form">
            <FormView settings={settings} onChange={setSettings} />
          </TabsContent>

          <TabsContent value="json">
            <Card>
              <CardHeader>
                <CardTitle>Configuração JSON</CardTitle>
                <CardDescription>Edite toda a configuração diretamente em JSON</CardDescription>
              </CardHeader>
              <CardContent>
                <JsonEditor value={settings} onChange={setSettings} />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
    </div>
  )
}
