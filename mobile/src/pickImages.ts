// Choisir des photos dans la galerie du téléphone (ou du navigateur pour la version web).

import * as ImagePicker from "expo-image-picker";
import { Alert } from "react-native";

export async function pickImages(multiple: boolean): Promise<ImagePicker.ImagePickerAsset[]> {
  const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!permission.granted) {
    Alert.alert("Accès aux photos refusé", "Autorisez Sheenu à lire vos photos dans les réglages du téléphone.");
    return [];
  }
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ["images"],
    allowsMultipleSelection: multiple,
    quality: 0.85,
  });
  return result.canceled ? [] : result.assets;
}
