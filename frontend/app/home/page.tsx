"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
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
import {
  PressReviewError,
  generatePressReview,
  getPressReview,
  listPressReviews,
  type PressReview,
} from "@/lib/pressReviews";
import styles from "./page.module.css";

const examples = [
  "Quelles sont les dernières nouvelles en politique ?",
  "Génère une revue de presse sur la technologie",
  "Résume l'actualité économique de la semaine",
];

// Pre-filled in the message input so the user can send it right away.
const PRELOADED_DRAFT = examples[0];

const envLinks = [
  { label: "Local front", href: "http://localhost:3000/home" },
  { label: "Local back", href: "http://localhost:8000/" },
  { label: "Prod front", href: "https://news-foundry-git-main-generate-ia.vercel.app/" },
  { label: "Prod back", href: "https://newsfoundry-production-ac98.up.railway.app/" },
];

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("fr-FR");
}

function formatRevueDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Home() {
  const router = useRouter();
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [activeChatId, setActiveChatId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState(PRELOADED_DRAFT);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"chat" | "revue">("chat");
  const [showRevueModal, setShowRevueModal] = useState(false);
  const [revueTitle, setRevueTitle] = useState("");
  const [discussionPressReviews, setDiscussionPressReviews] = useState<PressReview[]>([]);
  const [isLoadingDiscussionRevues, setIsLoadingDiscussionRevues] = useState(false);
  const [isGeneratingRevue, setIsGeneratingRevue] = useState(false);
  const [revueError, setRevueError] = useState<string | null>(null);
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

  async function loadDiscussionPressReviews(chatId: number) {
    setIsLoadingDiscussionRevues(true);
    try {
      const summaries = await listPressReviews(chatId);
      const reviews = await Promise.all(summaries.map((summary) => getPressReview(summary.id)));
      setDiscussionPressReviews(reviews);
    } catch {
      setRevueError("Impossible de récupérer les revues de cette discussion.");
    } finally {
      setIsLoadingDiscussionRevues(false);
    }
  }

  async function handleSelectChat(chatId: number) {
    // Keep whichever tab (Discussion or Revue de presse) was already open
    // instead of forcing it back to Discussion.
    setActiveChatId(chatId);
    setRevueError(null);
    setError(null);
    setIsLoadingMessages(true);
    loadDiscussionPressReviews(chatId);
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
    setActiveTab("chat");
    setActiveChatId(null);
    setMessages([]);
    setDiscussionPressReviews([]);
    setDraft(PRELOADED_DRAFT);
    setError(null);
  }

  function handleShowRevueTab() {
    setActiveTab("revue");
    setRevueError(null);
  }

  function buildReviewCopyText(review: PressReview): string {
    const lines = [review.title, formatRevueDate(review.generated_at), ""];
    for (const article of review.articles) {
      lines.push(article.title);
      if (article.summary) {
        lines.push(article.summary);
      }
      lines.push("");
    }
    return lines.join("\n").trim();
  }

  function handleCopyReview(reviewId: number) {
    const review = discussionPressReviews.find((item) => item.id === reviewId);
    if (!review) return;
    navigator.clipboard.writeText(buildReviewCopyText(review));
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
        setDiscussionPressReviews([]);
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

  function handleOpenRevueModal() {
    setRevueTitle("");
    setShowRevueModal(true);
  }

  async function handleGenerateRevue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const theme = revueTitle.trim();
    // The "Générer" button only shows once a discussion is loaded, so
    // activeChatId is always set here; a revue always belongs to one.
    if (!theme || isGeneratingRevue || activeChatId === null) return;

    setShowRevueModal(false);
    setActiveTab("revue");
    setRevueError(null);
    setIsGeneratingRevue(true);

    try {
      await generatePressReview(theme, activeChatId);
      await loadDiscussionPressReviews(activeChatId);
    } catch (err) {
      setRevueError(
        err instanceof PressReviewError ? err.message : "Une erreur est survenue."
      );
    } finally {
      setIsGeneratingRevue(false);
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

          <nav className={styles.sidebarNav}>
            <div className={styles.menuSection}>
              <button
                type="button"
                className={
                  activeTab === "chat"
                    ? `${styles.menuHeader} ${styles.menuHeaderActive}`
                    : styles.menuHeader
                }
                onClick={handleNewDiscussion}
              >
                <span aria-hidden="true">💬</span>
                <span>Discussion</span>
              </button>
              <ul className={styles.discussionList}>
                {chats.slice(0, 5).map((chat) => (
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
            </div>
          </nav>

          <div className={styles.menuSection}>
            <a href="/settings" className={styles.menuHeader}>
              <span aria-hidden="true">⚙️</span>
              <span>Paramètres</span>
            </a>
            <ul className={styles.discussionList}>
              <li>
                <a href="/settings/swagger" className={styles.discussionItem}>
                  <div className={styles.discussionTitle}>SwaggerUI</div>
                </a>
              </li>
            </ul>
          </div>

          <button type="button" className={styles.logout}>
            <span aria-hidden="true">🚪</span>
            <span>Se déconnecter</span>
          </button>
        </aside>

        <main className={styles.main}>
          <div className={styles.tabBar}>
            <button
              type="button"
              className={activeTab === "chat" ? `${styles.tab} ${styles.tabActive}` : styles.tab}
              onClick={() => setActiveTab("chat")}
            >
              <span aria-hidden="true">💬</span>
              <span>Chat</span>
            </button>
            <button
              type="button"
              className={activeTab === "revue" ? `${styles.tab} ${styles.tabActive}` : styles.tab}
              onClick={handleShowRevueTab}
            >
              <span aria-hidden="true">📄</span>
              <span>Revue de presse</span>
            </button>
            {activeChatId !== null && (
              <button
                type="button"
                className={styles.generateRevueButton}
                onClick={handleOpenRevueModal}
              >
                + Générer une revue de presse
              </button>
            )}
          </div>

          {activeTab === "chat" ? (
            <>
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
                          {message.role === "assistant" ? (
                            <ReactMarkdown>{message.content}</ReactMarkdown>
                          ) : (
                            message.content
                          )}
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
            </>
          ) : (
            <div className={styles.chatArea}>
              <div className={styles.revuePage}>
                <h1 className={styles.revuePageTitle}>Revues de Presse</h1>
                <p className={styles.revuePageSubtitle}>
                  {activeChatId === null
                    ? "Démarrez ou sélectionnez une discussion pour voir ses revues de presse."
                    : "Revues de presse générées dans cette discussion."}
                </p>

                {isGeneratingRevue && (
                  <p className={styles.loadingText}>Génération de la revue de presse…</p>
                )}

                {revueError && (
                  <p role="alert" className={styles.errorBanner}>
                    {revueError}
                  </p>
                )}

                {activeChatId === null ? null : isLoadingDiscussionRevues ? (
                  <p className={styles.loadingText}>Chargement…</p>
                ) : discussionPressReviews.length === 0 && !isGeneratingRevue ? (
                  <p className={styles.loadingText}>
                    Aucune revue de presse dans cette discussion pour le moment.
                  </p>
                ) : (
                  <div className={styles.revueList}>
                    {discussionPressReviews.map((review) => (
                      <div className={styles.revueCard} key={review.id}>
                        <div className={styles.revueCardHeader}>
                          <h3 className={styles.revueCardTitle}>{review.title}</h3>
                          <button
                            type="button"
                            className={styles.copyButton}
                            onClick={() => handleCopyReview(review.id)}
                          >
                            Copier
                          </button>
                        </div>
                        <div className={styles.revueCardDate}>
                          <span aria-hidden="true">📅</span>
                          <span>{formatRevueDate(review.generated_at)}</span>
                        </div>

                        {review.articles.length > 0 && (
                          <div className={styles.articleList}>
                            {review.articles.map((article, articleIndex) => (
                              <div key={articleIndex} className={styles.articleRow}>
                                <h4 className={styles.articleTitle}>{article.title}</h4>
                                {article.summary && (
                                  <p className={styles.articleText}>{article.summary}</p>
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                        {review.prompt && (
                          <div className={styles.promptUsed}>
                            <p className={styles.promptUsedLabel}>Prompt utilisé</p>
                            <p className={styles.promptUsedText}>{review.prompt}</p>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </main>
      </div>

      {showRevueModal && (
        <div className={styles.modalOverlay} onClick={() => setShowRevueModal(false)}>
          <div className={styles.modalCard} onClick={(event) => event.stopPropagation()}>
            <div className={styles.modalHeader}>
              <button
                type="button"
                className={styles.modalClose}
                onClick={() => setShowRevueModal(false)}
              >
                Fermer
              </button>
            </div>

            <h2 className={styles.modalTitle}>Générer une revue de presse</h2>
            <p className={styles.modalSubtitle}>Donner un titre à votre revue de presse</p>

            <form onSubmit={handleGenerateRevue}>
              <label className={styles.modalLabel} htmlFor="revue-theme">
                Thème de la revue de presse
              </label>
              <input
                id="revue-theme"
                type="text"
                className={styles.modalInput}
                placeholder="ex. technologie, élections, économie"
                value={revueTitle}
                onChange={(event) => setRevueTitle(event.target.value)}
                autoFocus
              />

              <button
                type="submit"
                className={styles.modalSubmit}
                disabled={!revueTitle.trim() || isSending}
              >
                Générer
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
