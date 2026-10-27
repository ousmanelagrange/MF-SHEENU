// Plusieurs personnes choisies dans l'arbre : pastilles retirables et recherche pour en ajouter.

import { CloseOutlined } from "@ant-design/icons";
import { PersonPicker } from "../../../components/Person";
import type { PersonSummary } from "../../../types";

export function PersonsField({
  value = [],
  onChange,
  placeholder = "Ajouter une personne",
}: {
  value?: PersonSummary[];
  onChange?: (persons: PersonSummary[]) => void;
  placeholder?: string;
}) {
  return (
    <div>
      {value.length > 0 && (
        <div className="chips">
          {value.map((p) => (
            <span key={p.id} className="chip">
              {p.display_name}
              <button type="button" aria-label={`Retirer ${p.display_name}`} onClick={() => onChange?.(value.filter((x) => x.id !== p.id))}>
                <CloseOutlined />
              </button>
            </span>
          ))}
        </div>
      )}
      {/* La clé remet le sélecteur à zéro après chaque ajout */}
      <PersonPicker
        key={value.length}
        placeholder={placeholder}
        exclude={value.map((p) => p.id)}
        onChange={(_, person) => person && onChange?.([...value, person])}
      />
    </div>
  );
}
