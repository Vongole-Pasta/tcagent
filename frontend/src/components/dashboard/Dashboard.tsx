"use client";

import React from 'react';
import { useStore } from '@/store/useStore';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Activity, Box, Globe, MousePointerClick } from 'lucide-react';

export function Dashboard() {
    const { projectNodes } = useStore();

    const totalMethods = projectNodes.length; // All nodes are methods, some have endpoints
    const totalEndpoints = projectNodes.filter(n => n.type === 'ENDPOINT').length;

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

                {/* Guide / Empty State Helper */}
                <Card className="items-center justify-center flex flex-col p-10 border-dashed border-2 bg-slate-50/50">
                    <div className="bg-blue-100 p-4 rounded-full mb-4">
                        <MousePointerClick className="h-8 w-8 text-blue-600" />
                    </div>
                    <h3 className="text-xl font-semibold mb-2">How to explore?</h3>
                    <p className="text-muted-foreground text-center max-w-md">
                        Select a <strong>Method</strong> or <strong>Endpoint</strong> from the left sidebar to visualize its call graph and dependency chain.
                    </p>
                </Card>

            </div>
        </div>
    );
}
