"use client"

import { useEffect, useState } from 'react'
import { initElectric } from '@/lib/electric/client'

interface ElectricProviderProps {
	children: React.ReactNode
}

export function ElectricProvider({ children }: ElectricProviderProps) {
	const [initialized, setInitialized] = useState(false)
	const [error, setError] = useState<Error | null>(null)

	useEffect(() => {
		async function init() {
			try {
				await initElectric()
				setInitialized(true)
				setError(null)
			} catch (err) {
				console.error('Failed to initialize Electric SQL:', err)
				setError(err instanceof Error ? err : new Error('Failed to initialize Electric SQL'))
				// Don't block rendering if Electric SQL fails - app can still work
				setInitialized(true)
			}
		}

		init()
	}, [])

	// Show loading state only briefly, then render children
	// Electric SQL will sync in the background
	if (!initialized) {
		return (
			<div className="flex items-center justify-center min-h-screen">
				<div className="text-muted-foreground">Initializing...</div>
			</div>
		)
	}

	return <>{children}</>
}

