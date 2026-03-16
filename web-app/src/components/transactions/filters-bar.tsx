'use client'

import { useRef, useState, useMemo, useCallback } from 'react'
import { Search, ArrowUp, ArrowDown, CalendarIcon } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { type DateRange } from 'react-day-picker'
import { Input } from '@/components/ui/input'
import { Button, buttonVariants } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { type CategoryEnum, CATEGORY_OPTIONS } from '@/types/transaction'

export interface FiltersBarProps {
  searchInput: string
  onSearchChange: (value: string) => void
  dateFrom: string | undefined
  onDateFromChange: (value: string | undefined) => void
  dateTo: string | undefined
  onDateToChange: (value: string | undefined) => void
  category: CategoryEnum | undefined
  onCategoryChange: (value: CategoryEnum | undefined) => void
  amountMin: string | undefined
  onAmountMinChange: (value: string | undefined) => void
  amountMax: string | undefined
  onAmountMaxChange: (value: string | undefined) => void
  isRecurring: boolean | undefined
  onIsRecurringChange: (value: boolean | undefined) => void
  sortBy: 'date' | 'amount' | 'merchant'
  onSortByChange: (value: 'date' | 'amount' | 'merchant') => void
  sortOrder: 'asc' | 'desc'
  onSortOrderChange: (value: 'asc' | 'desc') => void
  onClearAll: () => void
  hasActiveFilters: boolean
}

export function FiltersBar({
  searchInput,
  onSearchChange,
  dateFrom,
  onDateFromChange,
  dateTo,
  onDateToChange,
  category,
  onCategoryChange,
  amountMin,
  onAmountMinChange,
  amountMax,
  onAmountMaxChange,
  isRecurring,
  onIsRecurringChange,
  sortBy,
  onSortByChange,
  sortOrder,
  onSortOrderChange,
  onClearAll,
  hasActiveFilters,
}: FiltersBarProps) {
  const [calendarOpen, setCalendarOpen] = useState(false)
  const awaitingEndRef = useRef(false)
  const firstClickDateRef = useRef<string | null>(null)

  const selectedRange = useMemo<DateRange>(() => ({
    from: dateFrom ? parseISO(dateFrom) : undefined,
    to: dateTo ? parseISO(dateTo) : undefined,
  }), [dateFrom, dateTo])

  const triggerLabel = useMemo(() =>
    selectedRange.from
      ? selectedRange.to && selectedRange.from.getTime() !== selectedRange.to.getTime()
        ? `${format(selectedRange.from, 'MMM d')} → ${format(selectedRange.to, 'MMM d')}`
        : format(selectedRange.from, 'MMM d')
      : 'Pick a date range',
    [selectedRange]
  )

  const handleRangeSelect = useCallback((range: DateRange | undefined) => {
    if (!awaitingEndRef.current) {
      // First click — record start date, wait for end
      const fromStr = range?.from ? format(range.from, 'yyyy-MM-dd') : undefined
      firstClickDateRef.current = fromStr ?? null
      onDateFromChange(fromStr)
      onDateToChange(undefined)
      awaitingEndRef.current = true
    } else {
      // Second click — confirm and close
      awaitingEndRef.current = false
      if (range?.from && range?.to && range.from.getTime() !== range.to.getTime()) {
        // Different end date — commit range
        onDateFromChange(format(range.from, 'yyyy-MM-dd'))
        onDateToChange(format(range.to, 'yyyy-MM-dd'))
      } else {
        // Same date (react-day-picker sends undefined) — single-day selection
        onDateToChange(firstClickDateRef.current ?? undefined)
      }
      firstClickDateRef.current = null
      setCalendarOpen(false)
    }
  }, [onDateFromChange, onDateToChange])

  const handleOpenChange = useCallback((open: boolean) => {
    if (!open) {
      awaitingEndRef.current = false
      firstClickDateRef.current = null
    }
    setCalendarOpen(open)
  }, [])

  return (
    <div className="bg-card rounded-xl border border-border/60 p-4 shadow-sm space-y-3">
      <div className="flex flex-wrap gap-2 items-end">
        {/* Search input */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Search</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input
              type="text"
              placeholder="Search merchants…"
              value={searchInput}
              onChange={(e) => onSearchChange(e.target.value)}
              className="pl-8 h-8 w-44 text-sm"
            />
          </div>
        </div>

        {/* Date Range */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Date range</label>
          <Popover open={calendarOpen} onOpenChange={handleOpenChange}>
            <PopoverTrigger
              render={(props) => (
                <button
                  {...props}
                  className={cn(buttonVariants({ variant: 'outline' }), 'h-8 w-44 justify-start text-left text-sm font-normal')}
                >
                  <CalendarIcon className="mr-1.5 h-3.5 w-3.5" />
                  <span className={!selectedRange.from ? 'text-muted-foreground' : ''}>
                    {triggerLabel}
                  </span>
                </button>
              )}
            />
            <PopoverContent className="w-auto p-0" align="start">
              <Calendar
                mode="range"
                selected={selectedRange}
                onSelect={handleRangeSelect}
              />
            </PopoverContent>
          </Popover>
        </div>

        {/* Category dropdown */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Category</label>
          <Select
            value={category ?? 'all'}
            onValueChange={(value) => {
              if (value) {
                onCategoryChange(value === 'all' ? undefined : (value as CategoryEnum))
              }
            }}
          >
            <SelectTrigger className="h-8 w-44 text-sm">
              <SelectValue placeholder="All categories" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {CATEGORY_OPTIONS.map((cat) => (
                <SelectItem key={cat} value={cat}>
                  {cat}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Amount range */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Amount range</label>
          <div className="flex items-center gap-1">
            <Input
              type="number"
              placeholder="Min"
              value={amountMin ?? ''}
              onChange={(e) => onAmountMinChange(e.target.value || undefined)}
              className="h-8 w-20 text-sm"
            />
            <span className="text-xs text-muted-foreground">–</span>
            <Input
              type="number"
              placeholder="Max"
              value={amountMax ?? ''}
              onChange={(e) => onAmountMaxChange(e.target.value || undefined)}
              className="h-8 w-20 text-sm"
            />
          </div>
        </div>

        {/* Recurring toggle */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground invisible">Recurring</label>
          <Button
            variant={isRecurring === true ? 'default' : 'outline'}
            size="sm"
            className="h-8 text-sm"
            onClick={() => onIsRecurringChange(isRecurring === true ? undefined : true)}
          >
            Recurring only
          </Button>
        </div>

        {/* Sort By + Sort Order — pushed to the right */}
        <div className="flex flex-col gap-1 ml-auto">
          <label className="text-xs text-muted-foreground">Sort by</label>
          <div className="flex items-center gap-1">
            <Select
              value={sortBy}
              onValueChange={(value) => {
                if (value) {
                  onSortByChange(value as 'date' | 'amount' | 'merchant')
                }
              }}
            >
              <SelectTrigger className="h-8 w-28 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="date">Date</SelectItem>
                <SelectItem value="amount">Amount</SelectItem>
                <SelectItem value="merchant">Merchant</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => onSortOrderChange(sortOrder === 'asc' ? 'desc' : 'asc')}
              aria-label={sortOrder === 'asc' ? 'Sort ascending' : 'Sort descending'}
            >
              {sortOrder === 'asc' ? (
                <ArrowUp className="h-3.5 w-3.5" />
              ) : (
                <ArrowDown className="h-3.5 w-3.5" />
              )}
            </Button>
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" className="h-8 text-sm text-muted-foreground hover:text-foreground" onClick={onClearAll}>
                Clear
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
