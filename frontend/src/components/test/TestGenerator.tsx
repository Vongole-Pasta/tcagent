
"use client";

import React, { useState } from 'react';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogTrigger
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Sparkles, Download, FileSpreadsheet, Loader2 } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

interface GeneratedScenario {
    test_case_id: string;
    test_case_name: string;
    step_no: number;
    description: string;
    pre_condition: string;
    procedure: string;
    expected_result: string;
    scenario_id: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function TestGenerator({ trigger }: { trigger?: React.ReactNode }) {
    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const [scenarios, setScenarios] = useState<GeneratedScenario[]>([]);
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
            setOpen(false); // Close dialog on success
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
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                {trigger || (
                    <Button size="lg" className="bg-blue-600 hover:bg-blue-700 shadow-md">
                        <Sparkles className="mr-2 h-4 w-4" />
                        Generate Tests
                    </Button>
                )}
            </DialogTrigger>
            <DialogContent className="max-w-6xl max-h-[90vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Sparkles className="h-5 w-5 text-blue-600" />
                        Integrated Test Generator
                    </DialogTitle>
                </DialogHeader>

                <div className="flex-1 overflow-auto p-1">
                    {loading ? (
                        <div className="flex flex-col items-center justify-center h-64 gap-4">
                            <Loader2 className="h-10 w-10 animate-spin text-blue-600" />
                            <p className="text-muted-foreground animate-pulse">Analyzing Call Graph & Generating Scenarios...</p>
                        </div>
                    ) : scenarios.length > 0 ? (
                        <div className="space-y-4">
                            <div className="flex justify-between items-center">
                                <p className="text-sm text-green-600 font-medium">✨ Successfully generated {scenarios.length} scenarios. Review and edit before downloading.</p>
                                <Button onClick={handleDownload} variant="outline" className="gap-2 border-green-600 text-green-700 hover:bg-green-50">
                                    <Download className="h-4 w-4" />
                                    Download Excel
                                </Button>
                            </div>
                            <div className="border rounded-md">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead className="w-[120px]">ID</TableHead>
                                            <TableHead className="w-[150px]">Case Name</TableHead>
                                            <TableHead className="w-[250px]">Description</TableHead>
                                            <TableHead className="w-[200px]">Pre-condition</TableHead>
                                            <TableHead className="w-[200px]">Procedure</TableHead>
                                            <TableHead className="w-[200px]">Expected Result</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {scenarios.map((scenario, idx) => (
                                            <TableRow key={idx}>
                                                <TableCell className="font-mono text-xs">{scenario.test_case_id}</TableCell>
                                                <TableCell>
                                                    <Input
                                                        value={scenario.test_case_name}
                                                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateScenario(idx, 'test_case_name', e.target.value)}
                                                        className="h-8 text-xs"
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <Textarea
                                                        value={scenario.description}
                                                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => updateScenario(idx, 'description', e.target.value)}
                                                        className="min-h-[60px] text-xs"
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <Textarea
                                                        value={scenario.pre_condition}
                                                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => updateScenario(idx, 'pre_condition', e.target.value)}
                                                        className="min-h-[60px] text-xs"
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <Textarea
                                                        value={scenario.procedure}
                                                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => updateScenario(idx, 'procedure', e.target.value)}
                                                        className="min-h-[60px] text-xs"
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <Textarea
                                                        value={scenario.expected_result}
                                                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => updateScenario(idx, 'expected_result', e.target.value)}
                                                        className="min-h-[60px] text-xs"
                                                    />
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center h-64 text-center space-y-4">
                            <FileSpreadsheet className="h-16 w-16 text-slate-200" />
                            <div className="space-y-2">
                                <h3 className="text-lg font-medium">Ready to Generate</h3>
                                <p className="text-sm text-muted-foreground max-w-sm">
                                    Click the button below to analyze modified code (Status: NEW/MODIFIED) and generate integration test scenarios.
                                </p>
                            </div>
                            <Button onClick={handleGenerate} size="lg" className="bg-blue-600 hover:bg-blue-700">
                                Start Generation
                            </Button>
                        </div>
                    )}

                    {error && (
                        <div className="p-4 mt-4 bg-red-50 text-red-600 rounded-md text-sm">
                            Error: {error}
                        </div>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}
