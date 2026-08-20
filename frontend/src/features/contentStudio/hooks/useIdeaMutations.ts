import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createIdea, deleteIdea, updateIdea } from "../../../api/contentStrategy";
import type { IdeaCreateInput, IdeaUpdateInput } from "../types";

export function useCreateIdea() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: IdeaCreateInput) => createIdea(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content-ideas"] });
    },
  });
}

export function useUpdateIdea() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ideaId, patch }: { ideaId: number; patch: IdeaUpdateInput }) => updateIdea(ideaId, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content-ideas"] });
    },
  });
}

export function useDeleteIdea() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ideaId: number) => deleteIdea(ideaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content-ideas"] });
    },
  });
}
