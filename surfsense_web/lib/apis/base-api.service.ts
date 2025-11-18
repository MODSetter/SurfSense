import type z from "zod";
import {
  AppError,
  AuthenticationError,
  AuthorizationError,
  NotFoundError,
} from "../error";

enum ResponseType {
  JSON = "json",
  TEXT = "text",
  BLOB = "blob",
  ARRAY_BUFFER = "arrayBuffer",
  // Add more response types as needed
}

export type RequestOptions = {
  method: "GET" | "POST" | "PUT" | "DELETE";
  headers?: Record<string, string>;
  contentType?: "application/json" | "application/x-www-form-urlencoded";
  signal?: AbortSignal;
  body?: any;
  responseType?: ResponseType;
  // Add more options as needed
};

class BaseApiService {
  bearerToken: string;
  baseUrl: string;

  noAuthEndpoints: string[] = [
    "/auth/jwt/login",
    "/auth/register",
    "/auth/refresh",
  ]; // Add more endpoints as needed

  constructor(bearerToken: string, baseUrl: string) {
    this.bearerToken = bearerToken;
    this.baseUrl = baseUrl;
  }

  setBearerToken(bearerToken: string) {
    this.bearerToken = bearerToken;
  }

  async request<T, R extends ResponseType = ResponseType.JSON>(
    url: string,
    responseSchema?: z.ZodSchema<T>,
    options?: RequestOptions & { responseType?: R }
  ): Promise<
    R extends ResponseType.JSON
      ? T
      : R extends ResponseType.TEXT
      ? string
      : R extends ResponseType.BLOB
      ? Blob
      : R extends ResponseType.ARRAY_BUFFER
      ? ArrayBuffer
      : unknown
  >  {
    try {
      const defaultOptions: RequestOptions = {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.bearerToken || ""}`,
        },
        method: "GET",
        responseType: ResponseType.JSON,
      };

      const mergedOptions: RequestOptions = {
        ...defaultOptions,
        ...(options ?? {}),
        headers: {
          ...defaultOptions.headers,
          ...(options?.headers ?? {}),
        },
      };

      if (!this.baseUrl) {
        throw new AppError("Base URL is not set.");
      }

      if (!this.bearerToken && !this.noAuthEndpoints.includes(url)) {
        throw new AuthenticationError(
          "You are not authenticated. Please login again."
        );
      }

      const fullUrl = new URL(url, this.baseUrl).toString();

      const response = await fetch(fullUrl, mergedOptions);

      if (!response.ok) {
        // biome-ignore lint/suspicious: Unknown
        let data;

        try {
          data = await response.json();
        } catch (error) {
          console.error("Failed to parse response as JSON:", error);

          throw new AppError(
            "Something went wrong",
            response.status,
            response.statusText
          );
        }

        // for fastapi errors response
        if (typeof data === "object" && "detail" in data) {
          throw new AppError(data.detail, response.status, response.statusText);
        }

        switch (response.status) {
          case 401:
            throw new AuthenticationError(
              "You are not authenticated. Please login again.",
              response.status,
              response.statusText
            );
          case 403:
            throw new AuthorizationError(
              "You don't have permission to access this resource.",
              response.status,
              response.statusText
            );
          case 404:
            throw new NotFoundError(
              "Resource not found",
              response.status,
              response.statusText
            );
          //  Add more cases as needed
          default:
            throw new AppError(
              "Something went wrong",
              response.status,
              response.statusText
            );
        }
      }

      // biome-ignore lint/suspicious: Unknown
      let data;
      const responseType = mergedOptions.responseType

      try {
        switch (responseType) {
          case ResponseType.JSON:
            data = await response.json();
            break;
          case ResponseType.TEXT:
            data = await response.text();
            break;
          case ResponseType.BLOB:
            data = await response.blob();
            break;
          case ResponseType.ARRAY_BUFFER:
            data = await response.arrayBuffer();
            break;
          //  Add more cases as needed
          default:
            data = await response.text();
        }
      } catch (error) {
        console.error("Failed to parse response as JSON:", error);
        throw new AppError(
          "Failed to parse response",
          response.status,
          response.statusText
        );
      }

      if (responseType === ResponseType.JSON) {
        if (!responseSchema) {
          return data;
        }
        const parsedData = responseSchema.safeParse(data);

        if (!parsedData.success) {
          /** The request was successful, but the response data does not match the expected schema.
           * 	This is a client side error, and should be fixed by updating the responseSchema to keep things typed.
           *  This error should not be shown to the user , it is for dev only.
           */
          console.error("Invalid API response schema:", parsedData.error);
        }

        return data;
      }

      return data;
    } catch (error) {
      console.error("Request failed:", error);
      throw error;
    }
  }

  async get<T>(
    url: string,
    responseSchema?: z.ZodSchema<T>,
    options?: Omit<RequestOptions, "method" | "responseType">
  ) {
    return this.request(url, responseSchema, {
      ...options,
      method: "GET",
	  responseType: ResponseType.JSON,
    });
  }

  async post<T>(
    url: string,
    responseSchema?: z.ZodSchema<T>,
    options?: Omit<RequestOptions, "method" | "responseType">
  ) {
    return this.request(url, responseSchema, {
      method: "POST",
      ...options,
	  responseType: ResponseType.JSON,
    });
  }

  async put<T>(
    url: string,
    responseSchema?: z.ZodSchema<T>,
    options?: Omit<RequestOptions, "method" | "responseType">
  ) {
    return this.request(url, responseSchema, {
      method: "PUT",
      ...options,
	  responseType: ResponseType.JSON,
    });
  }

  async delete<T>(
    url: string,
    responseSchema?: z.ZodSchema<T>,
    options?: Omit<RequestOptions, "method" | "responseType">,
  ) {
    return this.request(url, responseSchema, {
      method: "DELETE",
      ...options,
	  responseType: ResponseType.JSON,
    });
  }

  async getBlob(
    url: string,
    options?: Omit<RequestOptions, "method" | "responseType">
  ) {
    return this.request(url, undefined, {
      ...options,
      method: "GET",
      responseType: ResponseType.BLOB,
    });
  }
}

export const baseApiService = new BaseApiService(
  typeof window !== "undefined"
    ? localStorage.getItem("surfsense_bearer_token") || ""
    : "",
  process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || ""
);
