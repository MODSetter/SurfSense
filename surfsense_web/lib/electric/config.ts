/**
 * Electric SQL configuration
 * This file will be used by @electric-sql/cli to generate the schema
 */

export const electricConfig = {
	connection: {
		host: process.env.ELECTRIC_HOST || 'localhost',
		port: parseInt(process.env.ELECTRIC_PORT || '5133', 10),
		database: process.env.POSTGRES_DB || 'surfsense',
		user: process.env.ELECTRIC_USER || 'electric',
		password: process.env.ELECTRIC_PASSWORD || 'electric_password',
	},
	service: {
		host: process.env.ELECTRIC_HOST || 'localhost',
		port: parseInt(process.env.ELECTRIC_PORT || '5133', 10),
	},
}

