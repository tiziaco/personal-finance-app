'use client'

import { AppSidebar } from "@/components/layout/app-sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { HUB_NAV } from "@/lib/hub-nav";
import { CSVUploadDialog } from "@/components/transactions/csv-upload-dialog";
import { useUploadStore } from "@/lib/stores/upload-store";
import { useConfirmCSVUpload } from "@/hooks/use-csv-upload";

function UploadManager() {
  const open = useUploadStore((s) => s.open)
  const setOpen = useUploadStore((s) => s.setOpen)
  const setIsImporting = useUploadStore((s) => s.setIsImporting)
  const confirmMutation = useConfirmCSVUpload()

  function handleConfirm(mappingId: string, confirmedMapping: Record<string, string>) {
    setOpen(false)
    setIsImporting(true)
    confirmMutation.mutate(
      { mappingId, confirmedMapping },
      { onSettled: () => setIsImporting(false) }
    )
  }

  return <CSVUploadDialog open={open} onOpenChange={setOpen} onConfirm={handleConfirm} />
}

export default function HubLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <AppSidebar items={HUB_NAV} variant="floating" />
      <SidebarInset className="flex flex-col overflow-hidden">
        <div className="flex-1 overflow-auto">
          <div className="px-2 py-2 min-w-0">
            {children}
          </div>
        </div>
      </SidebarInset>
      <UploadManager />
    </SidebarProvider>
  )
}
