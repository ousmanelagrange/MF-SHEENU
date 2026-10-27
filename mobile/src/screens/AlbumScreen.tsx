// Un album sur mobile : grille de photos, visionneuse avec les personnes reconnues,
// ajout de photos depuis la galerie du téléphone.

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, FlatList, Image, Modal, Pressable, Text, useWindowDimensions, View } from "react-native";
import { api, uploadImage } from "../api";
import { Button, s } from "../components/ui";
import type { Album, AlbumPhoto } from "../memory";
import { pickImages } from "../pickImages";
import { colors, fonts } from "../theme";

export function AlbumScreen({ id }: { id: string }) {
  const { width } = useWindowDimensions();
  const [album, setAlbum] = useState<Album | null>(null);
  const [open, setOpen] = useState<AlbumPhoto | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => void api<Album>(`/albums/${id}`).then(setAlbum), [id]);
  useEffect(load, [load]);

  const add = async () => {
    const assets = await pickImages(true);
    if (!assets.length) return;
    setBusy(true);
    try {
      for (const a of assets) {
        const url = await uploadImage(a);
        await api(`/albums/${id}/photos`, { method: "POST", body: { url } });
      }
      load();
    } catch (e) {
      Alert.alert("Envoi interrompu", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!album) return <ActivityIndicator style={{ marginTop: 40 }} />;
  const side = (Math.min(width, 640) - 4) / 3;

  return (
    <View style={{ flex: 1, backgroundColor: colors.cotton }}>
      <FlatList
        data={album.photos}
        numColumns={3}
        keyExtractor={(p) => p.id}
        columnWrapperStyle={{ gap: 2 }}
        contentContainerStyle={{ gap: 2, paddingBottom: 100 }}
        ListHeaderComponent={
          <View style={{ padding: 20, gap: 6 }}>
            <Text style={[s.h1, { fontSize: 24 }]}>{album.title}</Text>
            <Text style={s.sub}>{[album.year, `${album.photos.length} photo${album.photos.length > 1 ? "s" : ""}`].filter(Boolean).join(", ")}</Text>
            {album.description && <Text style={[s.lead, { marginTop: 4 }]}>{album.description}</Text>}
          </View>
        }
        renderItem={({ item }) => (
          <Pressable onPress={() => setOpen(item)} accessibilityLabel={item.caption ?? "Photo"}>
            <Image source={{ uri: item.url }} style={{ width: side, height: side, backgroundColor: colors.indigo50 }} />
          </Pressable>
        )}
      />
      <View style={{ position: "absolute", left: 20, right: 20, bottom: 20 }}>
        {busy ? <ActivityIndicator /> : <Button title="Ajouter des photos" onPress={add} />}
      </View>

      <Modal visible={!!open} animationType="fade" onRequestClose={() => setOpen(null)}>
        {open && (
          <Pressable onPress={() => setOpen(null)} style={{ flex: 1, backgroundColor: colors.indigo900, justifyContent: "center" }}>
            <Image source={{ uri: open.url }} style={{ width: "100%", aspectRatio: 4 / 3 }} resizeMode="contain" />
            <View style={{ padding: 20, gap: 6 }}>
              {open.caption && <Text style={{ fontFamily: fonts.ui, fontSize: 16, color: colors.white }}>{open.caption}</Text>}
              {open.persons.length > 0 && (
                <Text style={{ fontFamily: fonts.ui, color: "#C9CFE2" }}>Sur la photo : {open.persons.map((p) => p.display_name).join(", ")}</Text>
              )}
              <Text style={{ fontFamily: fonts.ui, fontSize: 12.5, color: "#8D9AC2" }}>
                {[open.year, `ajoutée par ${open.added_by}`].filter(Boolean).join(", ")}
              </Text>
            </View>
          </Pressable>
        )}
      </Modal>
    </View>
  );
}
