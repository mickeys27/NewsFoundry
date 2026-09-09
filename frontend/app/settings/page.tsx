"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TOKEN_STORAGE_KEY } from "@/lib/auth";
import { getSystemPrompt, updateSystemPrompt } from "@/lib/settings";
import styles from "./page.module.css";

export default function SettingsPage() {
  const router = useRouter();
  const [savedPrompt, setSavedPrompt] = useState("");
  const [draft, setDraft] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(
    null,
  );

  useEffect(() => {
    if (!localStorage.getItem(TOKEN_STORAGE_KEY)) {
      router.replace("/");
      return;
    }

    getSystemPrompt()
      .then((prompt) => {
        setSavedPrompt(prompt);
        setDraft(prompt);
      })
      .catch(() => {
        setStatus({ type: "error", message: "Impossible de charger le prompt système." });
      })
      .finally(() => setIsLoading(false));
  }, [router]);

  async function handleSave() {
    setIsSaving(true);
    setStatus(null);

    try {
      const prompt = await updateSystemPrompt(draft);
      setSavedPrompt(prompt);
      setDraft(prompt);
      setStatus({ type: "success", message: "Prompt enregistré." });
    } catch {
      setStatus({ type: "error", message: "Échec de l'enregistrement, veuillez réessayer." });
    } finally {
      setIsSaving(false);
    }
  }

  const hasUnsavedChanges = draft !== savedPrompt;

  return (
    <div className={styles.appShell}>
      <div className={styles.breadcrumb}>
        <a href="/home" className={styles.breadcrumbLink}>
          Home
        </a>
        <span className={styles.breadcrumbSeparator}>/</span>
        <span className={styles.breadcrumbCurrent}>Paramètres</span>
      </div>

      <div className={styles.content}>
        <div className={styles.card}>
          <h1 className={styles.title}>Prompt système</h1>
          <p className={styles.subtitle}>
            Ce texte définit le ton et le style des réponses de l&apos;assistant pour toutes
            les discussions.
          </p>

          {isLoading ? (
            <p className={styles.loadingText}>Chargement…</p>
          ) : (
            <div className={styles.field}>
              <label htmlFor="system-prompt" className={styles.label}>
                Instructions données au modèle
              </label>
              <textarea
                id="system-prompt"
                className={styles.textarea}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                disabled={isSaving}
              />

              <div className={styles.actions}>
                <button
                  type="button"
                  className={styles.saveButton}
                  onClick={handleSave}
                  disabled={isSaving || !hasUnsavedChanges}
                >
                  {isSaving ? "Enregistrement…" : "Enregistrer"}
                </button>
                <button
                  type="button"
                  className={styles.resetButton}
                  onClick={() => setDraft(savedPrompt)}
                  disabled={isSaving || !hasUnsavedChanges}
                >
                  Annuler
                </button>

                {status && (
                  <span
                    role="status"
                    className={status.type === "success" ? styles.statusSuccess : styles.statusError}
                  >
                    {status.message}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
