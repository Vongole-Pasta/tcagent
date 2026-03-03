"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { GraphView } from "@/components/graph/GraphView";
import { DetailPanel } from "@/components/detail/DetailPanel";
import { Dashboard } from "@/components/dashboard/Dashboard";
import { useStore } from "@/store/useStore";
import { Button } from "@/components/ui/button";
import { HomeIcon } from "lucide-react";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { LoadingOverlay } from "@/components/ui/loading-overlay";
import { SuccessDialog } from "@/components/ui/success-dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { HappyCaseTableView } from "@/components/agent/HappyCaseTableView";
import { LoadingProgress } from "@/components/agent/LoadingProgress";
import { IntegrationScenarioView } from "@/components/agent/IntegrationScenarioView";
import { Card } from "@/components/ui/card";
import { Activity, LayoutDashboard, Share2, TestTube } from "lucide-react";




export default function Home() {
  const { 
    selectedNodeId, 
    clearSelection, 
    isLoading, 
    viewMode, 
    setViewMode,
    happyCaseScenarios,
    integrationScenarios,
    isAgentRunning
  } = useStore();

  return (
    <main className="h-screen w-screen overflow-hidden flex bg-background text-foreground relative">
      {isLoading && <LoadingOverlay />}
      <SuccessDialog />

      {/* Left Sidebar - Fixed Width */}
      <aside className="w-[300px] flex-shrink-0 border-r bg-muted/10 h-full overflow-hidden">
        <Sidebar />
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col h-full relative min-w-0">
        <Tabs 
          value={viewMode} 
          onValueChange={(v) => setViewMode(v as any)} 
          className="flex-1 flex flex-col h-full"
        >
          <div className="h-14 border-b flex items-center px-4 bg-background shrink-0 justify-between">
            <TabsList className="bg-muted/50">
              <TabsTrigger value="dashboard" className="gap-2">
                <LayoutDashboard className="h-4 w-4" />
                Overview
              </TabsTrigger>
              <TabsTrigger value="graph" className="gap-2">
                <Share2 className="h-4 w-4" />
                Visualization
              </TabsTrigger>
              <TabsTrigger value="results" className="gap-2">
                <TestTube className="h-4 w-4" />
                Test Results
              </TabsTrigger>
            </TabsList>

            {viewMode === 'graph' && selectedNodeId && (
              <Button
                variant="ghost"
                size="sm"
                className="gap-2 text-muted-foreground hover:text-foreground"
                onClick={clearSelection}
              >
                <HomeIcon className="h-4 w-4" />
                Reset Graph
              </Button>
            )}
          </div>

          <TabsContent value="dashboard" className="flex-1 m-0 overflow-auto">
            <Dashboard />
          </TabsContent>

          <TabsContent value="graph" className="flex-1 m-0 overflow-hidden">
            {selectedNodeId ? (
              <ResizablePanelGroup orientation="vertical">
                <ResizablePanel defaultSize={65} minSize={30}>
                  <div className="flex flex-col h-full">
                    <div className="flex-1 min-h-0 relative">
                      <GraphView />
                    </div>
                  </div>
                </ResizablePanel>
                <ResizableHandle withHandle />
                <ResizablePanel defaultSize={35} minSize={20}>
                  <DetailPanel />
                </ResizablePanel>
              </ResizablePanelGroup>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-10 text-center space-y-4">
                <div className="bg-muted p-6 rounded-full">
                  <Share2 className="h-10 w-10 text-muted-foreground" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-xl font-semibold">선택된 노드가 없습니다</h3>
                  <p className="text-muted-foreground max-w-sm">
                    왼쪽 사이드바에서 메서드나 엔드포인트를 선택하여 호출 관계를 시각화해 보세요.
                  </p>
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="results" className="flex-1 m-0 overflow-auto">
            <div className="p-8 h-full bg-slate-50">
                <div className="max-w-5xl mx-auto space-y-8">
                    <div className="space-y-1">
                        <h2 className="text-2xl font-bold tracking-tight">Test Results</h2>
                        <p className="text-muted-foreground">생성된 테스트 시나리오 및 케이스 목록입니다.</p>
                    </div>

                    {isAgentRunning && happyCaseScenarios.length === 0 && integrationScenarios.length === 0 ? (
                        <Card className="border-2 border-primary/20 shadow-xl overflow-hidden bg-white/50 backdrop-blur-sm">
                            <LoadingProgress />
                        </Card>
                    ) : (happyCaseScenarios.length > 0 || integrationScenarios.length > 0) ? (
                        <div className="space-y-8">
                            {happyCaseScenarios.length > 0 && (
                                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                                    <HappyCaseTableView />
                                </div>
                            )}

                            {integrationScenarios.length > 0 && (
                                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                                    <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                                        <Activity className="h-5 w-5 text-blue-500" />
                                        Integration Scenarios
                                    </h3>
                                    <Card className="border-2 border-primary/20 shadow-lg overflow-hidden">
                                        <IntegrationScenarioView />
                                    </Card>
                                </div>
                            )}
                        </div>
                    ) : (
                        <Card className="items-center justify-center flex flex-col p-20 border-dashed border-2 bg-slate-50/50">
                            <div className="bg-muted p-4 rounded-full mb-4">
                                <TestTube className="h-8 w-8 text-muted-foreground" />
                            </div>
                            <h3 className="text-xl font-semibold mb-2">생성된 결과가 없습니다</h3>
                            <p className="text-muted-foreground text-center max-w-md">
                                왼쪽 사이드바에서 메서드를 선택한 후 <strong>Happy Case 생성</strong> 버튼을 클릭하여 테스트 데이터를 생성해 보세요.
                            </p>
                        </Card>
                    )}
                </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </main>
  );
}
