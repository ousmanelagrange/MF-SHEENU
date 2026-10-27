// Lecteur des enregistrements de récits : lecture / pause, position, barre de progression
// sur laquelle on appuie pour se déplacer.

import { useAudioPlayer, useAudioPlayerStatus } from "expo-audio";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import Svg, { Path, Rect } from "react-native-svg";
import { colors, fonts } from "../theme";

const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

export function AudioPlayer({ uri }: { uri: string }) {
  const player = useAudioPlayer(uri);
  const status = useAudioPlayerStatus(player);
  const [width, setWidth] = useState(0);
  const progress = status.duration ? status.currentTime / status.duration : 0;

  const toggle = () => {
    if (status.playing) player.pause();
    else {
      // Arrivé à la fin, on reprend au début
      if (status.duration && status.currentTime >= status.duration - 0.5) void player.seekTo(0);
      player.play();
    }
  };

  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 14, padding: 14, backgroundColor: colors.indigo50, borderRadius: 10 }}>
      <Pressable
        onPress={toggle}
        accessibilityRole="button"
        accessibilityLabel={status.playing ? "Pause" : "Écouter"}
        style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: colors.indigo700, alignItems: "center", justifyContent: "center" }}
      >
        <Svg width={18} height={18} viewBox="0 0 18 18">
          {status.playing ? (
            <>
              <Rect x={3} y={2} width={4} height={14} rx={1} fill={colors.white} />
              <Rect x={11} y={2} width={4} height={14} rx={1} fill={colors.white} />
            </>
          ) : (
            <Path d="M5 2.5v13l11-6.5z" fill={colors.white} />
          )}
        </Svg>
      </Pressable>
      <View style={{ flex: 1, gap: 6 }}>
        <Pressable
          onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
          onPress={(e) => width && status.duration && player.seekTo((e.nativeEvent.locationX / width) * status.duration)}
          style={{ height: 18, justifyContent: "center" }}
          accessibilityLabel="Position dans l'enregistrement"
        >
          <View style={{ height: 4, borderRadius: 2, backgroundColor: colors.indigo100 }}>
            <View style={{ width: `${progress * 100}%`, height: 4, borderRadius: 2, backgroundColor: colors.indigo700 }} />
          </View>
        </Pressable>
        <Text style={{ fontFamily: fonts.ui, fontSize: 12.5, color: colors.muted }}>
          {clock(status.currentTime)} / {status.duration ? clock(status.duration) : "–:––"}
        </Text>
      </View>
    </View>
  );
}
