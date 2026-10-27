// Icônes des onglets, dessinées en SVG pour éviter une bibliothèque d'icônes entière.

import Svg, { Circle, Path, Rect } from "react-native-svg";

type P = { color: string; size?: number };

export const PeopleIcon = ({ color, size = 22 }: P) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8}>
    <Circle cx={9} cy={8} r={3.2} />
    <Path d="M3 19c.8-3.2 3.2-5 6-5s5.2 1.8 6 5" />
    <Circle cx={17} cy={9} r={2.4} />
    <Path d="M16 14.2c2.4.2 4.2 1.8 5 4.8" />
  </Svg>
);

export const TreeIcon = ({ color, size = 22 }: P) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8}>
    <Rect x={9} y={3} width={6} height={5} rx={1.2} />
    <Rect x={3} y={16} width={6} height={5} rx={1.2} />
    <Rect x={15} y={16} width={6} height={5} rx={1.2} />
    <Path d="M12 8v4M6 16v-4h12v4" />
  </Svg>
);

export const CheckIcon = ({ color, size = 22 }: P) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8}>
    <Rect x={4} y={4} width={16} height={16} rx={3} />
    <Path d="M8 12.5l2.7 2.7L16 9.8" />
  </Svg>
);

export const MeIcon = ({ color, size = 22 }: P) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8}>
    <Circle cx={12} cy={8.5} r={3.6} />
    <Path d="M5 20c1-3.6 3.8-5.6 7-5.6s6 2 7 5.6" />
  </Svg>
);

export const WalletIcon = ({ color, size = 22 }: P) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8}>
    <Rect x={3} y={6} width={18} height={13} rx={2.5} />
    <Path d="M3 10h18M16 14.5h2" />
    <Path d="M6 6l9-3 1.5 3" />
  </Svg>
);
