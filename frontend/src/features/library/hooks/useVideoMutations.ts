import { useMutation, useQueryClient } from "@tanstack/react-query";
import { addVideoTags, openFolder, removeVideoTag, setFavorite, updateVideo } from "../../../api/videos";

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

export function useUpdateVideo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      videoId,
      patch,
    }: {
      videoId: number;
      patch: { status?: string; category_id?: number; emotion_id?: number; notes?: string };
    }) => updateVideo(videoId, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
    },
  });
}

export function useAddTags() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ videoId, tagNames }: { videoId: number; tagNames: string[] }) =>
      addVideoTags(videoId, tagNames),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
    },
  });
}

export function useRemoveTag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ videoId, tagId }: { videoId: number; tagId: number }) => removeVideoTag(videoId, tagId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
    },
  });
}
