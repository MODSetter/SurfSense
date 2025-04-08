import React from 'react'
import icon from "data-base64:~assets/icon.png"
import { ReloadIcon } from "@radix-ui/react-icons"

const Loading = () => {
    return (
        <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-gray-900 to-gray-800">
            <div className="w-full max-w-md mx-auto space-y-8">
                <div className="flex flex-col items-center space-y-2">
                    <div className="bg-gray-800 p-3 rounded-full ring-2 ring-gray-700 shadow-lg">
                        <img className="w-12 h-12" src={icon} alt="SurfSense" />
                    </div>
                    <h1 className="text-3xl font-semibold tracking-tight text-white mt-4">SurfSense</h1>
                </div>
                
                <div className="flex flex-col items-center mt-8">
                    <ReloadIcon className="h-10 w-10 text-teal-400 animate-spin" />
                    <div className="mt-6 text-lg text-gray-300 flex space-x-1">
                        {Array.from("LOADING").map((letter, i) => (
                            <span 
                                key={i} 
                                className="inline-block animate-pulse text-teal-400"
                                style={{ 
                                    animationDelay: `${i * 0.1}s`,
                                    animationDuration: '1.5s'
                                }}
                            >
                                {letter}
                            </span>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    )
}

export default Loading