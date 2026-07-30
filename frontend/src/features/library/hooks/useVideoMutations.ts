import { useMutation, useQueryClient } from "@tanstack/react-query";
import { openFolder, setFavorite } from "../../../api/videos";

export function useToggleFavorite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ videoId, favorite }: { videoId: number; favorite: boolean }) =>
      setFavorite(videoId, favorite),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
    },
  });
}

export function useOpenFolder() {
  return useMutation({
    mutationFn: (videoId: number) => openFolder(videoId),
  });
}
