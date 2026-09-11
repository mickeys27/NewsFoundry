import { API_URL, TOKEN_STORAGE_KEY } from "@/lib/auth";

export class PressReviewError extends Error {}

export type PressReviewSummary = {
  id: number;
  title: string;
  excerpt: string;
  generated_at: string;
};

export type PressReviewArticle = {
  title: string;
  summary: string;
};

export type PressReview = {
  id: number;
  title: string;
  summary: string;
  prompt: string;
  generated_at: string;
  articles: PressReviewArticle[];
};

function authHeaders(): HeadersInit {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

export async function listPressReviews(chatId?: number): Promise<PressReviewSummary[]> {
  const url =
    chatId === undefined
      ? `${API_URL}/press-reviews`
      : `${API_URL}/press-reviews?chat_id=${chatId}`;
  const response = await fetch(url, { headers: authHeaders() });

  if (!response.ok) {
    throw new PressReviewError("Impossible de récupérer vos revues de presse.");
  }

  return response.json();
}

export async function getPressReview(reviewId: number): Promise<PressReview> {
  const response = await fetch(`${API_URL}/press-reviews/${reviewId}`, {
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new PressReviewError("Impossible de récupérer cette revue de presse.");
  }

  return response.json();
}

// Generates a press review synthesized directly from a discussion's own
// message history via a dedicated PydanticAI agent, so it always belongs to
// a chat and shows up in that discussion's "Revue de presse" tab.
export async function generatePressReview(
  theme: string,
  chatId: number
): Promise<PressReview> {
  const response = await fetch(`${API_URL}/press-reviews`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ theme, chat_id: chatId }),
  });

  if (!response.ok) {
    if (response.status === 502) {
      throw new PressReviewError(
        "Impossible de générer la revue de presse pour ce thème."
      );
    }
    throw new PressReviewError("Échec de la génération de la revue de presse.");
  }

  return response.json();
}
