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

export type NewsDigest = {
  synthesis_prompt: string;
  content: string;
  updated_at: string | null;
};

export async function getNewsDigest(): Promise<NewsDigest> {
  const response = await fetch(`${API_URL}/settings/news-digest`, {
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new SettingsError("Impossible de récupérer la synthèse des actualités.");
  }

  return response.json();
}

export async function updateNewsSynthesisPrompt(synthesisPrompt: string): Promise<NewsDigest> {
  const response = await fetch(`${API_URL}/settings/news-digest/synthesis-prompt`, {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify({ synthesis_prompt: synthesisPrompt }),
  });

  if (!response.ok) {
    throw new SettingsError("Impossible d'enregistrer le prompt de synthèse.");
  }

  return response.json();
}

export async function refreshNewsDigest(): Promise<NewsDigest> {
  const response = await fetch(`${API_URL}/settings/news-digest/refresh`, {
    method: "POST",
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new SettingsError("Impossible de régénérer la synthèse des actualités.");
  }

  return response.json();
}

export type DisplaySettings = {
  press_review_list_limit: number;
};

export async function getDisplaySettings(): Promise<DisplaySettings> {
  const response = await fetch(`${API_URL}/settings/display`, {
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new SettingsError("Impossible de récupérer les préférences d'affichage.");
  }

  return response.json();
}

export async function updateDisplaySettings(
  pressReviewListLimit: number
): Promise<DisplaySettings> {
  const response = await fetch(`${API_URL}/settings/display`, {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify({
      press_review_list_limit: pressReviewListLimit,
    }),
  });

  if (!response.ok) {
    throw new SettingsError("Impossible d'enregistrer les préférences d'affichage.");
  }

  return response.json();
}
