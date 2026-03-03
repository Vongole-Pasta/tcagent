import { create } from 'zustand';
import { Node, Edge } from '@xyflow/react';

interface MethodNode {
    id: string;
    name: string;
    signature?: string;
    endpoint?: string;
    http_method?: string;
    type: 'METHOD' | 'ENDPOINT';
    status?: string | null;
}

interface GraphData {
    nodes: Node[];
    edges: Edge[];
}

interface IntegrationScenario {
    endpoint: string;
    http_method: string;
    trigger_methods: string[];
    result: {
        scenario: string;
        expected_result: string;
        request: {
            payload: any;
            headers: string;
        };
        response: {
            payload: any;
            headers: string;
        };
    };
}

interface HappyCaseScenario {
    test_case_id: string;
    test_case: string;
    input_data: string;
    expected_result: string;
    endpoint: string;
    http_method: string;
}

interface AppState {
    // Data
    projectNodes: MethodNode[];
    graphData: GraphData;
    selectedNodeId: string | null;
    selectedNodeDetail: { name: string; signature: string; source: string; type?: string } | null;
    isLoading: boolean;
    error: string | null;

    // Agent State
    integrationScenarios: IntegrationScenario[];
    happyCaseScenarios: HappyCaseScenario[];
    scenarioCache: Record<string, IntegrationScenario[]>;
    isAgentRunning: boolean;
    selectedMethodIds: string[];
    viewMode: 'dashboard' | 'graph' | 'results';

    // Actions
    fetchProjectNodes: (projectId?: string) => Promise<void>;
    fetchUpstreamGraph: (nodeId: string) => Promise<void>;
    fetchDownstreamGraph: (nodeId: string) => Promise<void>;
    fetchNodeDetail: (nodeId: string) => Promise<void>;
    uploadFiles: (files: File[]) => Promise<void>;
    clearSelection: () => void;

    // Agent Actions
    generateIntegrationScenario: (methodId: string) => Promise<void>;
    generateBatchIntegrationScenarios: () => Promise<void>;
    generateHappyCaseScenarios: (methodIds?: string[]) => Promise<void>;
    clearScenarios: () => void;
    toggleMethodSelection: (id: string) => void;
    setViewMode: (mode: 'dashboard' | 'graph' | 'results') => void;

    projects: string[];
    selectedProject: string | null;
    fetchProjects: () => Promise<void>;
    selectProject: (projectId: string | null) => void;

    uploadSuccess: boolean;
    setUploadSuccess: (v: boolean) => void;
}

const API_BASE = 'http://localhost:8000'; // Make sure this matches your backend

export const useStore = create<AppState>((set, get) => ({
    projectNodes: [],
    graphData: { nodes: [], edges: [] },
    selectedNodeId: null,
    selectedNodeDetail: null,
    isLoading: false,
    error: null,

    // Agent State
    integrationScenarios: [],
    happyCaseScenarios: [],
    scenarioCache: {},
    isAgentRunning: false,
    selectedMethodIds: [],
    viewMode: 'dashboard',

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
        // Optionally fetch nodes for this project immediately?
        // The user might want to click "Search" or similar, but auto-fetch is nice.
        if (projectId) {
            get().fetchProjectNodes(projectId);
        } else {
            set({ projectNodes: [] });
        }
    },

    fetchProjectNodes: async (projectId = 'default') => {
        set({ isLoading: true, error: null });
        try {
            // Fetch both endpoints and methods to merge or just fetch all
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

    toggleMethodSelection: (id: string) => {
        const stringId = String(id);
        set((state) => ({
            selectedMethodIds: state.selectedMethodIds.includes(stringId)
                ? state.selectedMethodIds.filter(mid => String(mid) !== stringId)
                : [...state.selectedMethodIds, stringId]
        }));
    },

    setViewMode: (mode) => set({ viewMode: mode }),

    fetchUpstreamGraph: async (nodeId) => {
        set((state) => ({ 
            isLoading: true, 
            error: null, 
            selectedNodeId: nodeId, 
            integrationScenarios: state.scenarioCache[nodeId] || [] 
        }));
        try {
            const res = await fetch(`${API_BASE}/graph/upstream/${nodeId}`);
            if (!res.ok) throw new Error('Failed to fetch upstream graph');
            const data = await res.json();

            // Auto-layout logic can be added here or in visualizer
            // For now, passing raw data. UI component handles layout (dagre).
            set({ graphData: data, viewMode: 'graph' });

            // Also fetch details
            await get().fetchNodeDetail(nodeId);
        } catch (err: any) {
            set({ error: err.message });
        } finally {
            set({ isLoading: false });
        }
    },

    fetchDownstreamGraph: async (nodeId) => {
        set((state) => ({ 
            isLoading: true, 
            error: null, 
            selectedNodeId: nodeId, 
            integrationScenarios: state.scenarioCache[nodeId] || [] 
        }));
        try {
            const res = await fetch(`${API_BASE}/graph/downstream/${nodeId}`);
            if (!res.ok) throw new Error('Failed to fetch downstream graph');
            const data = await res.json();
            set({ graphData: data, viewMode: 'graph' });

            // Also fetch details
            await get().fetchNodeDetail(nodeId);
        } catch (err: any) {
            set({ error: err.message });
        } finally {
            set({ isLoading: false });
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

    // Agent Actions
    generateIntegrationScenario: async (methodId) => {
        set({ isAgentRunning: true, error: null, integrationScenarios: [] });
        try {
            const res = await fetch(`${API_BASE}/agent/integration-scenario/${methodId}`);
            if (!res.ok) throw new Error('Failed to generate integration scenario');
            const data = await res.json();
            set((state) => ({ 
                integrationScenarios: data.scenarios,
                scenarioCache: {
                    ...state.scenarioCache,
                    [methodId]: data.scenarios
                }
            }));
        } catch (err: any) {
            set({ error: err.message });
        } finally {
            set({ isAgentRunning: false });
        }
    },

    generateBatchIntegrationScenarios: async () => {
        set({ isAgentRunning: true, error: null, integrationScenarios: [], happyCaseScenarios: [] });
        try {
            const res = await fetch(`${API_BASE}/agent/integration-scenario/batch/all`);
            if (!res.ok) throw new Error('Failed to generate batch scenarios');
            const data = await res.json();
            set({ integrationScenarios: data.scenarios });
        } catch (err: any) {
            set({ error: err.message });
        } finally {
            set({ isAgentRunning: false });
        }
    },

    generateHappyCaseScenarios: async (methodIds) => {
        set({ isAgentRunning: true, error: null, happyCaseScenarios: [], integrationScenarios: [], viewMode: 'results' });
        try {
            const ids = methodIds || get().selectedMethodIds;
            const url = ids.length > 0
                ? `${API_BASE}/agent/happy-case/batch?method_ids=${ids.join(',')}`
                : `${API_BASE}/agent/happy-case/batch`;

            const res = await fetch(url);
            if (!res.ok) throw new Error('Failed to generate happy-case scenarios');
            const data = await res.json();
            set({ happyCaseScenarios: data.scenarios });
        } catch (err: any) {
            set({ error: err.message });
        } finally {
            set({ isAgentRunning: false });
        }
    },

    clearScenarios: () => set({ integrationScenarios: [], happyCaseScenarios: [], scenarioCache: {} }),

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

            // Refresh list after upload
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
}));
