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

interface AppState {
    // Data
    projectNodes: MethodNode[];
    graphData: GraphData;
    selectedNodeId: string | null;
    selectedNodeDetail: { name: string; signature: string; source: string } | null;
    isLoading: boolean;
    error: string | null;

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

const API_BASE = 'http://localhost:8000'; // Make sure this matches your backend

export const useStore = create<AppState>((set, get) => ({
    projectNodes: [],
    graphData: { nodes: [], edges: [] },
    selectedNodeId: null,
    selectedNodeDetail: null,
    isLoading: false,
    error: null,

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

    fetchUpstreamGraph: async (nodeId) => {
        set({ isLoading: true, error: null, selectedNodeId: nodeId });
        try {
            const res = await fetch(`${API_BASE}/graph/upstream/${nodeId}`);
            if (!res.ok) throw new Error('Failed to fetch upstream graph');
            const data = await res.json();

            // Auto-layout logic can be added here or in visualizer
            // For now, passing raw data. UI component handles layout (dagre).
            set({ graphData: data });

            // Also fetch details
            await get().fetchNodeDetail(nodeId);
        } catch (err: any) {
            set({ error: err.message });
        } finally {
            set({ isLoading: false });
        }
    },

    fetchDownstreamGraph: async (nodeId) => {
        set({ isLoading: true, error: null, selectedNodeId: nodeId });
        try {
            const res = await fetch(`${API_BASE}/graph/downstream/${nodeId}`);
            if (!res.ok) throw new Error('Failed to fetch downstream graph');
            const data = await res.json();
            set({ graphData: data });

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
