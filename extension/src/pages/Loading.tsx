import React from 'react'

const Loading = () => {
    return (
        <><div className="flex flex-col items-center justify-center px-6 pt-2 pb-12 mx-auto md:h-screen lg:py-0">
            <div className="flex items-center mb-6 text-2xl font-semibold text-gray-900 dark:text-white">
                <img className="w-8 h-8 mr-2" src="./icon-128.png" alt="logo" />
                SurfSense
            </div>
            <div className="loading">
                {"S A V I N G".split(" ").map((v, i) => (
                    <button
                        className="btn1"
                        style={{ animation: `move linear 0.9s infinite ${i / 10}s` }}
                        key={v}
                    >
                        {v}
                    </button>
                ))}
            </div>
        </div>

        </>

    )
}

export default Loading