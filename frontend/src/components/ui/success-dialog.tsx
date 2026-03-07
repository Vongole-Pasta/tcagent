import React from 'react';
import { CheckCircle2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useStore } from '@/store/useStore';
import { useEffect, useState } from 'react';

export function SuccessDialog() {
    const { uploadSuccess, setUploadSuccess } = useStore();
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        if (uploadSuccess) {
            setIsVisible(true);
            // Auto close after 5 seconds? Or let user close.
            // User said "Update finished window", implies interaction or clear notification.
        } else {
            setIsVisible(false);
        }
    }, [uploadSuccess]);

    if (!isVisible) return null;

    const handleClose = () => {
        setIsVisible(false);
        setUploadSuccess(false);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-300">
            <div className="relative w-full max-w-sm p-6 bg-white rounded-xl shadow-2xl border transform transition-all scale-100 animate-in zoom-in-95 duration-200">
                <button
                    onClick={handleClose}
                    className="absolute right-4 top-4 text-gray-400 hover:text-gray-600"
                >
                    <X className="h-4 w-4" />
                </button>

                <div className="flex flex-col items-center text-center space-y-4">
                    <div className="h-16 w-16 bg-green-100 rounded-full flex items-center justify-center mb-2">
                        <CheckCircle2 className="h-10 w-10 text-green-600" />
                    </div>

                    <h3 className="text-xl font-bold text-gray-900">
                        업로드 완료!
                    </h3>

                    <p className="text-sm text-gray-500">
                        프로젝트가 성공적으로 업로드, 분석되었습니다.
                    </p>

                    <Button
                        onClick={handleClose}
                        className="w-full bg-green-600 hover:bg-green-700 mt-2"
                    >
                        확인
                    </Button>
                </div>
            </div>
        </div>
    );
}
