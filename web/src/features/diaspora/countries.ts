// Nom de pays tel que saisi (français, souvent) → identifiant ISO 3166 numérique utilisé
// par la carte (world-atlas). Les pays les plus fréquents dans la diaspora africaine ;
// un pays absent de la liste figure quand même dans le classement, sans point sur la carte.

const ISO: Record<string, string> = {
  cameroun: "120", cameroon: "120", nigeria: "566", gabon: "266", tchad: "148", chad: "148",
  "guinee equatoriale": "226", congo: "178", "congo brazzaville": "178", "rd congo": "180", rdc: "180",
  "republique democratique du congo": "180", centrafrique: "140", "republique centrafricaine": "140",
  senegal: "686", "cote d'ivoire": "384", "cote divoire": "384", ghana: "288", togo: "768", benin: "204",
  mali: "466", "burkina faso": "854", niger: "562", guinee: "324", mauritanie: "478", liberia: "430",
  "sierra leone": "694", gambie: "270", maroc: "504", morocco: "504", algerie: "012", tunisie: "788",
  egypte: "818", "afrique du sud": "710", "south africa": "710", kenya: "404", rwanda: "646", burundi: "108",
  ethiopie: "231", angola: "024", madagascar: "450", zambie: "894", zimbabwe: "716", tanzanie: "834",
  ouganda: "800", mozambique: "508", namibie: "516", botswana: "072", soudan: "729",
  france: "250", belgique: "056", belgium: "056", suisse: "756", switzerland: "756", allemagne: "276",
  germany: "276", "royaume-uni": "826", "royaume uni": "826", angleterre: "826", uk: "826",
  "united kingdom": "826", italie: "380", italy: "380", espagne: "724", spain: "724", portugal: "620",
  "pays-bas": "528", "pays bas": "528", hollande: "528", luxembourg: "442", suede: "752", norvege: "578",
  danemark: "208", irlande: "372", autriche: "040", pologne: "616", russie: "643", turquie: "792",
  grece: "300", roumanie: "642", ukraine: "804", chypre: "196",
  "etats-unis": "840", "etats unis": "840", usa: "840", "united states": "840", canada: "124",
  mexique: "484", bresil: "076", haiti: "332",
  chine: "156", china: "156", japon: "392", inde: "356", "coree du sud": "410", malaisie: "458",
  "emirats arabes unis": "784", dubai: "784", "arabie saoudite": "682", qatar: "634", liban: "422",
  israel: "376", australie: "036",
};

/** « Côte d'Ivoire », « cote divoire » → « cote d'ivoire » (sans accents, minuscules). */
export function normalize(name: string) {
  return name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[’`]/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

export function isoOf(country: string): string | null {
  return ISO[normalize(country)] ?? null;
}
