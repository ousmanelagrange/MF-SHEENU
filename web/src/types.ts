export type Sex = "M" | "F" | "U";

export interface TitleBadge {
  holding_id: string;
  title_id: string;
  name: string;
  abbreviation: string | null;
  precedence: number;
  badge_color: string;
  active: boolean;
}

export interface PersonSummary {
  id: string;
  first_name: string;
  last_name: string | null;
  traditional_name: string | null;
  display_name: string;
  sex: Sex;
  birth_year: number | null;
  death_year: number | null;
  is_living: boolean;
  photo_url: string | null;
  generation: number | null;
  titles: TitleBadge[];
  has_account: boolean;
}

export interface PersonOut extends PersonSummary {
  nickname: string | null;
  birth_date: string | null;
  birth_place: string | null;
  death_date: string | null;
  death_place: string | null;
  village: string | null;
  country: string | null;
  biography: string | null;
  phone: string | null;
  email: string | null;
  contact_visibility: "family" | "branch" | "board" | "private";
  created_at: string;
  updated_at: string;
  can_edit: boolean;
}

export interface RelativeLink {
  relation_id: string;
  kind: string;
  certainty: string;
  person: PersonSummary;
}

export interface SpouseLink {
  union_id: string;
  kind: string;
  rank: number | null;
  start_date: string | null;
  end_date: string | null;
  end_reason: string | null;
  person: PersonSummary;
}

export interface PersonDetail extends PersonOut {
  parents: RelativeLink[];
  children: RelativeLink[];
  spouses: SpouseLink[];
  siblings: PersonSummary[];
}

export interface ParentChild {
  id: string;
  parent_id: string;
  child_id: string;
  kind: string;
  certainty: string;
}

export interface Union {
  id: string;
  person_a_id: string;
  person_b_id: string;
  kind: string;
  rank: number | null;
  end_reason: string | null;
}

export interface Tree {
  root_person_id: string | null;
  me_person_id: string | null;
  persons: PersonSummary[];
  parent_child: ParentChild[];
  unions: Union[];
}

export interface MyFamily {
  id: string;
  name: string;
  community: string | null;
  description: string | null;
  root_person_id: string | null;
  role: string;
  person_id: string | null;
}

export interface Kinship {
  related: boolean;
  label: string | null;
  relation_type: "self" | "blood" | "spouse" | "in_law" | "none";
  common_ancestor_id: string | null;
  distance_from: number | null;
  distance_to: number | null;
  path: PersonSummary[];
}

export interface Title {
  id: string;
  name: string;
  abbreviation: string | null;
  precedence: number;
  badge_color: string;
  hereditary: boolean;
  description: string | null;
}

export interface Member {
  id: string;
  user_id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  role: string;
  status: string;
  person_id: string | null;
  branch_person_id: string | null;
  joined_at: string;
}

export interface Invitation {
  id: string;
  person_id: string | null;
  role: string;
  note: string | null;
  created_at: string;
  expires_at: string;
  used_at: string | null;
}

export interface Stats {
  persons: number;
  living: number;
  deceased: number;
  members: number;
  generations: number;
  by_country: Record<string, number>;
  by_generation: Record<string, number>;
}

export const ROLE_LABELS: Record<string, string> = {
  member: "Membre",
  branch_head: "Chef de branche",
  treasurer: "Trésorier",
  secretary: "Secrétaire",
  admin: "Administrateur",
};
