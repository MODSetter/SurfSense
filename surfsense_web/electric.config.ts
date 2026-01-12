import { defineConfig } from '@electric-sql/cli'

export default defineConfig({
	connection: {
		host: process.env.ELECTRIC_HOST || 'localhost',
		port: parseInt(process.env.ELECTRIC_PORT || '5133', 10),
		database: process.env.POSTGRES_DB || 'surfsense',
		user: process.env.ELECTRIC_USER || 'electric',
		password: process.env.ELECTRIC_PASSWORD || 'electric_password',
	},
	outDir: './lib/electric/generated',
	service: {
		host: process.env.ELECTRIC_HOST || 'localhost',
		port: parseInt(process.env.ELECTRIC_PORT || '5133', 10),
	},
})

