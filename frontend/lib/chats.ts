import { API_URL, TOKEN_STORAGE_KEY } from "@/lib/auth";

export class ChatError extends Error {}

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type ChatSummary = {
  id: number;
  created_at: string;
};

function authHeaders(): HeadersInit {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

export async function listChats(): Promise<ChatSummary[]> {
  const response = await fetch(`${API_URL}/chats`, { headers: authHeaders() });

  if (!response.ok) {
    throw new ChatError("Impossible de récupérer vos discussions.");
  }

  return response.json();
}

export async function createChat(): Promise<number> {
  const response = await fetch(`${API_URL}/chats`, {
    method: "POST",
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new ChatError("Impossible de créer une nouvelle discussion.");
  }

  const data: { id: number } = await response.json();
  return data.id;
}

export async function getChatMessages(chatId: number): Promise<ChatMessage[]> {
  const response = await fetch(`${API_URL}/chats/${chatId}`, {
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new ChatError("Impossible de récupérer cette discussion.");
  }

  const data: { messages: ChatMessage[] } = await response.json();
  return data.messages;
}

export async function sendMessage(chatId: number, content: string): Promise<ChatMessage> {
  const response = await fetch(`${API_URL}/chats/${chatId}/messages`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ content }),
  });

  if (!response.ok) {
    if (response.status === 502) {
      throw new ChatError("L'assistant est momentanément indisponible, veuillez réessayer.");
    }
    throw new ChatError("Échec de l'envoi du message, veuillez réessayer.");
  }

  return response.json();
}
