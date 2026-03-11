import { create } from 'zustand'

interface UploadStore {
  open: boolean
  isImporting: boolean
  setOpen: (open: boolean) => void
  setIsImporting: (isImporting: boolean) => void
}

export const useUploadStore = create<UploadStore>((set) => ({
  open: false,
  isImporting: false,
  setOpen: (open) => set({ open }),
  setIsImporting: (isImporting) => set({ isImporting }),
}))
