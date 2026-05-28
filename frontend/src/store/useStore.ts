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
    class_name?: string;
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
    // Auth State
    user: { id: string; name: string; email: string } | null;
    token: string | null;
    isAuthenticated: boolean;
    authError: string | null;

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
    setSelectedMethodIds: (ids: string[]) => void;
    setViewMode: (mode: 'dashboard' | 'graph' | 'results') => void;

    projects: string[];
    selectedProject: string | null;
    fetchProjects: () => Promise<void>;
    selectProject: (projectId: string | null) => void;

    uploadSuccess: boolean;
    setUploadSuccess: (v: boolean) => void;

    // Auth Actions
    login: (email: string, password: string) => Promise<boolean>;
    signup: (name: string, email: string, password: string) => Promise<boolean>;
    logout: () => Promise<void>;
    checkAuth: () => Promise<void>;
    clearAuthError: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'; // 빌드/실행 환경에 맞게 백엔드 API 주소를 동적으로 선택합니다.

// 인증 토큰을 헤더에 자동으로 주입하는 fetch 래퍼 함수
const authFetch = async (url: string, options: RequestInit = {}): Promise<Response> => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    const headers = new Headers(options.headers || {});
    if (token) {
        headers.set('Authorization', `Bearer ${token}`);
    }
    return fetch(url, { ...options, headers });
};

export const useStore = create<AppState>((set, get) => ({
    // Auth State
    user: null,
    token: null,
    isAuthenticated: false,
    authError: null,

    // Data
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

    // Auth Actions
    clearAuthError: () => set({ authError: null }),

    checkAuth: async () => {
        const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
        if (!token) {
            set({ user: null, token: null, isAuthenticated: false });
            return;
        }
        try {
            const res = await authFetch(`${API_BASE}/auth/me`);
            if (res.ok) {
                const data = await res.json();
                set({ user: data.user, token: token, isAuthenticated: true });
            } else {
                localStorage.removeItem('token');
                set({ user: null, token: null, isAuthenticated: false });
            }
        } catch (err) {
            console.error('인증 확인 오류:', err);
            localStorage.removeItem('token');
            set({ user: null, token: null, isAuthenticated: false });
        }
    },

    login: async (email, password) => {
        set({ isLoading: true, authError: null });
        try {
            const res = await fetch(`${API_BASE}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || '로그인에 실패했습니다.');
            }
            const data = await res.json();
            localStorage.setItem('token', data.token);
            set({ user: data.user, token: data.token, isAuthenticated: true });
            return true;
        } catch (err: any) {
            set({ authError: err.message });
            return false;
        } finally {
            set({ isLoading: false });
        }
    },

    signup: async (name, email, password) => {
        set({ isLoading: true, authError: null });
        try {
            const res = await fetch(`${API_BASE}/auth/signup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, password })
            });
            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || '회원가입에 실패했습니다.');
            }
            return true;
        } catch (err: any) {
            set({ authError: err.message });
            return false;
        } finally {
            set({ isLoading: false });
        }
    },

    logout: async () => {
        const token = get().token;
        if (token) {
            try {
                await authFetch(`${API_BASE}/auth/logout`, {
                    method: 'POST'
                });
            } catch (err) {
                console.error('로그아웃 처리 중 오류:', err);
            }
        }
        localStorage.removeItem('token');
        set({ 
            user: null, 
            token: null, 
            isAuthenticated: false, 
            selectedMethodIds: [], 
            happyCaseScenarios: [], 
            integrationScenarios: [],
            selectedNodeId: null,
            selectedNodeDetail: null,
            graphData: { nodes: [], edges: [] }
        });
    },

    fetchProjects: async () => {
        try {
            const res = await authFetch(`${API_BASE}/projects`);
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
            const res = await authFetch(`${API_BASE}/projects/${projectId}/nodes`);
            if (!res.ok) throw new Error('Failed to fetch nodes');
            const data = await res.json();
            set({ projectNodes: data.nodes });

            // [Diff 기능] 초기 로딩 시 모든 메서드의 소스 코드를 스냅샷에 저장
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

    setSelectedMethodIds: (ids: string[]) => {
        set({ selectedMethodIds: ids.map(String) });
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
            const res = await authFetch(`${API_BASE}/graph/upstream/${nodeId}`);
            if (!res.ok) throw new Error('Failed to fetch upstream graph');
            const data = await res.json();
            set({ graphData: data, viewMode: 'graph' });
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
            const res = await authFetch(`${API_BASE}/graph/downstream/${nodeId}`);
            if (!res.ok) throw new Error('Failed to fetch downstream graph');
            const data = await res.json();
            set({ graphData: data, viewMode: 'graph' });
            await get().fetchNodeDetail(nodeId);
        } catch (err: any) {
            set({ error: err.message });
        } finally {
            set({ isLoading: false });
        }
    },

    fetchNodeDetail: async (nodeId) => {
        try {
            const res = await authFetch(`${API_BASE}/graph/node/${nodeId}`);
            if (res.ok) {
                const data = await res.json();
                set({ selectedNodeDetail: data });

                if (data.signature && data.source) {
                    const { codeSnapshots } = get();
                    const currentNode = get().projectNodes.find(n => n.id === nodeId);
                    const hasSnapshot = !!codeSnapshots[data.signature];
                    const isAlreadyModified = currentNode?.status === 'MODIFIED';

                    if (!hasSnapshot && !isAlreadyModified) {
                        console.log(`%c[Snapshot Saved] %c${data.signature}`, 'color: #4CAF50; font-weight: bold;', 'color: #2196F3;');
                        set({
                            codeSnapshots: {
                                ...codeSnapshots,
                                [data.signature]: data.source
                            }
                        });
                    }
                }
            }
        } catch (err) {
            console.error(err);
        }
    },

    generateIntegrationScenario: async (methodId) => {
        set({ isAgentRunning: true, error: null, integrationScenarios: [] });
        try {
            const res = await authFetch(`${API_BASE}/agent/integration-scenario/${methodId}`);
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
            const res = await authFetch(`${API_BASE}/agent/integration-scenario/batch/all`);
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

            const res = await authFetch(url);
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

            const res = await authFetch(`${API_BASE}/upload`, {
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
}));

if (typeof window !== 'undefined') {
    (window as any).store = useStore;
}
