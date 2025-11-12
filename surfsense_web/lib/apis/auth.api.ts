export const login = async (request: {
  username: string;
  password: string;
  grant_type?: string;
}) => {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/auth/jwt/login`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: JSON.stringify({
        username: request.username,
        password: request.password,
        grant_type: request.grant_type || "password",
      }),
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || `HTTP ${response.status}`);
  }

  return data;
};

export const register = async (request: {
  email: string;
  password: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}) => {
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
