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
    <div className="flex flex-wrap gap-3 items-end">
      {/* Search input */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Search</label>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <Input
            type="text"
            placeholder="Search merchants…"
            value={searchInput}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9 w-52"
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
                className={cn(buttonVariants({ variant: 'outline' }), 'w-52 justify-start text-left font-normal')}
              >
                <CalendarIcon className="mr-2 h-4 w-4" />
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
          <SelectTrigger className="w-48">
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

      {/* Amount Min */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Min €</label>
        <Input
          type="number"
          placeholder="0"
          value={amountMin ?? ''}
          onChange={(e) => onAmountMinChange(e.target.value || undefined)}
          className="w-24"
        />
      </div>

      {/* Amount Max */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Max €</label>
        <Input
          type="number"
          placeholder="∞"
          value={amountMax ?? ''}
          onChange={(e) => onAmountMaxChange(e.target.value || undefined)}
          className="w-24"
        />
      </div>

      {/* Recurring toggle */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Recurring</label>
        <Button
          variant={isRecurring === true ? 'default' : 'outline'}
          size="sm"
          className="h-9"
          onClick={() => onIsRecurringChange(isRecurring === true ? undefined : true)}
        >
          Recurring only
        </Button>
      </div>

      {/* Sort By + Sort Order */}
      <div className="flex flex-col gap-1">
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
            <SelectTrigger className="w-32">
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
            onClick={() => onSortOrderChange(sortOrder === 'asc' ? 'desc' : 'asc')}
            aria-label={sortOrder === 'asc' ? 'Sort ascending' : 'Sort descending'}
          >
            {sortOrder === 'asc' ? (
              <ArrowUp className="h-4 w-4" />
            ) : (
              <ArrowDown className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {/* Clear All */}
      {hasActiveFilters && (
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground invisible">Clear</label>
          <Button variant="outline" size="sm" onClick={onClearAll}>
            Clear
          </Button>
        </div>
      )}
    </div>
  )
}
