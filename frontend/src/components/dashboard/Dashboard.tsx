"use client";

import React, { useState } from 'react';
import { useStore } from '@/store/useStore';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from '@/components/ui/button';
import { TestResultsView, GeneratedScenario } from '@/components/test/TestResultsView';
import { Activity, Box, Globe, MousePointerClick, Sparkles, Loader2 } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function Dashboard() {
    const { projectNodes } = useStore();

    const totalMethods = projectNodes.length; // All nodes are methods, some have endpoints
    const totalEndpoints = projectNodes.filter(n => n.type === 'ENDPOINT').length;

    const [loading, setLoading] = useState(false);
    const [scenarios, setScenarios] = useState<GeneratedScenario[]>([]);
    const [strategySummary, setStrategySummary] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const handleGenerate = async () => {
        setLoading(true);
        setError(null);
        setScenarios([]);

        try {
            const response = await fetch(`${API_BASE_URL}/api/tests/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_id: 'default' })
            });

            if (!response.ok) {
                throw new Error('Failed to generate tests');
            }

            const data = await response.json();
            setScenarios(data.scenarios || []);
            setStrategySummary(data.strategy_summary || null);
        } catch (err: any) {
            setError(err.message || "An error occurred");
        } finally {
            setLoading(false);
        }
    };



    const handleDownload = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/tests/download`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scenarios })
            });

            if (!response.ok) throw new Error("Download failed");

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `integrated_tests_${new Date().toISOString().slice(0, 19)}.xlsx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (err: any) {
            setError(err.message);
        }
    };

    const updateScenario = (index: number, field: keyof GeneratedScenario, value: string | number) => {
        const newScenarios = [...scenarios];
        newScenarios[index] = { ...newScenarios[index], [field]: value };
        setScenarios(newScenarios);
    };

    return (
        <div className="p-8 h-full bg-slate-50 overflow-y-auto">
            <div className="max-w-5xl mx-auto space-y-8">

                {/* Header */}
                <div className="space-y-2">
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900">Project Dashboard</h1>
                    <p className="text-slate-500">
                        Welcome to TcAgent. Here is a summary of the analyzed project.
                    </p>
                </div>

                {/* Stats Grid */}
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Total Methods</CardTitle>
                            <Box className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{totalMethods}</div>
                            <p className="text-xs text-muted-foreground">
                                Identified functions & constructors
                            </p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Endpoints</CardTitle>
                            <Globe className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{totalEndpoints}</div>
                            <p className="text-xs text-muted-foreground">
                                Rest API Entry Points
                            </p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Analysis Status</CardTitle>
                            <Activity className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-green-600">Active</div>
                            <p className="text-xs text-muted-foreground">
                                Ready for Graph Exploration
                            </p>
                        </CardContent>
                    </Card>
                </div>

                {/* Actions */}
                <div className="flex items-center justify-between p-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-100 shadow-sm">
                    <div>
                        <h3 className="text-lg font-semibold text-blue-900">통합 테스트 생성</h3>
                        <p className="text-sm text-blue-700 mt-1">
                            현재 그래프 분석을 기반으로 포괄적인 통합 테스트 시나리오를 자동으로 생성합니다.
                        </p>
                    </div>
                    <Button
                        size="lg"
                        onClick={handleGenerate}
                        disabled={loading}
                        className="bg-blue-600 hover:bg-blue-700 shadow-md transition-all hover:scale-105"
                    >
                        {loading ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                생성 중...
                            </>
                        ) : (
                            <>
                                <Sparkles className="mr-2 h-4 w-4" />
                                테스트 생성
                            </>
                        )}
                    </Button>
                </div>

                {/* Error Message */}
                {error && (
                    <div className="p-4 bg-red-50 text-red-600 rounded-md text-sm border border-red-200">
                        Error: {error}
                    </div>
                )}

                {/* Content Area: Guide or Results */}
                {scenarios.length > 0 || strategySummary ? (
                    <TestResultsView
                        scenarios={scenarios}
                        strategySummary={strategySummary}
                        updateScenario={updateScenario}
                        onDownload={handleDownload}
                    />
                ) : (
                    /* Guide / Empty State Helper */
                    <Card className="items-center justify-center flex flex-col p-10 border-dashed border-2 bg-slate-50/50">
                        <div className="bg-blue-100 p-4 rounded-full mb-4">
                            <MousePointerClick className="h-8 w-8 text-blue-600" />
                        </div>
                        <h3 className="text-xl font-semibold mb-2">사용 방법</h3>
                        <p className="text-muted-foreground text-center max-w-md">
                            왼쪽 사이드바에서 <strong>Method</strong> 또는 <strong>Endpoint</strong>를 선택하여 호출 그래프와 의존성을 시각화하세요.
                            <br />
                            또는 위 <strong>"테스트 생성"</strong> 버튼을 눌러 변경된 코드에 대한 테스트 시나리오를 확인하세요.
                        </p>
                    </Card>
                )}

            </div>
        </div>
    );
}
