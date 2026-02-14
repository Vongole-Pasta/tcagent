import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Node, Edge } from '@xyflow/react';
import { GeneratedScenario } from '@/components/test/TestResultsView';

interface MethodNode {
    id: string;
    name: string;
    signature?: string;
    endpoint?: string;
    http_method?: string;
    type: 'METHOD' | 'ENDPOINT';
    status?: string | null;
    className?: string;
}

interface GraphData {
    nodes: Node[];
    edges: Edge[];
}

interface AppState {
    // Data
    projectNodes: MethodNode[];
    graphData: GraphData;
    selectedNodeId: string | null;
    selectedNodeDetail: { name: string; signature: string; source: string } | null;
    isLoading: boolean;
    isGraphLoading: boolean;
    error: string | null;

    // Test Results (Persisted)
    generatedScenarios: GeneratedScenario[];
    strategySummary: string | null;
    setGeneratedTestResults: (scenarios: GeneratedScenario[], summary: string | null) => void;
    updateScenario: (index: number, field: keyof GeneratedScenario, value: string | number) => void;

    // Actions
    fetchProjectNodes: (projectId?: string) => Promise<void>;
    fetchUpstreamGraph: (nodeId: string) => Promise<void>;
    fetchDownstreamGraph: (nodeId: string) => Promise<void>;
    fetchNodeDetail: (nodeId: string) => Promise<void>;
    uploadFiles: (files: File[]) => Promise<void>;
    clearSelection: () => void;

    projects: string[];
    selectedProject: string | null;
    fetchProjects: () => Promise<void>;
    selectProject: (projectId: string | null) => void;

    uploadSuccess: boolean;
    setUploadSuccess: (v: boolean) => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const useStore = create<AppState>()(
    persist(
        (set, get) => ({
            projectNodes: [],
            graphData: { nodes: [], edges: [] },
            selectedNodeId: null,
            selectedNodeDetail: null,
            isLoading: false,
            isGraphLoading: false,
            error: null,

            // Test Results
            generatedScenarios: [],
            strategySummary: null,
            setGeneratedTestResults: (scenarios, summary) => set({ generatedScenarios: scenarios, strategySummary: summary }),
            updateScenario: (index, field, value) => set((state) => {
                const newScenarios = [...state.generatedScenarios];
                newScenarios[index] = { ...newScenarios[index], [field]: value };
                return { generatedScenarios: newScenarios };
            }),

            // Project Management
            projects: [],
            selectedProject: null,

            fetchProjects: async () => {
                try {
                    const res = await fetch(`${API_BASE}/projects`);
                    if (res.ok) {
                        const data = await res.json();
                        set({ projects: data.projects });
                    }
                } catch (err) {
                    console.error(err);
                }
            },

            selectProject: (projectId) => {
                set({ selectedProject: projectId });
                if (projectId) {
                    get().fetchProjectNodes(projectId);
                } else {
                    set({ projectNodes: [] });
                }
            },

            fetchProjectNodes: async (projectId = 'default') => {
                set({ isLoading: true, error: null });
                try {
                    const res = await fetch(`${API_BASE}/projects/${projectId}/nodes`);
                    if (!res.ok) throw new Error('Failed to fetch nodes');
                    const data = await res.json();
                    set({ projectNodes: data.nodes });
                } catch (err: any) {
                    set({ error: err.message });
                } finally {
                    set({ isLoading: false });
                }
            },

            fetchUpstreamGraph: async (nodeId) => {
                set({ isGraphLoading: true, error: null, selectedNodeId: nodeId });
                try {
                    const res = await fetch(`${API_BASE}/graph/upstream/${nodeId}`);
                    if (!res.ok) throw new Error('Failed to fetch upstream graph');
                    const data = await res.json();
                    set({ graphData: data });
                    await get().fetchNodeDetail(nodeId);
                } catch (err: any) {
                    set({ error: err.message });
                } finally {
                    set({ isGraphLoading: false });
                }
            },

            fetchDownstreamGraph: async (nodeId) => {
                set({ isGraphLoading: true, error: null, selectedNodeId: nodeId });
                try {
                    const res = await fetch(`${API_BASE}/graph/downstream/${nodeId}`);
                    if (!res.ok) throw new Error('Failed to fetch downstream graph');
                    const data = await res.json();
                    set({ graphData: data });
                    await get().fetchNodeDetail(nodeId);
                } catch (err: any) {
                    set({ error: err.message });
                } finally {
                    set({ isGraphLoading: false });
                }
            },

            fetchNodeDetail: async (nodeId) => {
                try {
                    const res = await fetch(`${API_BASE}/graph/node/${nodeId}`);
                    if (res.ok) {
                        const data = await res.json();
                        set({ selectedNodeDetail: data });
                    }
                } catch (err) {
                    console.error(err);
                }
            },

            uploadFiles: async (files) => {
                set({ isLoading: true, error: null, uploadSuccess: false });
                try {
                    const formData = new FormData();
                    files.forEach(f => formData.append('files', f));

                    const currentProject = get().selectedProject;
                    if (currentProject) {
                        formData.append('project', currentProject);
                    }

                    const res = await fetch(`${API_BASE}/upload`, {
                        method: 'POST',
                        body: formData,
                    });

                    if (!res.ok) throw new Error('Upload failed');

                    await get().fetchProjectNodes(currentProject || 'default');
                    await get().fetchProjects();
                    set({ uploadSuccess: true });
                } catch (err: any) {
                    set({ error: err.message });
                } finally {
                    set({ isLoading: false });
                }
            },

            clearSelection: () => set({ selectedNodeId: null, selectedNodeDetail: null, graphData: { nodes: [], edges: [] } }),

            uploadSuccess: false,
            setUploadSuccess: (v: boolean) => set({ uploadSuccess: v }),
        }),
        {
            name: 'tcagent-storage',
            partialize: (state) => ({
                projects: state.projects,
                selectedProject: state.selectedProject,
                generatedScenarios: state.generatedScenarios,
                strategySummary: state.strategySummary,
            }),
        }
    )
);
