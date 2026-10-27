import type { ThemeConfig } from "antd";

// Palette tirée du ntienya (ndop) bamoun : indigo teint à l'indigotier, coton non teint,
// laiton des fondeurs de Foumban pour les titres, bois rouge (camwood) en appoint.
export const palette = {
  indigo900: "#141B33", // texte
  indigo700: "#1F2D5C", // tissu, couleur principale
  indigo500: "#3B4E8A",
  indigo300: "#8D9AC2",
  indigo100: "#E7EAF3",
  indigo50: "#F3F4F9",
  cotton: "#FAFAFB", // fond
  line: "#DCDFE8",
  muted: "#5D6379",
  brass: "#9C7428", // titres, préséance
  brassSoft: "#F4ECDC",
  camwood: "#8C3A2B", // défunts, actions destructrices
  leaf: "#2F6B4F",
};

export const fonts = {
  ui: '"Instrument Sans", system-ui, -apple-system, "Segoe UI", sans-serif',
  names: '"Literata Variable", "Literata", Georgia, serif',
};

export const theme: ThemeConfig = {
  token: {
    colorPrimary: palette.indigo700,
    colorLink: palette.indigo500,
    colorText: palette.indigo900,
    colorTextSecondary: palette.muted,
    colorBorder: palette.line,
    colorBorderSecondary: "#E8EAF0",
    colorBgLayout: palette.cotton,
    colorError: palette.camwood,
    colorSuccess: palette.leaf,
    colorWarning: palette.brass,
    fontFamily: fonts.ui,
    fontSize: 15,
    borderRadius: 6,
    borderRadiusLG: 10,
    controlHeight: 38,
    boxShadow: "0 1px 2px rgba(20, 27, 51, 0.06)",
    boxShadowSecondary: "0 8px 24px rgba(20, 27, 51, 0.10)",
  },
  components: {
    Button: { fontWeight: 500, primaryShadow: "none", defaultShadow: "none" },
    Table: { headerBg: palette.indigo50, headerColor: palette.muted, rowHoverBg: palette.indigo50 },
    Menu: {
      itemBg: "transparent",
      itemColor: "rgba(255,255,255,0.72)",
      itemHoverColor: "#fff",
      itemSelectedColor: "#fff",
      itemSelectedBg: "rgba(255,255,255,0.10)",
      itemHoverBg: "rgba(255,255,255,0.06)",
      itemBorderRadius: 6,
      iconSize: 16,
    },
    Card: { headerFontSize: 16 },
    Tag: { defaultBg: palette.indigo50 },
  },
};
