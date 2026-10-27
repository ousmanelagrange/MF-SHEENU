// Types partagés, calqués sur les réponses de l'API.

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

// ---------- Cotisations ----------

export type DueStatus = "paid" | "partial" | "unpaid" | "exempt";

export interface Scale {
  id: string;
  name: string;
  currency: string;
  amounts_by_generation: Record<string, number>;
  default_amount: number;
  exempt_under_age: number | null;
  include_spouses: boolean;
  active: boolean;
}

export interface Totals {
  due: number;
  collected: number;
  pending: number;
  persons_due: number;
  paid: number;
  partial: number;
  unpaid: number;
  exempt: number;
}

export interface ContributionEvent {
  id: string;
  title: string;
  kind: "mourning" | "wedding" | "birth" | "project" | "annual" | "other";
  description: string | null;
  currency: string;
  deadline: string | null;
  target_amount: number | null;
  concerned_person_id: string | null;
  status: "open" | "closed";
  created_at: string;
  closed_at: string | null;
  totals: Totals;
  can_manage: boolean;
}

export interface DueRow {
  due_id: string | null;
  person: PersonSummary;
  amount: number;
  paid: number;
  status: DueStatus;
  exempt: boolean;
  note: string | null;
}

export interface Payment {
  id: string;
  event_id: string;
  person: PersonSummary | null;
  amount: number;
  method: "mobile_money" | "cash" | "bank" | "other";
  reference: string | null;
  proof_url: string | null;
  original_amount: number | null;
  original_currency: string | null;
  status: "declared" | "validated" | "rejected";
  declared_by_name: string | null;
  review_note: string | null;
  created_at: string;
}

export interface PersonContribution {
  event: ContributionEvent;
  amount: number;
  paid: number;
  status: DueStatus;
}

// ---------- Vie sociale ----------

export interface Author {
  user_id: string;
  name: string;
  person: PersonSummary | null;
}

export interface PollOption {
  id: string;
  label: string;
  votes: number;
}

export interface Post {
  id: string;
  kind: "post" | "announcement" | "life_event" | "poll";
  life_event: "birth" | "wedding" | "death" | "success" | "other" | null;
  text: string;
  media: string[];
  persons: PersonSummary[];
  author: Author;
  on_behalf_of: PersonSummary | null;
  pinned: boolean;
  hidden: boolean;
  created_at: string;
  edited_at: string | null;
  reactions: Record<string, number>;
  my_reaction: string | null;
  comments_count: number;
  poll: PollOption[] | null;
  my_vote: string | null;
  can_edit: boolean;
  can_moderate: boolean;
}

export interface CommentItem {
  id: string;
  author: Author;
  text: string;
  created_at: string;
  can_delete: boolean;
}

export interface StoryGroup {
  author: Author;
  stories: { id: string; media_url: string; caption: string | null; created_at: string; expires_at: string }[];
}

export interface Birthday {
  person: PersonSummary;
  date: string;
  age: number | null;
  in_days: number;
}

// ---------- Mémoire (phase 5) ----------

export type LayerName = "original" | "fr" | "en";

export interface NarrativeTextVersion {
  id: string;
  layer: LayerName;
  text: string;
  author: Author;
  status: "pending" | "validated" | "superseded" | "rejected";
  review_note: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface NarrativeCard {
  id: string;
  title: string;
  language: string | null;
  teller: PersonSummary | null;
  media_kind: "audio" | "video" | null;
  year: number | null;
  era: string | null;
  layers: LayerName[];
  pending: number;
  created_at: string;
}

export interface Narrative extends NarrativeCard {
  media_url: string | null;
  place: string | null;
  persons: PersonSummary[];
  recorded_by: Author;
  texts: Record<LayerName, { validated: NarrativeTextVersion | null; pending: number }>;
  can_edit: boolean;
  can_review: boolean;
}

export interface AlbumCard {
  id: string;
  title: string;
  description: string | null;
  year: number | null;
  count: number;
  cover_url: string | null;
}

export interface AlbumPhoto {
  id: string;
  album_id: string;
  url: string;
  caption: string | null;
  year: number | null;
  persons: PersonSummary[];
  added_by: string;
  can_edit: boolean;
}

export interface Album extends AlbumCard {
  photos: AlbumPhoto[];
  can_edit: boolean;
}

export interface TimelineItem {
  year: number;
  day: string | null;
  kind: "birth" | "death" | "union" | "narrative" | "album" | "photo" | "life_event";
  title: string;
  person: PersonSummary | null;
  ref_id: string | null;
}
