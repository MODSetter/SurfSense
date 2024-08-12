"use client"
import React, { useState } from "react";
import { useRouter } from "next/navigation";

const FillEnvVariables = () => {
    const [neourl, setNeourl] = useState('');
    const [neouser, setNeouser] = useState('');
    const [neopass, setNeopass] = useState('');
    const [openaikey, setOpenaiKey] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);


    const router = useRouter();

    const validateForm = () => {
        if (!neourl || !neouser || !neopass || !openaikey) {
            setError('All values are required');
            return false;
        }
        setError('');
        return true;
    };

    const handleSubmit = async (event: { preventDefault: () => void; }) => {
        event.preventDefault();
        if (!validateForm()) return;
        setLoading(true);

        localStorage.setItem('neourl', neourl);
        localStorage.setItem('neouser', neouser);
        localStorage.setItem('neopass', neopass);
        localStorage.setItem('openaikey', openaikey);

        setLoading(false);
        router.push('/chat')
    };


    return (
        <section className="bg-gray-50 dark:bg-gray-900">
            <div className="flex flex-col items-center justify-center px-6 py-8 mx-auto md:h-screen lg:py-0">
                <a href="#" className="flex items-center mb-6 text-2xl font-semibold text-gray-900 dark:text-white">
                    <img className="w-8 h-8 mr-2" src="./icon-128.png" alt="logo" />
                    SurfSense
                </a>
                <div className="w-full bg-white rounded-lg shadow dark:border md:mt-0 sm:max-w-md xl:p-0 dark:bg-gray-800 dark:border-gray-700">
                    <div className="p-6 space-y-4 md:space-y-6 sm:p-8">
                        <h1 className="text-xl font-bold leading-tight tracking-tight text-gray-900 md:text-2xl dark:text-white">
                            Required Values
                        </h1>
                        <form className="space-y-4 md:space-y-6" onSubmit={handleSubmit}>
                            <div>
                                <label className="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Neo4J URL</label>
                                <input type="text" value={neourl} onChange={(e) => setNeourl(e.target.value)} name="neourl" id="neourl" className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500" placeholder="name@company.com" />
                            </div>

                            <div>
                                <label className="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Neo4J Username</label>
                                <input type="text" value={neouser} onChange={(e) => setNeouser(e.target.value)} name="neouser" id="neouser" className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500" placeholder="name@company.com" />
                            </div>
                            <div>
                                <label className="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Neo4J Password</label>
                                <input type="text" value={neopass} onChange={(e) => setNeopass(e.target.value)} name="neopass" id="neopass" placeholder="••••••••" className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500" />
                            </div>
                            <div>
                                <label className="block mb-2 text-sm font-medium text-gray-900 dark:text-white">OpenAI API Key</label>
                                <input type="text" value={openaikey} onChange={(e) => setOpenaiKey(e.target.value)} name="openaikey" id="openaikey" className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500" placeholder="name@company.com" />
                            </div>
                            <button type="submit" className="mt-4 w-full text-white bg-primary-600 hover:bg-primary-700 focus:ring-4 focus:outline-none focus:ring-primary-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center dark:bg-primary-600 dark:hover:bg-primary-700 dark:focus:ring-primary-800">{loading ? 'Saving....' : 'Save & Proceed'}</button>
                            {error && <p style={{ color: 'red' }}>{error}</p>}
                        </form>
                    </div>
                </div>
            </div>
        </section>
    )
}

export default FillEnvVariables
