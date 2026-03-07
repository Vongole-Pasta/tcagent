import { create } from 'zustand';
import { Node, Edge } from '@xyflow/react';

interface MethodNode {
    id: string;
    name: string;
    signature?: string;
    source?: string;
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
    trigger_methods?: string[];
    trigger_method_name?: string;
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
    codeSnapshots: Record<string, string>; // Diff를 위한 코드 스냅샷 (signature -> source)

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
    codeSnapshots: {}, // 초기 스냅샷은 빈 객체

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

            // [Diff 기능] 초기 로딩 시 모든 메서드의 소스 코드를 스냅샷에 저장
            // 이미 저장된 스냅샷은 덮어쓰지 않아 원본 코드를 보존합니다.
            const { codeSnapshots } = get();
            const newSnapshots: Record<string, string> = { ...codeSnapshots };
            let addedCount = 0;
            for (const node of data.nodes) {
                if (node.signature && node.source && !newSnapshots[node.signature]) {
                    newSnapshots[node.signature] = node.source;
                    addedCount++;
                }
            }
            if (addedCount > 0) {
                console.log(`%c[Snapshot] %c${addedCount}개 메서드 소스 코드 캐싱 완료`, 'color: #4CAF50; font-weight: bold;', 'color: #2196F3;');
                set({ codeSnapshots: newSnapshots });
            }
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

                // [Diff 기능] 소스 코드를 처음 가져왔을 때 스냅샷에 저장 (이력이 없을 때만)
                if (data.signature && data.source) {
                    const { codeSnapshots } = get();
                    const currentNode = get().projectNodes.find(n => n.id === nodeId);
                    const hasSnapshot = !!codeSnapshots[data.signature];
                    const isAlreadyModified = currentNode?.status === 'MODIFIED';

                    if (!hasSnapshot && !isAlreadyModified) {
                        // 저장이 가능한 경우
                        console.log(`%c[Snapshot Saved] %c${data.signature}`, 'color: #4CAF50; font-weight: bold;', 'color: #2196F3;');
                        set({
                            codeSnapshots: {
                                ...codeSnapshots,
                                [data.signature]: data.source
                            }
                        });
                    } else if (hasSnapshot) {
                        // 이미 저장된 경우
                        console.log(`%c[Snapshot Skipped] %c이미 저장된 스냅샷이 있습니다: ${data.signature}`, 'color: #FFA000; font-weight: bold;', 'color: #999;');
                    } else if (isAlreadyModified) {
                        // 이미 MODIFIED 상태라 저장을 안 하는 경우
                        console.log(`%c[Snapshot Skipped] %c이미 MODIFIED 상태라 원본으로 저장하지 않습니다: ${data.signature}`, 'color: #F44336; font-weight: bold;', 'color: #999;');
                    }
                }
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

// [디버깅용] 브라우저 콘솔에서 window.store.getState()로 상태 확인 가능
if (typeof window !== 'undefined') {
    (window as any).store = useStore;
}
