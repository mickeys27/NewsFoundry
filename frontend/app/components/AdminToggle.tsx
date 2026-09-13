"use client";

import { useAdminMode } from "@/lib/admin";
import styles from "./AdminToggle.module.css";

export default function AdminToggle() {
  const [isAdmin, setAdminMode] = useAdminMode();

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isAdmin}
      className={isAdmin ? `${styles.toggle} ${styles.toggleAdmin}` : styles.toggle}
      onClick={() => setAdminMode(!isAdmin)}
      title={isAdmin ? "Désactiver le mode admin" : "Activer le mode admin"}
    >
      <span className={styles.track}>
        <span className={styles.thumb} />
      </span>
      <span className={styles.label}>{isAdmin ? "Admin" : "Utilisateur"}</span>
    </button>
  );
}
