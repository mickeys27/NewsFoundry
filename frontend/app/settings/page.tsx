"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TOKEN_STORAGE_KEY } from "@/lib/auth";
import {
  getDisplaySettings,
  getNewsDigest,
  getSystemPrompt,
  refreshNewsDigest,
  updateDisplaySettings,
  updateNewsSynthesisPrompt,
  updateSystemPrompt,
  type NewsDigest,
} from "@/lib/settings";
import styles from "./page.module.css";

// Mirrors backend/src/models.py::DEFAULT_NEWS_SYNTHESIS_PROMPT, so the field
// always shows a sensible value even before the backend has responded.
const DEFAULT_NEWS_SYNTHESIS_PROMPT =
  "Tu vas recevoir une liste de titres et resumes d'articles d'actualite du jour. " +
  "Redige une synthese courte en francais, sous forme de liste a puces : une puce " +
  "par sujet distinct, une phrase courte par puce, pas de titres ni de sous-titres, " +
  "15 puces maximum. Regroupe les informations qui parlent du meme sujet et evite " +
  "les repetitions. Va a l'essentiel.";

function formatDateTime(isoDate: string): string {
  return new Date(isoDate).toLocaleString("fr-FR");
}

export default function SettingsPage() {
  const router = useRouter();
  const [savedPrompt, setSavedPrompt] = useState("");
  const [draft, setDraft] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(
    null,
  );

  const [digest, setDigest] = useState<NewsDigest | null>(null);
  const [synthesisDraft, setSynthesisDraft] = useState(DEFAULT_NEWS_SYNTHESIS_PROMPT);
  const [isLoadingDigest, setIsLoadingDigest] = useState(true);
  const [isSavingSynthesisPrompt, setIsSavingSynthesisPrompt] = useState(false);
  const [isRefreshingDigest, setIsRefreshingDigest] = useState(false);
  const [digestStatus, setDigestStatus] = useState<
    { type: "success" | "error"; message: string } | null
  >(null);

  const [savedListLimit, setSavedListLimit] = useState(5);
  const [listLimitDraft, setListLimitDraft] = useState("5");
  const [isLoadingListLimit, setIsLoadingListLimit] = useState(true);
  const [isSavingListLimit, setIsSavingListLimit] = useState(false);
  const [listLimitStatus, setListLimitStatus] = useState<
    { type: "success" | "error"; message: string } | null
  >(null);

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

    getNewsDigest()
      .then((value) => {
        setDigest(value);
        setSynthesisDraft(value.synthesis_prompt);
      })
      .catch(() => {
        setDigestStatus({
          type: "error",
          message: "Impossible de charger la synthèse des actualités.",
        });
      })
      .finally(() => setIsLoadingDigest(false));

    getDisplaySettings()
      .then((value) => {
        setSavedListLimit(value.press_review_list_limit);
        setListLimitDraft(String(value.press_review_list_limit));
      })
      .catch(() => {
        setListLimitStatus({
          type: "error",
          message: "Impossible de charger les préférences d'affichage.",
        });
      })
      .finally(() => setIsLoadingListLimit(false));
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

  async function handleSaveSynthesisPrompt() {
    setIsSavingSynthesisPrompt(true);
    setDigestStatus(null);

    try {
      const value = await updateNewsSynthesisPrompt(synthesisDraft);
      setDigest(value);
      setSynthesisDraft(value.synthesis_prompt);
      setDigestStatus({ type: "success", message: "Prompt de synthèse enregistré." });
    } catch {
      setDigestStatus({ type: "error", message: "Échec de l'enregistrement, veuillez réessayer." });
    } finally {
      setIsSavingSynthesisPrompt(false);
    }
  }

  async function handleRefreshDigest() {
    setIsRefreshingDigest(true);
    setDigestStatus(null);

    try {
      const value = await refreshNewsDigest();
      setDigest(value);
      setSynthesisDraft(value.synthesis_prompt);
      setDigestStatus({ type: "success", message: "Synthèse régénérée." });
    } catch {
      setDigestStatus({
        type: "error",
        message: "Échec de la régénération, veuillez réessayer.",
      });
    } finally {
      setIsRefreshingDigest(false);
    }
  }

  async function handleSaveListLimit() {
    const parsed = Number(listLimitDraft);
    if (!Number.isInteger(parsed) || parsed < 1) {
      setListLimitStatus({ type: "error", message: "Entrez un nombre entier positif." });
      return;
    }

    setIsSavingListLimit(true);
    setListLimitStatus(null);

    try {
      const value = await updateDisplaySettings(parsed);
      setSavedListLimit(value.press_review_list_limit);
      setListLimitDraft(String(value.press_review_list_limit));
      setListLimitStatus({ type: "success", message: "Préférence enregistrée." });
    } catch {
      setListLimitStatus({ type: "error", message: "Échec de l'enregistrement, veuillez réessayer." });
    } finally {
      setIsSavingListLimit(false);
    }
  }

  const hasUnsavedChanges = draft !== savedPrompt;
  const hasUnsavedSynthesisChanges = digest !== null && synthesisDraft !== digest.synthesis_prompt;
  const hasUnsavedListLimitChanges = listLimitDraft !== String(savedListLimit);

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

        <div className={`${styles.card} ${styles.cardSpacer}`}>
          <h1 className={styles.title}>Synthèse des actualités</h1>
          <p className={styles.subtitle}>
            Ce prompt sert à condenser les articles récupérés depuis World News API en un
            résumé court, injecté dans le prompt système du chat. La synthèse est enregistrée
            en base et ne change pas tant qu&apos;elle n&apos;est pas régénérée, pour ne pas
            perturber les discussions déjà en cours.
          </p>

          {isLoadingDigest ? (
            <p className={styles.loadingText}>Chargement…</p>
          ) : (
            <div className={styles.field}>
              <label htmlFor="news-synthesis-prompt" className={styles.label}>
                Instructions données au modèle pour la synthèse
                {synthesisDraft === DEFAULT_NEWS_SYNTHESIS_PROMPT && (
                  <span className={styles.defaultBadge}>Texte par défaut</span>
                )}
              </label>
              <textarea
                id="news-synthesis-prompt"
                className={styles.textarea}
                value={synthesisDraft}
                onChange={(event) => setSynthesisDraft(event.target.value)}
                disabled={isSavingSynthesisPrompt || isRefreshingDigest}
              />

              <div className={styles.actions}>
                <button
                  type="button"
                  className={styles.saveButton}
                  onClick={handleSaveSynthesisPrompt}
                  disabled={
                    isSavingSynthesisPrompt || isRefreshingDigest || !hasUnsavedSynthesisChanges
                  }
                >
                  {isSavingSynthesisPrompt ? "Enregistrement…" : "Enregistrer"}
                </button>
                <button
                  type="button"
                  className={styles.resetButton}
                  onClick={() => digest && setSynthesisDraft(digest.synthesis_prompt)}
                  disabled={
                    isSavingSynthesisPrompt || isRefreshingDigest || !hasUnsavedSynthesisChanges
                  }
                >
                  Annuler
                </button>
                <button
                  type="button"
                  className={styles.refreshButton}
                  onClick={handleRefreshDigest}
                  disabled={isRefreshingDigest || isSavingSynthesisPrompt}
                >
                  {isRefreshingDigest ? "Régénération…" : "Régénérer maintenant"}
                </button>

                {digestStatus && (
                  <span
                    role="status"
                    className={
                      digestStatus.type === "success" ? styles.statusSuccess : styles.statusError
                    }
                  >
                    {digestStatus.message}
                  </span>
                )}
              </div>

              {digest?.content && (
                <>
                  <div className={styles.digestPreview}>{digest.content}</div>
                  {digest.updated_at && (
                    <p className={styles.digestMeta}>
                      Dernière génération : {formatDateTime(digest.updated_at)}
                    </p>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        <div className={`${styles.card} ${styles.cardSpacer}`}>
          <h1 className={styles.title}>Affichage</h1>
          <p className={styles.subtitle}>
            Nombre de revues de presse affichées dans le menu et sur la page Revues de presse.
          </p>

          {isLoadingListLimit ? (
            <p className={styles.loadingText}>Chargement…</p>
          ) : (
            <div className={styles.field}>
              <label htmlFor="press-review-list-limit" className={styles.label}>
                Nombre de revues affichées
              </label>
              <input
                id="press-review-list-limit"
                type="number"
                min={1}
                className={styles.numberInput}
                value={listLimitDraft}
                onChange={(event) => setListLimitDraft(event.target.value)}
                disabled={isSavingListLimit}
              />

              <div className={styles.actions}>
                <button
                  type="button"
                  className={styles.saveButton}
                  onClick={handleSaveListLimit}
                  disabled={isSavingListLimit || !hasUnsavedListLimitChanges}
                >
                  {isSavingListLimit ? "Enregistrement…" : "Enregistrer"}
                </button>
                <button
                  type="button"
                  className={styles.resetButton}
                  onClick={() => setListLimitDraft(String(savedListLimit))}
                  disabled={isSavingListLimit || !hasUnsavedListLimitChanges}
                >
                  Annuler
                </button>

                {listLimitStatus && (
                  <span
                    role="status"
                    className={
                      listLimitStatus.type === "success" ? styles.statusSuccess : styles.statusError
                    }
                  >
                    {listLimitStatus.message}
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
