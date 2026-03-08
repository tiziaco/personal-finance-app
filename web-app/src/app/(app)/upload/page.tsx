'use client'

import { useRef, useState } from 'react'
import { Upload, FileSpreadsheet, CheckCircle2, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useUploadCSV, useConfirmCSVUpload } from '@/hooks/use-csv-upload'
import type { CSVUploadProposalResponse, CSVUploadResponse } from '@/types/csv-upload'

type Step = 'idle' | 'uploading' | 'mapping' | 'confirming' | 'done'

export default function UploadPage() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [step, setStep] = useState<Step>('idle')
  const [proposal, setProposal] = useState<CSVUploadProposalResponse | null>(null)
  const [editedMapping, setEditedMapping] = useState<Record<string, string>>({})
  const [result, setResult] = useState<CSVUploadResponse | null>(null)
  const [errorsOpen, setErrorsOpen] = useState(false)

  const uploadMutation = useUploadCSV()
  const confirmMutation = useConfirmCSVUpload()

  function handleFile(file: File) {
    setStep('uploading')
    uploadMutation.mutate(file, {
      onSuccess: (data) => {
        setProposal(data)
        setEditedMapping({ ...data.proposed_mapping })
        setStep('mapping')
      },
      onError: () => {
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
    setStep('confirming')
    confirmMutation.mutate(
      { mappingId: proposal.mapping_id, confirmedMapping: editedMapping },
      {
        onSuccess: (data) => {
          setResult(data)
          setStep('done')
        },
        onError: () => {
          setStep('mapping')
        },
      }
    )
  }

  function resetToIdle() {
    setStep('idle')
    setProposal(null)
    setEditedMapping({})
    setResult(null)
    setErrorsOpen(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  if (step === 'idle' || step === 'uploading') {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] p-6">
        <Card className="w-full max-w-lg">
          <CardHeader className="text-center">
            <div className="flex justify-center mb-4">
              <FileSpreadsheet className="h-12 w-12 text-muted-foreground" />
            </div>
            <CardTitle>Upload CSV</CardTitle>
            <CardDescription>
              Import your bank transactions by uploading a CSV file. We&apos;ll automatically
              detect and map your columns.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div
              className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-muted-foreground/30 p-10 cursor-pointer hover:border-muted-foreground/60 transition-colors"
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="h-8 w-8 text-muted-foreground" />
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
              {step === 'uploading' ? 'Processing...' : 'Select File'}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if ((step === 'mapping' || step === 'confirming') && proposal) {
    const csvColumns = Object.keys(proposal.proposed_mapping)
    const sampleRows = proposal.sample_rows.slice(0, 3)

    return (
      <div className="flex flex-col gap-6 p-6 max-w-4xl mx-auto">
        <div>
          <h1 className="text-2xl font-bold">Review Column Mapping</h1>
          <p className="text-muted-foreground mt-1">
            We detected these columns. Adjust the mapping if needed before importing.
          </p>
        </div>

        <Card>
          <CardContent className="pt-6">
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
                {csvColumns.map((col) => {
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
          </CardContent>
        </Card>

        {sampleRows.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Sample rows</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b">
                    {csvColumns.map((col) => (
                      <th key={col} className="text-left font-medium pb-2 pr-4 font-mono">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sampleRows.map((row, i) => (
                    <tr key={i} className="border-b last:border-0">
                      {csvColumns.map((col) => (
                        <td key={col} className="py-2 pr-4 text-muted-foreground">
                          {String(row[col] ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}

        <div className="flex gap-3">
          <Button variant="outline" onClick={resetToIdle} disabled={step === 'confirming'}>
            Back
          </Button>
          <Button onClick={handleConfirm} disabled={step === 'confirming'}>
            {step === 'confirming'
              ? 'Importing...'
              : `Import ${proposal.sample_rows.length > 0 ? '' : ''}rows →`}
          </Button>
        </div>
      </div>
    )
  }

  if (step === 'done' && result) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] p-6">
        <Card className="w-full max-w-lg">
          <CardHeader className="text-center">
            <div className="flex justify-center mb-4">
              <CheckCircle2 className="h-12 w-12 text-green-500" />
            </div>
            <CardTitle>Import complete</CardTitle>
            <CardDescription>Your transactions have been imported successfully.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex justify-center gap-8 py-4">
              <div className="text-center">
                <p className="text-3xl font-bold">{result.imported}</p>
                <p className="text-sm text-muted-foreground mt-1">Imported</p>
              </div>
              {result.skipped > 0 && (
                <div className="text-center">
                  <p className="text-3xl font-bold text-muted-foreground">{result.skipped}</p>
                  <p className="text-sm text-muted-foreground mt-1">Skipped</p>
                </div>
              )}
            </div>

            {result.errors.length > 0 && (
              <div className="rounded-lg border border-destructive/30 overflow-hidden">
                <button
                  className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-destructive hover:bg-destructive/5 transition-colors"
                  onClick={() => setErrorsOpen((o) => !o)}
                >
                  <span>Show {result.errors.length} error{result.errors.length !== 1 ? 's' : ''}</span>
                  <ChevronDown
                    className={`h-4 w-4 transition-transform ${errorsOpen ? 'rotate-180' : ''}`}
                  />
                </button>
                {errorsOpen && (
                  <ul className="border-t border-destructive/20 px-4 py-3 text-xs text-muted-foreground space-y-1">
                    {result.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <Button onClick={resetToIdle} className="w-full">
              Upload another file
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return null
}
