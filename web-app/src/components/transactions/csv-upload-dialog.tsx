'use client'

import { useRef, useState } from 'react'
import { Upload, FileSpreadsheet } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useUploadCSV } from '@/hooks/use-csv-upload'
import type { CSVUploadProposalResponse } from '@/types/csv-upload'

type Step = 'idle' | 'uploading' | 'mapping'

interface CSVUploadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (mappingId: string, confirmedMapping: Record<string, string>) => void
}

export function CSVUploadDialog({ open, onOpenChange, onConfirm }: CSVUploadDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const openRef = useRef(open)
  openRef.current = open
  const [step, setStep] = useState<Step>('idle')
  const [proposal, setProposal] = useState<CSVUploadProposalResponse | null>(null)
  const [editedMapping, setEditedMapping] = useState<Record<string, string>>({})

  const uploadMutation = useUploadCSV()

  function resetState() {
    setStep('idle')
    setProposal(null)
    setEditedMapping({})
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  function handleOpenChange(next: boolean) {
    if (!next) resetState()
    onOpenChange(next)
  }

  function handleFile(file: File) {
    setStep('uploading')
    uploadMutation.mutate(file, {
      onSuccess: (data) => {
        if (!openRef.current) return
        setProposal(data)
        setEditedMapping({ ...data.proposed_mapping })
        setStep('mapping')
      },
      onError: () => {
        if (!openRef.current) return
        setStep('idle')
      },
    })
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
  }

  function handleFileInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  function handleMappingChange(column: string, value: string | null) {
    if (value === null) return
    setEditedMapping((prev) => ({ ...prev, [column]: value }))
  }

  function handleConfirm() {
    if (!proposal) return
    onConfirm(proposal.mapping_id, editedMapping)
    resetState()
  }

  const isMapping = step === 'mapping'

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className={isMapping ? 'max-w-2xl' : 'max-w-md'}>
        {!isMapping ? (
          <>
            <DialogHeader>
              <div className="flex justify-center mb-2">
                <FileSpreadsheet className="h-10 w-10 text-muted-foreground" />
              </div>
              <DialogTitle className="text-center">Upload CSV</DialogTitle>
              <DialogDescription className="text-center">
                Import bank transactions from a CSV file. We&apos;ll detect and map your columns
                automatically.
              </DialogDescription>
            </DialogHeader>

            <div className="flex flex-col gap-3 mt-2">
              <div
                className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-muted-foreground/30 p-8 cursor-pointer hover:border-muted-foreground/60 transition-colors"
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-7 w-7 text-muted-foreground" />
                <p className="text-sm text-muted-foreground text-center">
                  Drag and drop a CSV file here, or click to browse
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={handleFileInputChange}
                />
              </div>

              <Button
                disabled={step === 'uploading'}
                onClick={() => fileInputRef.current?.click()}
                className="w-full"
              >
                {step === 'uploading' ? 'Processing…' : 'Select File'}
              </Button>
            </div>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Review Column Mapping</DialogTitle>
              <DialogDescription>
                We detected these columns. Adjust the mapping if needed before importing.
              </DialogDescription>
            </DialogHeader>

            <div className="mt-2 overflow-auto max-h-[60vh]">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left font-medium pb-3 w-1/3">Your CSV column</th>
                    <th className="text-left font-medium pb-3 w-1/3">Maps to</th>
                    <th className="text-left font-medium pb-3 w-1/3 text-muted-foreground">
                      Null rate
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {proposal && Object.keys(proposal.proposed_mapping).map((col) => {
                    const nullRate = proposal.column_null_rates[col] ?? 0
                    return (
                      <tr key={col} className="border-b last:border-0">
                        <td className="py-3 pr-4 font-mono text-xs">{col}</td>
                        <td className="py-3 pr-4">
                          <Select
                            value={editedMapping[col] ?? ''}
                            onValueChange={(value) => handleMappingChange(col, value)}
                          >
                            <SelectTrigger className="h-8">
                              <SelectValue placeholder="Select field" />
                            </SelectTrigger>
                            <SelectContent>
                              {proposal.available_fields.map((field) => (
                                <SelectItem key={field} value={field}>
                                  {field}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </td>
                        <td className="py-3 text-muted-foreground text-xs">
                          {nullRate > 0.1 ? `${(nullRate * 100).toFixed(0)}%` : null}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <DialogFooter showCloseButton>
              <Button variant="outline" onClick={resetState}>
                Back
              </Button>
              <Button onClick={handleConfirm}>
                Import →
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
