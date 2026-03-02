'use client'

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useInsights } from '@/hooks/use-insights'
import { Button } from '@/components/ui/button'

const COOLDOWN_KEY = 'insights_last_generated'
const COOLDOWN_MS = 60 * 60 * 1000 // 1 hour

export function GenerateButton() {
  const { refetch, isFetching } = useInsights()
  const [cooldownRemaining, setCooldownRemaining] = useState(0)

  // Hydrate cooldown from localStorage on mount (SSR-safe)
  useEffect(() => {
    if (typeof window === 'undefined') return
    const stored = localStorage.getItem(COOLDOWN_KEY)
    if (!stored) return
    const elapsed = Date.now() - parseInt(stored, 10)
    const remaining = Math.max(0, COOLDOWN_MS - elapsed)
    setCooldownRemaining(remaining)
  }, [])

  // Tick down every 30 seconds
  useEffect(() => {
    if (cooldownRemaining <= 0) return
    const id = setInterval(() => {
      setCooldownRemaining((prev) => Math.max(0, prev - 30_000))
    }, 30_000)
    return () => clearInterval(id)
  }, [cooldownRemaining])

  const handleGenerate = async () => {
    try {
      await refetch()
      const now = Date.now()
      localStorage.setItem(COOLDOWN_KEY, String(now))
      setCooldownRemaining(COOLDOWN_MS)
      toast.success('Insights updated')
    } catch {
      toast.error('Failed to generate insights. Please try again.')
    }
  }

  const minutesRemaining = Math.ceil(cooldownRemaining / 60_000)
  const isOnCooldown = cooldownRemaining > 0
  const isDisabled = isFetching || isOnCooldown

  return (
    <Button
      onClick={handleGenerate}
      disabled={isDisabled}
      size="lg"
      className="gap-2"
    >
      {isFetching && <Loader2 className="h-4 w-4 animate-spin" />}
      {isFetching
        ? 'Generating...'
        : isOnCooldown
          ? `Refreshes in ${minutesRemaining} minute${minutesRemaining === 1 ? '' : 's'}`
          : 'Generate New Insights'}
    </Button>
  )
}
