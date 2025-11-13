import { LoginRequest, LoginResponse, RegisterRequest, RegisterResponse } from "./contracts";

export class AuthApiService {
  login = async (request: LoginRequest) : Promise<LoginResponse> => {
    const requestBody = new URLSearchParams();
    requestBody.append("username", request.email);
    requestBody.append("password", request.password);
    requestBody.append("grant_type", "password");

    const response = await fetch(
      `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/auth/jwt/login`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: requestBody.toString(),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }

    return data;
  };

  register = async (request: RegisterRequest) : Promise<RegisterResponse> => {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/auth/register`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }

    return data;
  };
}
