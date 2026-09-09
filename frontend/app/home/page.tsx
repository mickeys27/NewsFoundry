"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { TOKEN_STORAGE_KEY } from "@/lib/auth";
import {
  ChatError,
  createChat,
  getChatMessages,
  listChats,
  sendMessage,
  type ChatMessage,
  type ChatSummary,
} from "@/lib/chats";
import styles from "./page.module.css";

const examples = [
  "Quelles sont les dernières nouvelles en politique ?",
  "Génère une revue de presse sur la technologie",
  "Résume l'actualité économique de la semaine",
];

const envLinks = [
  { label: "Local front", href: "http://localhost:3000/home" },
  { label: "Local back", href: "http://localhost:8000/" },
  { label: "Prod front", href: "https://news-foundry-git-main-generate-ia.vercel.app/" },
  { label: "Prod back", href: "https://newsfoundry-production-ac98.up.railway.app/" },
];

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("fr-FR");
}

export default function Home() {
  const router = useRouter();
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [activeChatId, setActiveChatId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chatAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!localStorage.getItem(TOKEN_STORAGE_KEY)) {
      router.replace("/");
      return;
    }

    listChats()
      .then(setChats)
      .catch(() => setError("Impossible de récupérer vos discussions."));
  }, [router]);

  useEffect(() => {
    chatAreaRef.current?.scrollTo({ top: chatAreaRef.current.scrollHeight });
  }, [messages]);

  async function handleSelectChat(chatId: number) {
    setActiveChatId(chatId);
    setError(null);
    setIsLoadingMessages(true);
    try {
      const chatMessages = await getChatMessages(chatId);
      setMessages(chatMessages);
    } catch {
      setError("Impossible de récupérer cette discussion.");
    } finally {
      setIsLoadingMessages(false);
    }
  }

  function handleNewDiscussion() {
    setActiveChatId(null);
    setMessages([]);
    setError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || isSending) return;

    setDraft("");
    setError(null);
    setMessages((previous) => [...previous, { role: "user", content }]);
    setIsSending(true);

    try {
      let chatId = activeChatId;
      if (chatId === null) {
        chatId = await createChat();
        setActiveChatId(chatId);
        setChats((previous) => [
          { id: chatId as number, created_at: new Date().toISOString(), last_message: content },
          ...previous,
        ]);
      }

      const reply = await sendMessage(chatId, content);
      setMessages((previous) => [...previous, reply]);
      setChats((previous) =>
        previous.map((chat) =>
          chat.id === chatId ? { ...chat, last_message: reply.content } : chat
        )
      );
    } catch (err) {
      setError(err instanceof ChatError ? err.message : "Une erreur est survenue.");
    } finally {
      setIsSending(false);
    }
  }

  const showWelcome = activeChatId === null && messages.length === 0;

  return (
    <div className={styles.appShell}>
      <div className={styles.breadcrumb}>
        <a href="/home" className={styles.breadcrumbLink}>
          Home
        </a>
      </div>

      <div className={styles.layout}>
        <aside className={styles.sidebar}>
          <div className={styles.sidebarHeader}>
            <span>NEWSFOUNDRY</span>
            <span aria-hidden="true">🔒</span>
          </div>

          <button type="button" className={styles.newChatButton} onClick={handleNewDiscussion}>
            + Nouvelle discussion
          </button>

          <div className={styles.envLinks}>
            {envLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.envLink}
              >
                {link.label}
              </a>
            ))}
          </div>

          <ul className={styles.discussionList}>
            {chats.map((chat) => (
              <li key={chat.id}>
                <button
                  type="button"
                  onClick={() => handleSelectChat(chat.id)}
                  className={
                    chat.id === activeChatId
                      ? `${styles.discussionItem} ${styles.discussionItemActive}`
                      : styles.discussionItem
                  }
                >
                  <div className={styles.discussionTitle}>
                    {chat.last_message || "Nouvelle discussion"}
                  </div>
                  <div className={styles.discussionDate}>{formatDate(chat.created_at)}</div>
                </button>
              </li>
            ))}
          </ul>

          <a href="/settings" className={styles.settingsLink}>
            <span aria-hidden="true">⚙️</span>
            <span>Paramètres</span>
          </a>

          <button type="button" className={styles.logout}>
            <span aria-hidden="true">🚪</span>
            <span>Se déconnecter</span>
          </button>
        </aside>

        <main className={styles.main}>
          <div className={styles.tabBar}>
            <button type="button" className={`${styles.tab} ${styles.tabActive}`}>
              <span aria-hidden="true">💬</span>
              <span>Chat</span>
            </button>
            <button type="button" className={styles.tab}>
              <span aria-hidden="true">📄</span>
              <span>Revue de presse</span>
            </button>
          </div>

          <div className={styles.chatArea} ref={chatAreaRef}>
            {showWelcome ? (
              <div className={styles.welcomeCard}>
                <div className={styles.robotIcon} aria-hidden="true">
                  🤖
                </div>
                <h1 className={styles.welcomeTitle}>Assistant Revue de Presse IA</h1>
                <p className={styles.welcomeText}>
                  Posez-moi des questions sur l&apos;actualité récente ou demandez-moi de
                  générer une revue de presse sur un sujet spécifique.
                </p>
                <p className={styles.examplesLabel}>Exemples :</p>
                <ul className={styles.examplesList}>
                  {examples.map((example) => (
                    <li key={example}>&quot;{example}&quot;</li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className={styles.messageList}>
                {isLoadingMessages && <p className={styles.loadingText}>Chargement…</p>}
                {messages.map((message, index) => (
                  <div
                    key={index}
                    className={
                      message.role === "user"
                        ? `${styles.messageRow} ${styles.messageRowUser}`
                        : styles.messageRow
                    }
                  >
                    {message.role === "assistant" && (
                      <div className={styles.avatarAssistant} aria-hidden="true">
                        🤖
                      </div>
                    )}
                    <div
                      className={
                        message.role === "user" ? styles.bubbleUser : styles.bubbleAssistant
                      }
                    >
                      {message.content}
                    </div>
                    {message.role === "user" && (
                      <div className={styles.avatarUser} aria-hidden="true">
                        👤
                      </div>
                    )}
                  </div>
                ))}
                {isSending && (
                  <div className={styles.messageRow}>
                    <div className={styles.avatarAssistant} aria-hidden="true">
                      🤖
                    </div>
                    <div className={styles.bubbleAssistant}>…</div>
                  </div>
                )}
              </div>
            )}
          </div>

          {error && (
            <p role="alert" className={styles.errorBanner}>
              {error}
            </p>
          )}

          <form className={styles.inputBar} onSubmit={handleSubmit}>
            <input
              type="text"
              name="message"
              placeholder="Tapez votre message ici..."
              className={styles.messageInput}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              disabled={isSending}
            />
            <button
              type="submit"
              className={styles.sendButton}
              aria-label="Envoyer"
              disabled={isSending || !draft.trim()}
            >
              ➤
            </button>
          </form>
        </main>
      </div>
    </div>
  );
}
