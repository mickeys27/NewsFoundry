import { API_URL, TOKEN_STORAGE_KEY } from "@/lib/auth";

export class SettingsError extends Error {}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

export async function getSystemPrompt(): Promise<string> {
  const response = await fetch(`${API_URL}/settings/system-prompt`, {
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new SettingsError("Impossible de récupérer le prompt système.");
  }

  const data: { system_prompt: string } = await response.json();
  return data.system_prompt;
}

export async function updateSystemPrompt(systemPrompt: string): Promise<string> {
  const response = await fetch(`${API_URL}/settings/system-prompt`, {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify({ system_prompt: systemPrompt }),
  });

  if (!response.ok) {
    throw new SettingsError("Impossible d'enregistrer le prompt système.");
  }

  const data: { system_prompt: string } = await response.json();
  return data.system_prompt;
}
