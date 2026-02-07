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




export default function Home() {
  const { selectedNodeId, clearSelection, isLoading } = useStore(); // Added isLoading

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
        {selectedNodeId ? (
          <ResizablePanelGroup orientation="vertical">
            {/* Header / Toolbar - Fixed within the panel or part of the layout? 
                Better to put Header OUTSIDE the resizable group so it stays fixed at top 
            */}

            {/* Graph View (Top) */}
            <ResizablePanel defaultSize={65} minSize={30}>
              {/* Header / Toolbar - We can put it here or outside. 
                     If inside, it shrinks with the panel. 
                     Let's put it OUTSIDE the Group to keep it stable? 
                     Actually, let's keep it simple. Put it inside the top panel for now 
                     OR wrapping the group? 
                     
                     Wait, structure: 
                     [Header] (Fixed height)
                     [ResizableGroup] (Flex-1)
                        [Panel: Graph]
                        [Handle]
                        [Panel: Detail]
                  */}
              <div className="flex flex-col h-full">
                <div className="h-14 border-b flex items-center px-4 bg-background shrink-0 gap-4">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="gap-2 text-muted-foreground hover:text-foreground"
                    onClick={clearSelection}
                  >
                    <HomeIcon className="h-4 w-4" />
                    Back to Dashboard
                  </Button>
                  <div className="h-4 w-px bg-border" />
                  <span className="font-medium text-sm">
                    Graph View
                  </span>
                </div>
                <div className="flex-1 min-h-0 relative">
                  <GraphView />
                </div>
              </div>
            </ResizablePanel>

            <ResizableHandle withHandle />

            {/* Detail View (Bottom) */}
            <ResizablePanel defaultSize={35} minSize={20}>
              <DetailPanel />
            </ResizablePanel>
          </ResizablePanelGroup>
        ) : (
          <div className="flex-1 w-full h-full overflow-auto">
            <Dashboard />
          </div>
        )}
      </div>
    </main>
  );
}
