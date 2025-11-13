export class AppError extends Error {
	constructor(message: string) {
		super(message);
		this.name = this.constructor.name;
	}
}

export class NetworkError extends AppError {
	constructor(message: string) {
		super(message);
	}
}

export class ValidationError extends AppError {
	constructor(message: string) {
		super(message);
	}
}

export class AuthenticationError extends AppError {
	constructor(message: string) {
		super(message);
	}
}

export class AuthorizationError extends AppError {
	constructor(message: string) {
		super(message);
	}
}
