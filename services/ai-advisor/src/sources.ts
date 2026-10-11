import { sha256Hex } from "@terravoce/protocol";
import type { Source } from "./schemas.js";

// Public project documentation, pinned by this reviewed source version.
// These are design constraints, not field-validated environmental evidence.
const corpus = [
  {
    id: "sampling-v1",
    text: "Il campionamento aggiuntivo raccoglie nuove osservazioni per verificare un calo dell'ossigeno. EXTRA_SAMPLING è un'azione reversibile del catalogo dimostrativo e richiede la verifica di TerraLex. Una proposta non autorizza da sola l'intervento.",
    url: "https://github.com/atlas-devlab/terravoce/blob/feat/ai-advisor/services/ai-advisor/SOURCES.md#sampling-v1"
  },
  {
    id: "limits-v1",
    text: "Rischio e confidence sono euristiche dimostrative, non probabilità scientifiche calibrate. Il consenso delle repliche non dimostra la verità fisica dei sensori. Comunità e giovani mantengono i diritti decisionali previsti dal Governor.",
    url: "https://github.com/atlas-devlab/terravoce/blob/feat/ai-advisor/services/ai-advisor/SOURCES.md#limits-v1"
  }
];
export const approvedSources = corpus.map((entry) => ({ ...entry, contentHash: sha256Hex(entry.text) }));
export const publicSources = (): Source[] => approvedSources.map(({ url: _url, ...source }) => ({ ...source }));
