"use client";

import { useEffect, useRef, useState } from "react";
import Script from "next/script";
import { useRouter } from "next/navigation";
import { TOKEN_STORAGE_KEY } from "@/lib/auth";
import styles from "./page.module.css";

type SwaggerUIBundleFn = {
  (config: Record<string, unknown>): void;
  presets: { apis: unknown };
  plugins: { DownloadUrl: unknown };
};

declare global {
  interface Window {
    SwaggerUIBundle?: SwaggerUIBundleFn;
    SwaggerUIStandalonePreset?: unknown;
  }
}

export default function SwaggerPage() {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const [bundleLoaded, setBundleLoaded] = useState(false);
  const [presetLoaded, setPresetLoaded] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(TOKEN_STORAGE_KEY)) {
      router.replace("/");
    }
  }, [router]);

  useEffect(() => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/swagger-ui/swagger-ui.css";
    document.head.appendChild(link);
    return () => {
      document.head.removeChild(link);
    };
  }, []);

  useEffect(() => {
    if (!bundleLoaded || !presetLoaded) return;
    const { SwaggerUIBundle, SwaggerUIStandalonePreset } = window;
    if (!SwaggerUIBundle || !containerRef.current) return;

    SwaggerUIBundle({
      url: "/world-news-api-openapi.json",
      domNode: containerRef.current,
      deepLinking: true,
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
      plugins: [SwaggerUIBundle.plugins.DownloadUrl],
      layout: "StandaloneLayout",
    });
  }, [bundleLoaded, presetLoaded]);

  return (
    <div className={styles.appShell}>
      <Script
        src="/swagger-ui/swagger-ui-bundle.js"
        strategy="afterInteractive"
        onLoad={() => setBundleLoaded(true)}
      />
      <Script
        src="/swagger-ui/swagger-ui-standalone-preset.js"
        strategy="afterInteractive"
        onLoad={() => setPresetLoaded(true)}
      />

      <div className={styles.breadcrumb}>
        <a href="/home" className={styles.breadcrumbLink}>
          Home
        </a>
        <span className={styles.breadcrumbSeparator}>/</span>
        <a href="/settings" className={styles.breadcrumbLink}>
          Paramètres
        </a>
        <span className={styles.breadcrumbSeparator}>/</span>
        <span className={styles.breadcrumbCurrent}>SwaggerUI</span>
      </div>

      <div className={styles.header}>
        <h1 className={styles.title}>World News API</h1>
        <p className={styles.subtitle}>
          Documentation interactive de l&apos;API utilisée pour générer les revues de presse
          (spécification officielle World News API).
        </p>
      </div>

      <div id="swagger-ui-container" ref={containerRef} className={styles.swaggerContainer} />
    </div>
  );
}
