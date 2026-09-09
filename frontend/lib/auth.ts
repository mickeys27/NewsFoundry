export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const TOKEN_STORAGE_KEY = "access_token";

export class LoginError extends Error {}

export async function login(email: string, password: string): Promise<string> {
  const response = await fetch(`${API_URL}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    if (response.status === 401) {
      throw new LoginError("Email ou mot de passe incorrect.");
    }
    throw new LoginError("Une erreur est survenue, veuillez réessayer.");
  }

  const data: { access_token: string } = await response.json();
  return data.access_token;
}
