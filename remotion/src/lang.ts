import { createContext, useContext } from "react";

// The project's language ("vi", "en", ...) so on-screen labels that the renderer itself writes
// (not cut from the narration) match the narration language.
export const LanguageContext = createContext<string>("vi");

export function useStampLabel(status: "disputed" | "verified"): string {
  const en = useContext(LanguageContext).toLowerCase().startsWith("en");
  if (status === "disputed") return en ? "DISPUTED" : "CÒN TRANH CÃI";
  return en ? "VERIFIED" : "ĐÃ XÁC MINH";
}
