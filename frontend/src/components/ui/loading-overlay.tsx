import React, { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';

const MESSAGES = [
    "Analyzing Code Structure... 🧐",
    "Extracting Dependency Graph... 🕸️",
    "Identifying API Endpoints... 🔗",
    "Calculating Complexity Metrics... 🧮",
    "Syncing with Neo4j Database... 💾",
    "Almost there... 🚀"
];

export function LoadingOverlay() {
    const [messageIndex, setMessageIndex] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setMessageIndex((prev) => (prev + 1) % MESSAGES.length);
        }, 2000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-background/80 backdrop-blur-sm">
            <div className="flex flex-col items-center space-y-4 p-8 rounded-xl bg-card border shadow-2xl animate-in fade-in zoom-in duration-300">
                <div className="relative">
                    <div className="absolute inset-0 bg-blue-500 rounded-full blur-xl opacity-20 animate-pulse"></div>
                    <Loader2 className="h-12 w-12 text-blue-600 animate-spin relative z-10" />
                </div>

                <h3 className="text-lg font-semibold text-foreground animate-pulse">
                    Processing Project
                </h3>

                <p className="text-sm text-muted-foreground min-w-[200px] text-center transition-all duration-500">
                    {MESSAGES[messageIndex]}
                </p>
            </div>
        </div>
    );
}
