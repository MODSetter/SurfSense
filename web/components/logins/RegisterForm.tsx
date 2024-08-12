"use client"
import React, { FormEvent, useState } from "react";
import ReCAPTCHA from "react-google-recaptcha";
import { useRouter } from "next/navigation";
import { useToast } from "../ui/use-toast";
import Link from "next/link";

export const RegisterForm = () => {
  const [captcha, setCaptcha] = useState<string | null>();
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confpassword, setConfPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { toast } = useToast()

  const validateForm = () => {
    if (!username || !password || !confpassword) {
      setError('Username and password are required');
      return false;
    }
    setError('');
    return true;
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);

    if (captcha) {
      if (!validateForm()) return;

      try {

        const toSend = {
          username: username,
          password: password,
          apisecretkey: process.env.NEXT_PUBLIC_API_SECRET_KEY!
        }

        const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL!}/register`, {
          method: 'POST',
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(toSend),
        });

        setLoading(false);

        if (response.ok) {
          toast({
            title: "Registered Successfully",
            description: "Redirecting to Login",
          })
          router.push('/login');
        } else {
          const errorData = await response.json();
          setError(errorData.detail || 'Authentication failed!');
        }
      } catch (error) {
        setLoading(false);
        setError('An error occurred. Please try again later.');
      }

    } else {
      setError('Recaptcha Failed');
    }
  }
  return (
    <section>
      <div className="flex flex-col items-center justify-center px-6 py-8 mx-auto md:h-screen lg:py-0">
        <div className="flex items-center mb-6 text-2xl font-semibold text-gray-900 dark:text-white">
          <img className="w-8 h-8 mr-2" src="./icon-128.png" alt="logo" />
          SurfSense
        </div>
        <div className="w-full bg-white rounded-lg shadow dark:border md:mt-0 sm:max-w-md xl:p-0 dark:bg-gray-800 dark:border-gray-700">
          <div className="p-6 space-y-4 md:space-y-6 sm:p-8">
            <h1 className="text-xl font-bold leading-tight tracking-tight text-gray-900 md:text-2xl dark:text-white">
              Create an account
            </h1>
            <form className="space-y-4 md:space-y-6" onSubmit={handleSubmit}>
              <div>
                <label className="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Your email</label>
                <input value={username}
                  onChange={(e) => setUsername(e.target.value)} type="username" name="username" id="username" className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500" placeholder="name@company.com" />
              </div>
              <div>
                <label className="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Password</label>
                <input value={password}
                  onChange={(e) => setPassword(e.target.value)} type="password" name="password" id="password" placeholder="••••••••" className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500" />
              </div>
              <div>
                <label className="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Confirm password</label>
                <input value={confpassword}
                  onChange={(e) => setConfPassword(e.target.value)}
                  type="confirm-password" name="confpassword" id="confpassword" placeholder="••••••••" className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500" />
              </div>
              <ReCAPTCHA sitekey={process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY!} className="mx-auto" onChange={setCaptcha} />
              <button type="submit" className="mt-4 w-full text-white bg-primary-600 hover:bg-primary-700 focus:ring-4 focus:outline-none focus:ring-primary-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center dark:bg-primary-600 dark:hover:bg-primary-700 dark:focus:ring-primary-800"> {loading ? 'Creating...' : 'Create Account'}</button>
              <p className="text-sm font-light text-gray-500 dark:text-gray-400">
                Already have an account? <Link href={"/login"} className="font-medium text-primary-600 hover:underline dark:text-primary-500">Login here</Link>
              </p>
              {error && <p style={{ color: 'red' }}>{error}</p>}
            </form>
          </div>
        </div>
      </div>
    </section>
  )
}