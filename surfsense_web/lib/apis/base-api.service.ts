import z from "zod";
import {
  AppError,
  AuthenticationError,
  AuthorizationError,
  ValidationError,
} from "../error";

export type RequestOptions = {
  method: "GET" | "POST" | "PUT" | "DELETE";
  headers?: Record<string, string>;
  contentType?: "application/json" | "application/x-www-form-urlencoded";
  signal?: AbortSignal;
  body?: any;
  // Add more options as needed
};

export class BaseApiService {
  bearerToken: string;
  baseUrl: string;

  constructor(bearerToken: string, baseUrl: string) {
    this.bearerToken = bearerToken;
    this.baseUrl = baseUrl;
  }

  setBearerToken(bearerToken: string) {
    this.bearerToken = bearerToken;
  }

  async request<T>(
    url: string,
    body?: any,
    responseSchema?: z.ZodSchema<T>,
    options?: RequestOptions
  ) {
    const defaultOptions: RequestOptions = {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.bearerToken}`,
      },
      method: "GET",
    };

    const mergedOptions: RequestOptions = {
      ...defaultOptions,
      ...(options ?? {}),
      headers: {
        ...defaultOptions.headers,
        ...(options?.headers ?? {}),
      },
    };

    let requestBody;

    // Serialize body
    if (body) {
      if (mergedOptions.headers?.["Content-Type"].toLocaleLowerCase() === "application/json") {
        requestBody = JSON.stringify(body);
      }

      if (
        mergedOptions.headers?.["Content-Type"].toLocaleLowerCase() ===
        "application/x-www-form-urlencoded"
      ) {
        requestBody = new URLSearchParams(body);
      }

      mergedOptions.body = requestBody;
    }

    if (!this.baseUrl) {
      throw new AppError("Base URL is not set.");
    }

    if (!this.bearerToken) {
      throw new AuthenticationError(
        "You are not authenticated. Please login again."
      );
    }

    const fullUrl = new URL(url, this.baseUrl).toString();

    const response = await fetch(fullUrl, mergedOptions);

    if (!response.ok) {
      if (response.status === 401) {
        throw new AuthenticationError(
          "You are not authenticated. Please login again."
        );
      }

      if (response.status === 403) {
        throw new AuthorizationError(
          "You don't have permission to access this resource."
        );
      }

      throw new AppError(`API Error: ${response.statusText}`);
    }

    let data;

    try {
      data = await response.json();
    } catch (error) {
      throw new AppError(`Failed to parse response as JSON: ${error}`);
    }

    if (!responseSchema) {
      return data;
    }

    const parsedData = responseSchema.safeParse(data);

    if (!parsedData.success) {
      throw new ValidationError(
        `Invalid response: ${parsedData.error.message}`
      );
    }

    return parsedData.data;
  }

  async get<T>(
    url: string,
    responseSchema?: z.ZodSchema<T>,
    options?: RequestOptions
  ) {
    return this.request(url, undefined, responseSchema, {
      ...options,
      method: "GET",
    });
  }

  async post<T>(
    url: string,
    body?: any,
    responseSchema?: z.ZodSchema<T>,
    options?: RequestOptions
  ) {
    return this.request(url, body, responseSchema, {
      ...options,
      method: "POST",
    });
  }

  async put<T>(
    url: string,
    body?: any,
    responseSchema?: z.ZodSchema<T>,
    options?: RequestOptions
  ) {
    return this.request(url, body, responseSchema, {
      ...options,
      method: "PUT",
    });
  }

  async delete<T>(
    url: string,
    body?: any,
    responseSchema?: z.ZodSchema<T>,
    options?: RequestOptions
  ) {
    return this.request(url, body, responseSchema, {
      ...options,
      method: "DELETE",
    });
  }
}
